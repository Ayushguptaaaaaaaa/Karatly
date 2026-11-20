"""Customers and dealers (suppliers): add, edit, search, with their sales / purchase totals."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Bill, Customer, Dealer, StockMovement, User
from app.models.enums import MovementType
from app.services import audit_service, costing_service, data_version_service

money = costing_service.money
CUSTOMER_FIELDS = ("name", "phone", "email", "city", "state", "country", "notes")
DEALER_FIELDS = ("name", "phone", "city", "state", "country", "gstin", "notes")


def _clean(data: dict, fields: tuple[str, ...]) -> dict:
    out = {}
    for f in fields:
        if f in data:
            v = data[f]
            v = v.strip() if isinstance(v, str) else v
            out[f] = v or None
    if "country" in out and not out["country"]:
        out["country"] = "India"
    return out


def _title(s: str | None) -> str | None:
    """'mumbai' -> 'Mumbai' so the same city is not counted twice."""
    if not s:
        return s
    return " ".join(w[:1].upper() + w[1:] for w in s.split())


# ---------------------------------------------------------------- customers
def customer_out(c: Customer, stats: dict | None = None) -> dict:
    st = stats or {}
    return {"id": c.id, "name": c.name, "phone": c.phone, "email": c.email, "city": c.city, "state": c.state,
            "country": c.country, "notes": c.notes, "created_at": c.created_at,
            "bills": st.get("bills", 0), "pieces": st.get("pieces", 0), "revenue": float(st.get("revenue", 0)),
            "last_bill_on": st.get("last"), }


def _customer_stats(db: Session, ids: list[int] | None = None) -> dict[int, dict]:
    q = (db.query(Bill.customer_id, Bill.id, Bill.taxable, Bill.bill_date)
         .filter(Bill.is_void.is_(False), Bill.customer_id.isnot(None)))
    if ids is not None:
        q = q.filter(Bill.customer_id.in_(ids))
    bills = q.all()
    pieces = defaultdict(int)
    if bills:
        rows = (db.query(StockMovement.bill_id, StockMovement.quantity)
                .filter(StockMovement.bill_id.in_([b.id for b in bills]), StockMovement.is_void.is_(False)).all())
        for bid, q_ in rows:
            pieces[bid] += q_
    out: dict[int, dict] = defaultdict(lambda: {"bills": 0, "pieces": 0, "revenue": Decimal(0), "last": None})
    for cid, bid, taxable, on in bills:
        s = out[cid]
        s["bills"] += 1
        s["pieces"] += pieces[bid]
        s["revenue"] += Decimal(taxable or 0)
        s["last"] = max(s["last"], on) if s["last"] else on
    return out


def list_customers(db: Session, q: str | None = None, limit: int = 500) -> list[dict]:
    query = db.query(Customer).filter(Customer.is_active.is_(True))
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.filter(or_(Customer.name_key.like(like), Customer.phone.like(f"%{q.strip()}%"),
                                 Customer.city.ilike(like)))
    rows = query.order_by(Customer.name_key).limit(limit).all()
    stats = _customer_stats(db, [c.id for c in rows])
    return [customer_out(c, stats.get(c.id)) for c in rows]


def get_customer(db: Session, cid: int) -> Customer:
    c = db.get(Customer, cid)
    if not c or not c.is_active:
        raise AppError("CUSTOMER_NOT_FOUND", "Customer not found", 404)
    return c


def create_customer(db: Session, user: User | None, data: dict, commit: bool = True) -> Customer:
    d = _clean(data, CUSTOMER_FIELDS)
    if not d.get("name"):
        raise AppError("VALIDATION_ERROR", "Customer name is required", 422, {"fields": {"name": "Required"}})
    for f in ("city", "state", "country"):
        d[f] = _title(d.get(f))
    if d.get("phone"):
        dup = db.query(Customer).filter(Customer.phone == d["phone"], Customer.is_active.is_(True)).first()
        if dup:
            raise AppError("CUSTOMER_EXISTS", f"{dup.name} already has this phone number.", 409, {"customer_id": dup.id})
    c = Customer(**d, name_key=d["name"].lower())
    c.country = c.country or "India"
    db.add(c)
    db.flush()
    audit_service.log(db, user, "CREATE", "customer", c.id, after={"name": c.name})
    if commit:
        ev = data_version_service.notify(db, "customer", "create", c.id)
        db.commit()
        data_version_service.publish(ev)
    return c


def update_customer(db: Session, user: User, cid: int, data: dict) -> dict:
    c = get_customer(db, cid)
    d = _clean(data, CUSTOMER_FIELDS)
    if "name" in d and not d["name"]:
        raise AppError("VALIDATION_ERROR", "Customer name is required", 422, {"fields": {"name": "Required"}})
    for k, v in d.items():
        setattr(c, k, _title(v) if k in ("city", "state", "country") else v)
    c.name_key = c.name.lower()
    audit_service.log(db, user, "UPDATE", "customer", c.id, after=d)
    ev = data_version_service.notify(db, "customer", "update", c.id)
    db.commit()
    data_version_service.publish(ev)
    return customer_out(c, _customer_stats(db, [c.id]).get(c.id))


def delete_customer(db: Session, user: User, cid: int) -> None:
    c = get_customer(db, cid)
    c.is_active = False  # bills keep their copy of the name and region
    audit_service.log(db, user, "DELETE", "customer", c.id)
    ev = data_version_service.notify(db, "customer", "delete", c.id)
    db.commit()
    data_version_service.publish(ev)


# ---------------------------------------------------------------- dealers
def dealer_out(d: Dealer, stats: dict | None = None) -> dict:
    st = stats or {}
    return {"id": d.id, "name": d.name, "phone": d.phone, "city": d.city, "state": d.state, "country": d.country,
            "gstin": d.gstin, "notes": d.notes, "created_at": d.created_at,
            "purchases": st.get("purchases", 0), "pieces": st.get("pieces", 0), "amount": float(st.get("amount", 0)),
            "designs": len(st.get("designs", ())), "last_purchase_on": st.get("last")}


def _dealer_stats(db: Session, ids: list[int] | None = None) -> dict[int, dict]:
    q = (db.query(StockMovement.dealer_id, StockMovement.design_id, StockMovement.quantity, StockMovement.unit_price,
                  StockMovement.occurred_on)
         .filter(StockMovement.is_void.is_(False), StockMovement.dealer_id.isnot(None),
                 StockMovement.type.in_([MovementType.PURCHASE, MovementType.OPENING])))
    if ids is not None:
        q = q.filter(StockMovement.dealer_id.in_(ids))
    out: dict[int, dict] = defaultdict(lambda: {"purchases": 0, "pieces": 0, "amount": Decimal(0), "designs": set(),
                                                "last": None})
    for did, design_id, qty, price, on in q.all():
        s = out[did]
        s["purchases"] += 1
        s["pieces"] += qty
        s["amount"] += Decimal(price or 0) * qty
        s["designs"].add(design_id)
        s["last"] = max(s["last"], on) if s["last"] else on
    return out


def get_or_create_dealer(db: Session, user: User | None, name: str, city: str | None = None,
                         state: str | None = None) -> Dealer:
    """Find a dealer by name (case-insensitive) or create it. Used by imports and the design form."""
    key = " ".join(name.strip().lower().split())
    d = db.query(Dealer).filter(Dealer.name_key == key, Dealer.is_active.is_(True)).first()
    if d:
        if city and not d.city:
            d.city = _title(city)
        if state and not d.state:
            d.state = _title(state)
        return d
    return create_dealer(db, user, {"name": " ".join(name.split()), "city": city, "state": state}, commit=False)


def list_dealers(db: Session, q: str | None = None) -> list[dict]:
    query = db.query(Dealer).filter(Dealer.is_active.is_(True))
    if q:
        query = query.filter(Dealer.name_key.like(f"%{q.strip().lower()}%"))
    rows = query.order_by(Dealer.name_key).all()
    stats = _dealer_stats(db, [d.id for d in rows])
    return [dealer_out(d, stats.get(d.id)) for d in rows]


def get_dealer(db: Session, did: int) -> Dealer:
    d = db.get(Dealer, did)
    if not d or not d.is_active:
        raise AppError("DEALER_NOT_FOUND", "Dealer not found", 404)
    return d


def create_dealer(db: Session, user: User | None, data: dict, commit: bool = True) -> Dealer:
    d = _clean(data, DEALER_FIELDS)
    if not d.get("name"):
        raise AppError("VALIDATION_ERROR", "Dealer name is required", 422, {"fields": {"name": "Required"}})
    for f in ("city", "state", "country"):
        d[f] = _title(d.get(f))
    key = d["name"].lower()
    if db.query(Dealer).filter(Dealer.name_key == key, Dealer.is_active.is_(True)).first():
        raise AppError("DEALER_EXISTS", f"Dealer {d['name']} already exists.", 409)
    dl = Dealer(**d, name_key=key)
    dl.country = dl.country or "India"
    db.add(dl)
    db.flush()
    audit_service.log(db, user, "CREATE", "dealer", dl.id, after={"name": dl.name})
    if commit:
        ev = data_version_service.notify(db, "dealer", "create", dl.id)
        db.commit()
        data_version_service.publish(ev)
    return dl


def update_dealer(db: Session, user: User, did: int, data: dict) -> dict:
    dl = get_dealer(db, did)
    d = _clean(data, DEALER_FIELDS)
    if "name" in d and not d["name"]:
        raise AppError("VALIDATION_ERROR", "Dealer name is required", 422, {"fields": {"name": "Required"}})
    for k, v in d.items():
        setattr(dl, k, _title(v) if k in ("city", "state", "country") else v)
    dl.name_key = dl.name.lower()
    audit_service.log(db, user, "UPDATE", "dealer", dl.id, after=d)
    ev = data_version_service.notify(db, "dealer", "update", dl.id)
    db.commit()
    data_version_service.publish(ev)
    return dealer_out(dl, _dealer_stats(db, [dl.id]).get(dl.id))


def delete_dealer(db: Session, user: User, did: int) -> None:
    dl = get_dealer(db, did)
    dl.is_active = False
    audit_service.log(db, user, "DELETE", "dealer", dl.id)
    ev = data_version_service.notify(db, "dealer", "delete", dl.id)
    db.commit()
    data_version_service.publish(ev)

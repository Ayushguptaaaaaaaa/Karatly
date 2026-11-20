"""Excel-style explorer for sales and purchases: filter by anything, group by one dimension, sort, export.

Sales rows come from SALE stock movements (minus nothing: returns are tracked separately), joined to their
bill (customer + region). Purchases come from PURCHASE / OPENING movements joined to their dealer.
Revenue is the price after bill discount, before GST.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError
from app.models import Bill, Category, Customer, Dealer, Design, StockMovement
from app.models.enums import MovementType
from app.services import costing_service
from app.services.import_export_service import build_xlsx

money = costing_service.money
WALK_IN = "Walk-in customer"
UNKNOWN = "Not set"

SALES_GROUPS = {
    "customer": "Customer", "city": "City", "state": "State", "country": "Country", "design": "Design",
    "category": "Category", "subcategory": "Subcategory", "metal": "Material", "month": "Month", "day": "Day",
    "payment_mode": "Payment",
}
PURCHASE_GROUPS = {
    "dealer": "Dealer", "dealer_city": "Dealer city", "dealer_state": "Dealer state", "design": "Design",
    "category": "Category", "metal": "Material", "month": "Month", "day": "Day",
}


def _month_label(d: date) -> str:
    return d.strftime("%b %Y")


# ---------------------------------------------------------------- row loading
def _base(db: Session, types: list[MovementType], f: dict):
    q = (db.query(StockMovement)
         .options(joinedload(StockMovement.design).joinedload(Design.category),
                  joinedload(StockMovement.design).joinedload(Design.subcategory),
                  joinedload(StockMovement.bill), joinedload(StockMovement.dealer))
         .join(Design, Design.id == StockMovement.design_id)
         .filter(StockMovement.is_void.is_(False), StockMovement.type.in_(types)))
    if f.get("date_from"):
        q = q.filter(StockMovement.occurred_on >= f["date_from"])
    if f.get("date_to"):
        q = q.filter(StockMovement.occurred_on <= f["date_to"])
    if f.get("category_id"):
        q = q.filter(Design.category_id == f["category_id"])
    if f.get("design_id"):
        q = q.filter(StockMovement.design_id == f["design_id"])
    if f.get("label"):
        q = q.filter(Design.label.contains(f["label"].strip().upper()))
    if f.get("metal"):
        q = q.filter(Design.metal == f["metal"])
    return q


def sales_rows(db: Session, f: dict) -> list[dict]:
    q = _base(db, [MovementType.SALE], f).outerjoin(Bill, Bill.id == StockMovement.bill_id)
    if f.get("customer_id"):
        q = q.filter(Bill.customer_id == f["customer_id"])
    if f.get("walk_in"):
        q = q.filter(Bill.customer_id.is_(None))
    for key, col in (("city", Bill.city), ("state", Bill.state), ("country", Bill.country)):
        if f.get(key):
            q = q.filter(col == f[key])
    if f.get("payment_mode"):
        q = q.filter(Bill.payment_mode == f["payment_mode"])
    out = []
    for m in q.all():
        d, b = m.design, m.bill
        price = Decimal(m.unit_price or 0)
        out.append({
            "id": m.id, "date": m.occurred_on, "bill_id": b.id if b else None, "bill_number": b.number if b else None,
            "customer_id": b.customer_id if b else None, "customer": b.customer_name if b else WALK_IN,
            "city": (b.city if b else None) or UNKNOWN, "state": (b.state if b else None) or UNKNOWN,
            "country": (b.country if b else None) or UNKNOWN, "payment_mode": (b.payment_mode if b else None) or UNKNOWN,
            "design_id": d.id, "design": d.label, "design_name": d.name, "category": d.category.name,
            "subcategory": d.subcategory.name if d.subcategory else UNKNOWN, "metal": d.metal.value,
            "qty": m.quantity, "unit_price": price, "revenue": price * m.quantity,
        })
    return out


def purchase_rows(db: Session, f: dict) -> list[dict]:
    types = [MovementType.PURCHASE] if f.get("purchases_only") else [MovementType.PURCHASE, MovementType.OPENING]
    q = _base(db, types, f).outerjoin(Dealer, Dealer.id == StockMovement.dealer_id)
    if f.get("dealer_id"):
        q = q.filter(StockMovement.dealer_id == f["dealer_id"])
    if f.get("no_dealer"):
        q = q.filter(StockMovement.dealer_id.is_(None))
    if f.get("dealer_city"):
        q = q.filter(Dealer.city == f["dealer_city"])
    if f.get("dealer_state"):
        q = q.filter(Dealer.state == f["dealer_state"])
    out = []
    for m in q.all():
        d, dl = m.design, m.dealer
        cost = Decimal(m.unit_price or 0)
        out.append({
            "id": m.id, "date": m.occurred_on, "type": "Opening stock" if m.type == MovementType.OPENING else "Purchase",
            "dealer_id": dl.id if dl else None, "dealer": dl.name if dl else UNKNOWN,
            "dealer_city": (dl.city if dl else None) or UNKNOWN, "dealer_state": (dl.state if dl else None) or UNKNOWN,
            "design_id": d.id, "design": d.label, "design_name": d.name, "category": d.category.name,
            "metal": d.metal.value, "qty": m.quantity, "unit_cost": cost, "amount": cost * m.quantity,
        })
    return out


# ---------------------------------------------------------------- grouping
def _key(r: dict, group: str) -> tuple[Any, str]:
    if group == "month":
        return r["date"].strftime("%Y-%m"), _month_label(r["date"])
    if group == "day":
        return r["date"].isoformat(), r["date"].strftime("%d %b %Y")
    if group == "customer":
        return (r["customer_id"] or 0), r["customer"]
    if group == "dealer":
        return (r["dealer_id"] or 0), r["dealer"]
    if group == "design":
        return r["design_id"], r["design"]
    return r[group], str(r[group])


def _group(rows: list[dict], group: str, value_key: str) -> list[dict]:
    acc: dict[Any, dict] = {}
    for r in rows:
        k, label = _key(r, group)
        g = acc.get(k)
        if g is None:
            g = acc[k] = {"key": str(k), "label": label, "qty": 0, "value": Decimal(0), "entries": 0,
                          "_bills": set(), "_customers": set(), "_designs": set(), "_dealers": set()}
            if group == "design":
                g["sub"] = f"{r['design_name'] or ''} · {r['category']}".strip(" ·")
        g["qty"] += r["qty"]
        g["value"] += r[value_key]
        g["entries"] += 1
        if r.get("bill_id"):
            g["_bills"].add(r["bill_id"])
        g["_customers"].add(r.get("customer_id") or r.get("customer"))
        g["_designs"].add(r["design_id"])
        g["_dealers"].add(r.get("dealer_id"))
    total = sum((g["value"] for g in acc.values()), Decimal(0))
    out = []
    for g in acc.values():
        out.append({
            "key": g["key"], "label": g["label"], "sub": g.get("sub"), "qty": g["qty"], "value": float(money(g["value"])),
            "entries": g["entries"], "bills": len(g["_bills"]), "customers": len(g["_customers"]),
            "designs": len(g["_designs"]), "dealers": len([x for x in g["_dealers"] if x]),
            "avg_price": float(money(g["value"] / g["qty"])) if g["qty"] else 0.0,
            "share_pct": round(float(g["value"] / total * 100), 1) if total else 0.0,
        })
    return out


def _sort(items: list[dict], sort_by: str | None, desc: bool, default: str) -> list[dict]:
    key = sort_by or default
    if items and key not in items[0]:
        key = default

    def k(x):
        v = x.get(key)
        return (v is None, v.lower() if isinstance(v, str) else v)

    return sorted(items, key=k, reverse=desc)


def _page(items: list[dict], page: int, page_size: int) -> tuple[list[dict], int, int]:
    page_size = max(1, min(int(page_size or 50), 500))
    page = max(1, int(page or 1))
    return items[(page - 1) * page_size: page * page_size], page, page_size


def _jsonable(r: dict) -> dict:
    return {k: (float(money(v)) if isinstance(v, Decimal) else v) for k, v in r.items()}


# ---------------------------------------------------------------- public
def explore(db: Session, kind: str, f: dict, group_by: str | None, sort_by: str | None, sort_dir: str | None,
            page: int = 1, page_size: int = 50) -> dict:
    sales = kind == "sales"
    groups = SALES_GROUPS if sales else PURCHASE_GROUPS
    if group_by and group_by not in groups:
        raise AppError("VALIDATION_ERROR", f"Can't group by {group_by}", 422)
    rows = sales_rows(db, f) if sales else purchase_rows(db, f)
    value_key = "revenue" if sales else "amount"
    total_value = sum((r[value_key] for r in rows), Decimal(0))
    totals = {
        "entries": len(rows), "qty": sum(r["qty"] for r in rows), "value": float(money(total_value)),
        "designs": len({r["design_id"] for r in rows}),
        "bills": len({r["bill_id"] for r in rows if r.get("bill_id")}) if sales else None,
        "customers": len({r.get("customer_id") or r.get("customer") for r in rows}) if sales else None,
        "dealers": len({r["dealer_id"] for r in rows if r.get("dealer_id")}) if not sales else None,
    }
    desc = (sort_dir or "desc").lower() != "asc"
    if group_by:
        items = _group(rows, group_by, value_key)
        if group_by in ("month", "day") and sort_by in (None, "", "label", "key"):
            items = sorted(items, key=lambda x: x["key"], reverse=bool(sort_by) and desc)  # by date, not by name
        else:
            items = _sort(items, sort_by, desc, "value")
        chart = sorted(items, key=lambda x: -x["value"])[:12] if group_by not in ("month", "day") else items[-24:]
        page_items, page, page_size = _page(items, page, page_size)
        return {"kind": kind, "group_by": group_by, "group_label": groups[group_by], "items": page_items,
                "total": len(items), "page": page, "page_size": page_size, "totals": totals,
                "chart": [{"label": c["label"], "value": c["value"], "qty": c["qty"]} for c in chart]}
    items = _sort(rows, sort_by, desc, "date")
    page_items, page, page_size = _page(items, page, page_size)
    return {"kind": kind, "group_by": None, "group_label": None, "items": [_jsonable(r) for r in page_items],
            "total": len(items), "page": page, "page_size": page_size, "totals": totals, "chart": []}


def facets(db: Session) -> dict:
    """Values for the filter dropdowns."""
    def distinct(col, *filters):
        return sorted({v for (v,) in db.query(col).filter(*filters).distinct().all() if v})

    cities = set(distinct(Bill.city)) | set(distinct(Customer.city))
    states = set(distinct(Bill.state)) | set(distinct(Customer.state))
    countries = set(distinct(Bill.country)) | set(distinct(Customer.country))
    return {
        "cities": sorted(cities), "states": sorted(states), "countries": sorted(countries),
        "payment_modes": distinct(Bill.payment_mode),
        "dealer_cities": distinct(Dealer.city, Dealer.is_active.is_(True)),
        "dealer_states": distinct(Dealer.state, Dealer.is_active.is_(True)),
        "customers": [{"value": str(c.id), "label": c.name + (f" · {c.city}" if c.city else "")}
                      for c in db.query(Customer).filter(Customer.is_active.is_(True)).order_by(Customer.name_key)],
        "dealers": [{"value": str(d.id), "label": d.name}
                    for d in db.query(Dealer).filter(Dealer.is_active.is_(True)).order_by(Dealer.name_key)],
        "categories": [{"value": str(c.id), "label": c.name}
                       for c in db.query(Category).filter(Category.is_active.is_(True)).order_by(Category.sort_order)],
        "sales_groups": [{"value": k, "label": v} for k, v in SALES_GROUPS.items()],
        "purchase_groups": [{"value": k, "label": v} for k, v in PURCHASE_GROUPS.items()],
    }


def export_xlsx(db: Session, kind: str, f: dict, group_by: str | None, sort_by: str | None,
                sort_dir: str | None) -> tuple[str, bytes]:
    data = explore(db, kind, f, group_by, sort_by, sort_dir, page=1, page_size=100000)
    sales = kind == "sales"
    vname = "Revenue" if sales else "Amount"
    if group_by:
        heads = [data["group_label"], "Pieces", vname, "Avg price", "Share %"]
        heads += ["Bills", "Customers"] if sales else ["Entries", "Designs"]
        rows = [[i["label"], i["qty"], i["value"], i["avg_price"], i["share_pct"]]
                + ([i["bills"], i["customers"]] if sales else [i["entries"], i["designs"]]) for i in data["items"]]
        rows.append(["TOTAL", data["totals"]["qty"], data["totals"]["value"], "", 100])
        money_cols = {2, 3}
    elif sales:
        heads = ["Date", "Bill", "Customer", "City", "State", "Country", "Design", "Name", "Category", "Material",
                 "Pieces", "Price / piece", "Revenue", "Payment"]
        rows = [[i["date"], i["bill_number"] or "", i["customer"], i["city"], i["state"], i["country"], i["design"],
                 i["design_name"] or "", i["category"], i["metal"], i["qty"], i["unit_price"], i["revenue"],
                 i["payment_mode"]] for i in data["items"]]
        money_cols = {11, 12}
    else:
        heads = ["Date", "Type", "Dealer", "Dealer city", "Dealer state", "Design", "Name", "Category", "Material",
                 "Pieces", "Cost / piece", "Amount"]
        rows = [[i["date"], i["type"], i["dealer"], i["dealer_city"], i["dealer_state"], i["design"],
                 i["design_name"] or "", i["category"], i["metal"], i["qty"], i["unit_cost"], i["amount"]]
                for i in data["items"]]
        money_cols = {10, 11}
    name = f"{kind}_{group_by or 'detail'}.xlsx"
    return name, build_xlsx(f"{kind.title()} by {group_by or 'entry'}", heads, rows, money_cols)


def top(db: Session, f: dict, group_by: str, n: int = 5) -> list[dict]:
    """Small helper for insights / chat: top N groups of sales by revenue."""
    return explore(db, "sales", f, group_by, "value", "desc", 1, n)["items"]


def dealer_summary(db: Session, f: dict, n: int = 5) -> list[dict]:
    return explore(db, "purchases", f, "dealer", "value", "desc", 1, n)["items"]



def summary(db: Session, date_from: date, date_to: date, n: int = 5) -> dict:
    """Compact who / where / from-whom summary for a period (insights report, chat, dashboards)."""
    f = {"date_from": date_from, "date_to": date_to}
    rows = sales_rows(db, f)

    def top_of(group: str) -> list[dict]:
        items = sorted(_group(rows, group, "revenue"), key=lambda x: -x["value"])
        return [{"name": i["label"], "pieces": i["qty"], "revenue": i["value"], "share_pct": i["share_pct"],
                 "bills": i["bills"]} for i in items if i["label"] not in (WALK_IN, UNKNOWN)][:n]

    named = [r for r in rows if r.get("customer_id")]
    walk_in_rev = sum((r["revenue"] for r in rows if not r.get("customer_id")), Decimal(0))
    total = sum((r["revenue"] for r in rows), Decimal(0))
    purchases = purchase_rows(db, f)  # deliveries incl. opening stock, so an imported shop shows its dealers
    dealers = sorted(_group(purchases, "dealer", "amount"), key=lambda x: -x["value"])
    return {
        "top_customers": [c for c in top_of("customer") if c["name"] != WALK_IN][:n],
        "top_cities": [c for c in top_of("city") if c["name"] != UNKNOWN][:n],
        "top_states": [c for c in top_of("state") if c["name"] != UNKNOWN][:n],
        "top_countries": [c for c in top_of("country") if c["name"] != UNKNOWN][:n],
        "material_mix": top_of("metal"),
        "payment_mix": [c for c in top_of("payment_mode") if c["name"] != UNKNOWN],
        "customers": {"named_customers": len({r["customer_id"] for r in named}), "bills": len({r["bill_id"] for r in rows
                                                                                              if r.get("bill_id")}),
                      "walk_in_share_pct": round(float(walk_in_rev / total * 100), 1) if total else 0.0},
        "top_dealers": [{"name": d["label"], "pieces": d["qty"], "amount": d["value"], "designs": d["designs"],
                         "share_pct": d["share_pct"]} for d in dealers[:n]],
    }


def design_parties(db: Session, date_from: date | None = None, date_to: date | None = None) -> dict[int, dict]:
    """Per design: its dealer (latest delivery, any time) and who bought it in the period."""
    out: dict[int, dict] = {}
    q = (db.query(StockMovement.design_id, Dealer.name, Dealer.id)
         .join(Dealer, Dealer.id == StockMovement.dealer_id)
         .filter(StockMovement.is_void.is_(False),
                 StockMovement.type.in_([MovementType.PURCHASE, MovementType.OPENING]))
         .order_by(StockMovement.occurred_on, StockMovement.id))
    dealers_per: dict[int, set] = {}
    for did, name, dealer_id in q.all():
        out.setdefault(did, {})["dealer"] = name
        out[did]["dealer_id"] = dealer_id
        dealers_per.setdefault(did, set()).add(dealer_id)
    for did, s in dealers_per.items():
        out[did]["dealers"] = len(s)
    q = (db.query(StockMovement.design_id, Bill.customer_id, Bill.customer_name, StockMovement.quantity,
                  StockMovement.unit_price)
         .join(Bill, Bill.id == StockMovement.bill_id)
         .filter(StockMovement.is_void.is_(False), StockMovement.type == MovementType.SALE,
                 Bill.customer_id.isnot(None)))
    if date_from:
        q = q.filter(StockMovement.occurred_on >= date_from)
    if date_to:
        q = q.filter(StockMovement.occurred_on <= date_to)
    per: dict[int, dict] = {}
    for did, cid, cname, qty, price in q.all():
        c = per.setdefault(did, {}).setdefault(cid, {"name": cname, "pieces": 0, "revenue": Decimal(0)})
        c["pieces"] += qty
        c["revenue"] += Decimal(price or 0) * qty
    for did, custs in per.items():
        top = max(custs.values(), key=lambda c: c["revenue"])
        out.setdefault(did, {}).update(customers=len(custs), top_customer=top["name"])
    return out


def parties_for_design(db: Session, design_id: int) -> dict:
    """Design page: every dealer it came from and every customer who bought it (all time)."""
    f = {"design_id": design_id}
    sales = explore(db, "sales", f, "customer", "value", "desc", 1, 50)
    buys = explore(db, "purchases", f, "dealer", "value", "desc", 1, 50)
    return {
        "customers": [{"id": int(i["key"]) or None, "name": i["label"], "pieces": i["qty"], "revenue": i["value"],
                       "bills": i["bills"]} for i in sales["items"]],
        "dealers": [{"id": int(i["key"]) or None, "name": i["label"], "pieces": i["qty"], "amount": i["value"],
                     "deliveries": i["entries"]} for i in buys["items"]],
    }

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.clock import now_utc, today as _today
from app.core.errors import AppError
from app.models import Design, StockMovement, User
from app.models.enums import IN_TYPES, MovementSource, MovementType, direction
from app.services import audit_service, data_version_service, metrics_service
from app.services.serializers import movement_out

TYPE_LABELS = {
    MovementType.OPENING: "Opening stock",
    MovementType.PURCHASE: "New stock received",
    MovementType.CUSTOMER_RETURN: "Customer return",
    MovementType.ADJUSTMENT_IN: "Correction (+)",
    MovementType.SALE: "Sale",
    MovementType.SUPPLIER_RETURN: "Return to supplier",
    MovementType.ADJUSTMENT_OUT: "Correction (−)",
}


def stock_now(db: Session, design_id: int) -> int:
    return int(
        db.query(func.coalesce(func.sum(StockMovement.signed_qty), 0))
        .filter(StockMovement.design_id == design_id, StockMovement.is_void.is_(False))
        .scalar()
    )


def stock_as_of(db: Session, design_id: int, on: date) -> int:
    return int(
        db.query(func.coalesce(func.sum(StockMovement.signed_qty), 0))
        .filter(StockMovement.design_id == design_id, StockMovement.is_void.is_(False),
                StockMovement.occurred_on <= on)
        .scalar()
    )


def _check_can_remove(db: Session, design: Design, qty: int, on: date) -> None:
    now_stock = stock_now(db, design.id)
    as_of = stock_as_of(db, design.id, on)
    if now_stock - qty < 0 or as_of - qty < 0:
        avail = min(now_stock, as_of)
        when = "" if on >= _today() else f" on {on.strftime('%d %b %Y')}"
        raise AppError(
            "INSUFFICIENT_STOCK",
            f"Only {avail} in stock for {design.label}{when}.",
            409,
            {"available": avail, "label": design.label},
        )


def _resolve_design(db: Session, design_id: int | None, label: str | None) -> Design:
    design = None
    if design_id:
        design = db.get(Design, design_id)
    elif label:
        design = db.query(Design).filter(Design.label == label.strip().upper()).first()
    if not design:
        raise AppError("DESIGN_NOT_FOUND", f"Design {label or design_id} not found", 404)
    return design


def _add_movement(db: Session, user: User | None, design: Design, mtype: MovementType, qty: int,
                  occurred_on: date | None = None, unit_price=None, note: str | None = None,
                  source: MovementSource = MovementSource.MANUAL, plan_item_id: int | None = None,
                  check: bool = True) -> StockMovement:
    mtype = MovementType(mtype)
    if qty is None or int(qty) <= 0:
        raise AppError("VALIDATION_ERROR", "Quantity must be at least 1", 422, {"fields": {"quantity": "Must be ≥ 1"}})
    qty = int(qty)
    on = occurred_on or _today()
    if on > _today():
        raise AppError("FUTURE_DATE", "The date cannot be in the future.", 422, {"fields": {"occurred_on": "Future date"}})
    if not design.is_active and source != MovementSource.DEMO:
        raise AppError("DESIGN_ARCHIVED", f"{design.label} is archived. Unarchive it to record stock.", 409)
    if check and mtype not in IN_TYPES:
        _check_can_remove(db, design, qty, on)
    if unit_price is None:
        if mtype == MovementType.SALE:
            unit_price = design.selling_price
        elif mtype in (MovementType.PURCHASE, MovementType.OPENING):
            unit_price = design.cost_price
    if unit_price is not None and Decimal(str(unit_price)) < 0:
        raise AppError("VALIDATION_ERROR", "Price cannot be negative", 422, {"fields": {"unit_price": "≥ 0"}})
    m = StockMovement(
        design_id=design.id, type=mtype, quantity=qty, signed_qty=direction(mtype) * qty,
        unit_price=unit_price, occurred_on=on, note=(note or None), source=source,
        purchase_plan_item_id=plan_item_id, created_by=user.id if user else None,
    )
    db.add(m)
    db.flush()
    return m


def _design_brief(db: Session, design: Design) -> dict:
    snap = metrics_service.snapshot(db)
    st = snap.states[design.id]
    return {"id": design.id, "label": design.label, "current_stock": st.current_stock,
            "status": st.status.value, "demand_class": st.demand.value}


def record(db: Session, user: User, data: dict) -> dict:
    design = _resolve_design(db, data.get("design_id"), data.get("label"))
    if MovementType(data["type"]) == MovementType.SALE:
        # every sale is billed (customer optional = walk-in)
        from app.services import billing_service

        bill = billing_service.create_bill(db, user, {
            "bill_date": data.get("occurred_on"), "customer_id": data.get("customer_id"),
            "customer": data.get("customer"), "payment_mode": data.get("payment_mode"), "notes": data.get("note"),
            "items": [{"design_id": design.id, "quantity": data.get("quantity"), "unit_price": data.get("unit_price")}],
        })
        m = bill.items[0]
        db.refresh(m)
        return {"movement": movement_out(m), "design": _design_brief(db, design), "bill_id": bill.id,
                "bill_number": bill.number}
    m = _add_movement(db, user, design, data["type"], data.get("quantity"), data.get("occurred_on"),
                      data.get("unit_price"), data.get("note"))
    if data.get("dealer_id"):
        if m.type not in (MovementType.PURCHASE, MovementType.OPENING, MovementType.SUPPLIER_RETURN):
            raise AppError("VALIDATION_ERROR", "A dealer can only be set on purchases or returns to a dealer.", 422)
        from app.services import contacts_service

        m.dealer_id = contacts_service.get_dealer(db, int(data["dealer_id"])).id
    audit_service.log(db, user, "CREATE", "movement", m.id,
                      after={"label": design.label, "type": m.type.value, "qty": m.quantity})
    ev = data_version_service.bump(db, "movement", "create", m.id)
    db.commit()
    data_version_service.publish(ev)
    db.refresh(m)
    return {"movement": movement_out(m), "design": _design_brief(db, design)}


def record_batch(db: Session, user: User, items: list[dict]) -> dict:
    if not items:
        raise AppError("VALIDATION_ERROR", "No items", 422)
    created, touched = [], {}
    try:
        for idx, data in enumerate(items):
            try:
                design = _resolve_design(db, data.get("design_id"), data.get("label"))
                m = _add_movement(db, user, design, data["type"], data.get("quantity"), data.get("occurred_on"),
                                  data.get("unit_price"), data.get("note"))
            except AppError as e:
                e.details = {**e.details, "rows": [{"index": idx, "field": "quantity", "message": e.message}]}
                raise
            created.append(m)
            touched[design.id] = design
        audit_service.log(db, user, "CREATE", "movement_batch", None, after={"count": len(created)})
        ev = data_version_service.bump(db, "movement", "create_batch")
        db.commit()
    except Exception:
        db.rollback()
        raise
    data_version_service.publish(ev)
    return {"movements": [movement_out(m) for m in created],
            "designs": [_design_brief(db, d) for d in touched.values()]}


def void(db: Session, user: User, movement_id: int, reason: str | None) -> dict:
    m = db.get(StockMovement, movement_id)
    if not m:
        raise AppError("MOVEMENT_NOT_FOUND", "Entry not found", 404)
    if m.is_void:
        raise AppError("ALREADY_VOID", "This entry was already undone.", 409)
    design = m.design
    if m.bill_id:
        from app.services import billing_service

        live = [x for x in m.bill.items if not x.is_void]
        if len(live) > 1:
            raise AppError("PART_OF_BILL", f"This sale is on bill {m.bill.number} with {len(live)} designs. "
                                           "Cancel the whole bill instead.", 409, {"bill_id": m.bill_id})
        billing_service.void_bill(db, user, m.bill_id, reason, commit=False)
        ev = data_version_service.bump(db, "movement", "void", m.id)
        db.commit()
        data_version_service.publish(ev)
        db.refresh(m)
        return {"movement": movement_out(m), "design": _design_brief(db, design)}
    if m.type == MovementType.OPENING:
        others = db.query(StockMovement).filter(StockMovement.design_id == design.id, StockMovement.id != m.id,
                                                StockMovement.is_void.is_(False)).count()
        if others:
            raise AppError("CANNOT_VOID_OPENING", "Opening stock can only be undone before any other entry exists.", 409)
    if m.type in IN_TYPES:
        # removing an IN must not make stock negative now or after that date
        now_stock = stock_now(db, design.id)
        if now_stock - m.quantity < 0:
            raise AppError("INSUFFICIENT_STOCK",
                           f"Can't undo: {design.label} would go below zero (only {now_stock} in stock).", 409)
    m.is_void = True
    m.voided_at = now_utc()
    m.voided_by = user.id
    m.void_reason = reason
    audit_service.log(db, user, "VOID", "movement", m.id, after={"reason": reason})
    ev = data_version_service.bump(db, "movement", "void", m.id)
    db.commit()
    data_version_service.publish(ev)
    db.refresh(m)
    return {"movement": movement_out(m), "design": _design_brief(db, design)}


def list_movements(db: Session, *, design_id=None, label=None, category_id=None, types=None, date_from=None,
                   date_to=None, include_void=True, created_by=None, page=1, page_size=25, customer_id=None,
                   dealer_id=None, sort_by: str | None = None, sort_dir: str | None = None) -> dict:
    q = db.query(StockMovement).options(joinedload(StockMovement.design), joinedload(StockMovement.creator),
                                        joinedload(StockMovement.bill), joinedload(StockMovement.dealer))
    if design_id:
        q = q.filter(StockMovement.design_id == design_id)
    if label:
        q = q.join(Design, Design.id == StockMovement.design_id).filter(Design.label.contains(label.strip().upper()))
    if category_id:
        q = q.filter(StockMovement.design_id.in_(db.query(Design.id).filter(Design.category_id == category_id)))
    if types:
        q = q.filter(StockMovement.type.in_([MovementType(t) for t in types]))
    if date_from:
        q = q.filter(StockMovement.occurred_on >= date_from)
    if date_to:
        q = q.filter(StockMovement.occurred_on <= date_to)
    if not include_void:
        q = q.filter(StockMovement.is_void.is_(False))
    if created_by:
        q = q.filter(StockMovement.created_by == created_by)
    if dealer_id:
        q = q.filter(StockMovement.dealer_id == dealer_id)
    if customer_id:
        from app.models import Bill

        q = q.filter(StockMovement.bill_id.in_(db.query(Bill.id).filter(Bill.customer_id == customer_id)))
    total = q.count()
    page_size = max(1, min(int(page_size), 200))
    page = max(1, int(page))
    rows = (q.order_by(*_history_order(q, sort_by, sort_dir)).offset((page - 1) * page_size).limit(page_size).all())
    return {"items": [movement_out(m) for m in rows], "total": total, "page": page, "page_size": page_size}


def _history_order(q, sort_by: str | None, sort_dir: str | None):
    """Order for the History table: date, type, design, quantity, value (₹), party (customer / dealer), user."""
    from sqlalchemy import func as f_

    from app.models import Bill, Dealer

    desc = (sort_dir or "desc").lower() != "asc"
    col = {
        "occurred_on": StockMovement.occurred_on,
        "type": StockMovement.type,
        "quantity": StockMovement.quantity,
        "value": f_.coalesce(StockMovement.unit_price, 0) * StockMovement.quantity,
        "created_by": StockMovement.created_by,
    }.get(sort_by or "occurred_on")
    if sort_by == "party":
        col = f_.coalesce(
            q.session.query(Bill.customer_name).filter(Bill.id == StockMovement.bill_id).scalar_subquery(),
            q.session.query(Dealer.name).filter(Dealer.id == StockMovement.dealer_id).scalar_subquery(), "")
    if sort_by == "design":
        col = q.session.query(Design.label).filter(Design.id == StockMovement.design_id).scalar_subquery()
    if col is None:
        col = StockMovement.occurred_on
    return [col.desc() if desc else col.asc(), StockMovement.id.desc() if desc else StockMovement.id.asc()]


def today_entries(db: Session, user: User) -> dict:
    t = _today()
    rows = (db.query(StockMovement).options(joinedload(StockMovement.design), joinedload(StockMovement.creator))
            .filter(StockMovement.created_by == user.id, StockMovement.occurred_on == t)
            .order_by(StockMovement.id.desc()).limit(100).all())
    live = [m for m in rows if not m.is_void]
    sold = [m for m in live if m.type == MovementType.SALE]
    return {
        "entries": [movement_out(m) for m in rows],
        "totals": {
            "sold_units": sum(m.quantity for m in sold),
            "sold_value": float(sum((m.unit_price or 0) * m.quantity for m in sold)),
            "received_units": sum(m.quantity for m in live if m.type == MovementType.PURCHASE),
        },
    }

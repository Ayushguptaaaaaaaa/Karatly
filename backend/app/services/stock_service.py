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
    m = _add_movement(db, user, design, data["type"], data.get("quantity"), data.get("occurred_on"),
                      data.get("unit_price"), data.get("note"))
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
                   date_to=None, include_void=True, created_by=None, page=1, page_size=25) -> dict:
    q = db.query(StockMovement).options(joinedload(StockMovement.design), joinedload(StockMovement.creator))
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
    total = q.count()
    page_size = max(1, min(int(page_size), 200))
    page = max(1, int(page))
    rows = (q.order_by(StockMovement.occurred_on.desc(), StockMovement.id.desc())
            .offset((page - 1) * page_size).limit(page_size).all())
    return {"items": [movement_out(m) for m in rows], "total": total, "page": page, "page_size": page_size}


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

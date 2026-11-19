"""Purchase cost estimation: last cost × (1 + inflation%) × quantity."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Category, Design
from app.services import settings_service

TWO = Decimal("0.01")


def money(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(TWO, rounding=ROUND_HALF_UP)


def resolve_inflation(design: Design, category: Category | None, global_pct) -> Decimal:
    if design.inflation_pct_override is not None:
        return Decimal(str(design.inflation_pct_override))
    if category is not None and category.inflation_pct_override is not None:
        return Decimal(str(category.inflation_pct_override))
    return Decimal(str(global_pct))


def expected_unit_cost(last_cost, inflation_pct) -> Decimal:
    return money(Decimal(str(last_cost)) * (Decimal("1") + Decimal(str(inflation_pct)) / Decimal("100")))


def format_inr(value, decimals: int = 2) -> str:
    """Indian digit grouping: 12,34,567.00"""
    v = money(value)
    neg = v < 0
    v = abs(v)
    whole, frac = f"{v:.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    out = f"₹{whole}" + (f".{frac}" if decimals else "")
    return f"-{out}" if neg else out


def format_inr_compact(value) -> str:
    v = float(value or 0)
    if abs(v) >= 1e7:
        return f"₹{v / 1e7:.2f} Cr"
    if abs(v) >= 1e5:
        return f"₹{v / 1e5:.2f} L"
    return format_inr(v, decimals=0)


def line(last_cost, inflation_pct, qty: int) -> dict:
    unit = expected_unit_cost(last_cost, inflation_pct)
    total = money(unit * qty)
    infl = Decimal(str(inflation_pct)).normalize()
    return {
        "last_unit_cost": money(last_cost),
        "inflation_pct": money(inflation_pct),
        "expected_unit_cost": unit,
        "line_total": total,
        "formula_text": f"{format_inr(last_cost)} × (1 + {infl:f}%) = {format_inr(unit)} per piece × {qty} = {format_inr(total)}",
    }


def calculate_purchase_cost(db: Session, label: str, qty: int) -> dict:
    from app.services import metrics_service

    design = db.query(Design).filter(Design.label == label.strip().upper()).first()
    if not design:
        raise AppError("DESIGN_NOT_FOUND", f"No design with label {label}", 404)
    snap = metrics_service.snapshot(db)
    st = snap.states[design.id]
    infl = resolve_inflation(design, design.category, settings_service.get(db, "inflation_pct_global"))
    return {"label": design.label, "quantity": qty, **line(st.last_unit_cost, infl, qty)}

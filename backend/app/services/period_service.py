"""Month / quarter (Indian financial year by default) / custom period helpers and period stock."""
from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.clock import today as _today
from app.core.errors import AppError
from app.models import StockMovement
from app.models.enums import MovementType
from app.services import settings_service

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
ABBR = [m[:3] for m in MONTHS]


@dataclass
class Period:
    period_type: str
    start: date
    end: date
    label: str
    short_label: str

    @property
    def effective_end(self) -> date:
        return min(self.end, _today())

    @property
    def is_current(self) -> bool:
        return self.start <= _today() <= self.end

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


def _month(anchor: date) -> Period:
    start = anchor.replace(day=1)
    end = anchor.replace(day=calendar.monthrange(anchor.year, anchor.month)[1])
    return Period("month", start, end, f"{MONTHS[anchor.month - 1]} {anchor.year}", f"{ABBR[anchor.month - 1]} {anchor.year}")


def _quarter(anchor: date, system: str) -> Period:
    m, y = anchor.month, anchor.year
    if system == "FINANCIAL":
        fy_start_year = y if m >= 4 else y - 1
        q = ((m - 4) % 12) // 3 + 1
        start_month = 4 + (q - 1) * 3
        start_year = fy_start_year
        if start_month > 12:
            start_month -= 12
            start_year += 1
        fy = f"FY{fy_start_year}-{str(fy_start_year + 1)[-2:]}"
        label_q = f"Q{q} {fy}"
    else:
        q = (m - 1) // 3 + 1
        start_month, start_year = (q - 1) * 3 + 1, y
        label_q = f"Q{q} {y}"
    start = date(start_year, start_month, 1)
    end_month = start_month + 2
    end = date(start_year, end_month, calendar.monthrange(start_year, end_month)[1])
    span = f"{ABBR[start.month - 1]}–{ABBR[end.month - 1]} {end.year}"
    return Period("quarter", start, end, f"{label_q} ({span})", label_q)


def resolve(db: Session, period_type: str = "month", anchor: date | None = None,
            start: date | None = None, end: date | None = None) -> Period:
    period_type = (period_type or "month").lower()
    anchor = anchor or _today()
    if period_type == "month":
        return _month(anchor)
    if period_type == "quarter":
        return _quarter(anchor, settings_service.get(db, "quarter_system") or "FINANCIAL")
    if period_type == "custom":
        if not start or not end or end < start:
            raise AppError("INVALID_PERIOD", "Custom periods need a start and end date (end after start).", 422)
        lbl = f"{start.day} {ABBR[start.month - 1]} – {end.day} {ABBR[end.month - 1]} {end.year}"
        return Period("custom", start, end, lbl, lbl)
    raise AppError("INVALID_PERIOD", "period_type must be month, quarter or custom", 422)


def previous(db: Session, p: Period) -> Period:
    if p.period_type in ("month", "quarter"):
        return resolve(db, p.period_type, p.start - timedelta(days=1))
    length = p.days
    end = p.start - timedelta(days=1)
    return resolve(db, "custom", start=end - timedelta(days=length - 1), end=end)


def to_out(db: Session, p: Period) -> dict:
    prev = previous(db, p)
    return {
        "period_type": p.period_type,
        "start": p.start,
        "end": p.end,
        "effective_end": p.effective_end,
        "label": p.label,
        "short_label": p.short_label,
        "is_current": p.is_current,
        "previous": {"start": prev.start, "end": prev.end, "label": prev.label, "short_label": prev.short_label},
    }


def options(db: Session) -> dict:
    t = _today()
    months, quarters = [], []
    y, m = t.year, t.month
    for _ in range(24):
        p = _month(date(y, m, 1))
        months.append({"period_type": "month", "anchor": p.start, "label": p.label, "start": p.start, "end": p.end})
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    anchor = t
    for _ in range(8):
        p = resolve(db, "quarter", anchor)
        quarters.append({"period_type": "quarter", "anchor": p.start, "label": p.label, "start": p.start, "end": p.end})
        anchor = p.start - timedelta(days=1)
    return {"months": months, "quarters": quarters}


# --- period stock ------------------------------------------------------------

FIELDS = ["opening", "opening_added", "received", "sold", "customer_returns", "supplier_returns",
          "adjustments_net", "closing"]

TYPE_FIELD = {
    MovementType.OPENING: "opening_added",
    MovementType.PURCHASE: "received",
    MovementType.SALE: "sold",
    MovementType.CUSTOMER_RETURN: "customer_returns",
    MovementType.SUPPLIER_RETURN: "supplier_returns",
}


def period_rows(db: Session, p: Period, design_ids: list[int] | None = None) -> dict[int, dict]:
    """Per design: opening, movements by type within the period, closing, sales_value."""
    end = p.effective_end
    rows: dict[int, dict] = defaultdict(lambda: {**{f: 0 for f in FIELDS}, "sales_value": Decimal("0")})

    base = db.query(StockMovement).filter(StockMovement.is_void.is_(False))
    if design_ids is not None:
        base = base.filter(StockMovement.design_id.in_(design_ids))

    opening_q = (
        db.query(StockMovement.design_id, func.sum(StockMovement.signed_qty))
        .filter(StockMovement.is_void.is_(False), StockMovement.occurred_on < p.start)
        .group_by(StockMovement.design_id)
    )
    if design_ids is not None:
        opening_q = opening_q.filter(StockMovement.design_id.in_(design_ids))
    for did, s in opening_q.all():
        rows[did]["opening"] = int(s or 0)

    if end >= p.start:
        in_q = (
            db.query(
                StockMovement.design_id,
                StockMovement.type,
                func.sum(StockMovement.quantity),
                func.sum(StockMovement.quantity * func.coalesce(StockMovement.unit_price, 0)),
            )
            .filter(StockMovement.is_void.is_(False), StockMovement.occurred_on >= p.start,
                    StockMovement.occurred_on <= end)
            .group_by(StockMovement.design_id, StockMovement.type)
        )
        if design_ids is not None:
            in_q = in_q.filter(StockMovement.design_id.in_(design_ids))
        for did, mtype, qty, value in in_q.all():
            r = rows[did]
            qty = int(qty or 0)
            if mtype == MovementType.ADJUSTMENT_IN:
                r["adjustments_net"] += qty
            elif mtype == MovementType.ADJUSTMENT_OUT:
                r["adjustments_net"] -= qty
            else:
                r[TYPE_FIELD[mtype]] += qty
            if mtype == MovementType.SALE:
                r["sales_value"] += Decimal(str(value or 0))

    for r in rows.values():
        r["closing"] = (r["opening"] + r["opening_added"] + r["received"] + r["customer_returns"]
                        - r["sold"] - r["supplier_returns"] + r["adjustments_net"])
    return rows

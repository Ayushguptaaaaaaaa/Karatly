"""Per-design calculated state (stock, status, demand, velocity, costs) built with grouped queries.

`snapshot(db)` is the single source of per-design numbers used by lists, dashboard, alerts,
reorder, reports and the AI analysis pack.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload

from app.core.clock import today as _today
from app.models import Category, Design, StockMovement
from app.models.enums import Demand, MovementType, StockStatus
from app.services import settings_service


@dataclass
class DesignState:
    design_id: int
    category_id: int
    current_stock: int = 0
    first_movement_on: date | None = None
    last_sale_on: date | None = None
    sold_30d: int = 0
    sold_90d: int = 0
    sold_total: int = 0
    velocity_30d: float = 0.0
    days_since_last_sale: int | None = None
    last_unit_cost: Decimal = Decimal("0")
    status: StockStatus = StockStatus.OUT
    demand: Demand = Demand.NEW
    stock_value_cost: Decimal = Decimal("0")


@dataclass
class Snapshot:
    today: date
    designs: dict[int, Design]
    categories: dict[int, Category]
    states: dict[int, DesignState]
    dead_days: int
    data_sufficiency: str = "GOOD"
    extra: dict = field(default_factory=dict)

    def active_ids(self) -> list[int]:
        return [i for i, d in self.designs.items() if d.is_active]


def _q(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(Decimal("0.01"))


def snapshot(db: Session, include_inactive: bool = True) -> Snapshot:
    today = _today()
    dead_days = int(settings_service.get(db, "dead_stock_days") or 90)
    q = db.query(Design).options(joinedload(Design.category), joinedload(Design.subcategory))
    if not include_inactive:
        q = q.filter(Design.is_active.is_(True))
    designs = {d.id: d for d in q.all()}
    categories = {c.id: c for c in db.query(Category).all()}
    states = {i: DesignState(design_id=i, category_id=d.category_id) for i, d in designs.items()}

    d30 = today - timedelta(days=30)
    d90 = today - timedelta(days=90)
    is_sale = StockMovement.type == MovementType.SALE
    rows = (
        db.query(
            StockMovement.design_id,
            func.coalesce(func.sum(StockMovement.signed_qty), 0),
            func.min(StockMovement.occurred_on),
            func.max(case((is_sale, StockMovement.occurred_on), else_=None)),
            func.coalesce(func.sum(case((is_sale & (StockMovement.occurred_on >= d30), StockMovement.quantity), else_=0)), 0),
            func.coalesce(func.sum(case((is_sale & (StockMovement.occurred_on >= d90), StockMovement.quantity), else_=0)), 0),
            func.coalesce(func.sum(case((is_sale, StockMovement.quantity), else_=0)), 0),
        )
        .filter(StockMovement.is_void.is_(False))
        .group_by(StockMovement.design_id)
        .all()
    )
    for design_id, stock, first_on, last_sale, s30, s90, stot in rows:
        st = states.get(design_id)
        if not st:
            continue
        st.current_stock = int(stock)
        st.first_movement_on = first_on
        st.last_sale_on = last_sale
        st.sold_30d, st.sold_90d, st.sold_total = int(s30), int(s90), int(stot)

    # last unit cost: latest PURCHASE, else latest OPENING, else design.cost_price
    cost_rows = (
        db.query(StockMovement.design_id, StockMovement.type, StockMovement.unit_price)
        .filter(
            StockMovement.is_void.is_(False),
            StockMovement.type.in_([MovementType.PURCHASE, MovementType.OPENING]),
            StockMovement.unit_price.isnot(None),
        )
        .order_by(StockMovement.occurred_on, StockMovement.id)
        .all()
    )
    last_purchase: dict[int, Decimal] = {}
    last_opening: dict[int, Decimal] = {}
    for design_id, mtype, price in cost_rows:
        (last_purchase if mtype == MovementType.PURCHASE else last_opening)[design_id] = Decimal(price)

    for i, st in states.items():
        d = designs[i]
        st.last_unit_cost = _q(last_purchase.get(i) or last_opening.get(i) or d.cost_price)
        st.stock_value_cost = _q(st.last_unit_cost * st.current_stock)
        if st.first_movement_on:
            age = (today - st.first_movement_on).days
            window = min(90, max(7, age))
            st.velocity_30d = round(st.sold_90d / window * 30, 2)
            ref = st.last_sale_on or st.first_movement_on
            st.days_since_last_sale = (today - ref).days
        st.status = compute_status(st, d.min_stock, dead_days, today)

    _classify_demand(snap_states=states, designs=designs, today=today)
    snap = Snapshot(today=today, designs=designs, categories=categories, states=states, dead_days=dead_days)
    total_sales = sum(s.sold_total for s in states.values())
    firsts = [s.first_movement_on for s in states.values() if s.first_movement_on]
    months = ((today - min(firsts)).days / 30.4) if firsts else 0
    snap.data_sufficiency = "LOW" if (total_sales < 20 or months < 1) else ("LIMITED" if months < 3 else "GOOD")
    snap.extra["months_of_history"] = round(months, 1)
    snap.extra["total_sales"] = total_sales
    return snap


def compute_status(st: DesignState, min_stock: int, dead_days: int, today: date) -> StockStatus:
    if st.current_stock <= 0:
        return StockStatus.OUT
    if (
        st.first_movement_on is not None
        and (today - st.first_movement_on).days >= dead_days
        and st.days_since_last_sale is not None
        and st.days_since_last_sale >= dead_days
    ):
        return StockStatus.DEAD
    if st.current_stock <= min_stock:
        return StockStatus.LOW
    return StockStatus.IN


def _classify_demand(snap_states: dict[int, DesignState], designs: dict[int, Design], today: date) -> None:
    by_cat: dict[int, list[DesignState]] = defaultdict(list)
    all_moving: list[DesignState] = []
    for i, st in snap_states.items():
        if not designs[i].is_active:
            continue
        if st.velocity_30d > 0 and st.status != StockStatus.DEAD:
            by_cat[st.category_id].append(st)
            all_moving.append(st)

    def pct_rank(st: DesignState, group: list[DesignState]) -> float:
        vals = sorted(s.velocity_30d for s in group)
        below = sum(1 for v in vals if v < st.velocity_30d)
        equal = sum(1 for v in vals if v == st.velocity_30d)
        return (below + 0.5 * equal) / len(vals)

    for i, st in snap_states.items():
        if st.first_movement_on is None or (
            (today - st.first_movement_on).days < 14 and st.sold_total == 0
        ):
            st.demand = Demand.NEW
            continue
        if st.status == StockStatus.DEAD:
            st.demand = Demand.DEAD
            continue
        if st.status == StockStatus.OUT and st.sold_30d >= 3:
            st.demand = Demand.HIGH
            continue
        if st.velocity_30d == 0:
            st.demand = Demand.LOW
            continue
        group = by_cat.get(st.category_id, [])
        if len(group) < 5:
            group = all_moving
        if len(group) < 3:
            st.demand = Demand.STEADY
            continue
        r = pct_rank(st, group)
        st.demand = Demand.HIGH if r >= 0.8 else (Demand.LOW if r <= 0.2 else Demand.STEADY)


# --- sales aggregates -------------------------------------------------------

def sales_by_design(db: Session, start: date, end: date) -> dict[int, tuple[int, Decimal]]:
    rows = (
        db.query(
            StockMovement.design_id,
            func.sum(StockMovement.quantity),
            func.sum(StockMovement.quantity * func.coalesce(StockMovement.unit_price, 0)),
        )
        .filter(
            StockMovement.is_void.is_(False),
            StockMovement.type == MovementType.SALE,
            StockMovement.occurred_on >= start,
            StockMovement.occurred_on <= end,
        )
        .group_by(StockMovement.design_id)
        .all()
    )
    return {d: (int(q or 0), _q(v)) for d, q, v in rows}


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def month_starts(today: date, months: int) -> list[date]:
    out = []
    y, m = today.year, today.month
    for _ in range(months):
        out.append(date(y, m, 1))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))


MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def monthly_sales(db: Session, months: int = 12, category_id: int | None = None, by_category: bool = False):
    """Returns {key: {month_key: (units, value)}} where key is 'total' or category_id."""
    today = _today()
    starts = month_starts(today, months)
    start = starts[0]
    month_expr = func.strftime("%Y-%m", StockMovement.occurred_on)
    q = (
        db.query(
            month_expr,
            Design.category_id,
            func.sum(StockMovement.quantity),
            func.sum(StockMovement.quantity * func.coalesce(StockMovement.unit_price, 0)),
        )
        .join(Design, Design.id == StockMovement.design_id)
        .filter(
            StockMovement.is_void.is_(False),
            StockMovement.type == MovementType.SALE,
            StockMovement.occurred_on >= start,
        )
        .group_by(month_expr, Design.category_id)
    )
    if category_id:
        q = q.filter(Design.category_id == category_id)
    data: dict = defaultdict(lambda: defaultdict(lambda: [0, Decimal("0")]))
    for mk, cat_id, units, value in q.all():
        key = cat_id if by_category else "total"
        data[key][mk][0] += int(units or 0)
        data[key][mk][1] += _q(value)
    return starts, data


def series_points(starts: list[date], per_month: dict) -> list[dict]:
    pts = []
    for s in starts:
        mk = month_key(s)
        units, value = per_month.get(mk, [0, Decimal("0")]) if per_month else (0, Decimal("0"))
        pts.append({"month": mk, "label": MONTH_ABBR[s.month - 1], "units": int(units), "value": float(_q(value))})
    return pts

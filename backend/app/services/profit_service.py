"""Net revenue and net profit per design / subcategory / category for any period.

Definitions (shown in the UI as well):
- gross sales      = Σ sale qty × sale price
- returns value    = customer-returned qty × the design's average sale price in the period
                     (falls back to its selling price when it had no sales in the period)
- net revenue      = gross sales − returns value
- net units        = sold − customer returns
- cost of goods    = net units × average purchase cost (weighted over OPENING + PURCHASE entries)
- net profit       = net revenue − cost of goods
- margin %         = net profit ÷ net revenue × 100
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Category, Design, StockMovement
from app.models.enums import MovementType
from app.services import costing_service, metrics_service, period_service
from app.services.serializers import photo_url

money = costing_service.money
ZERO = Decimal("0")
NUM_FIELDS = ["units_sold", "units_returned", "net_units", "gross_sales", "returns_value", "net_revenue", "cogs",
              "net_profit"]


def avg_cost_map(db: Session, design_ids: list[int] | None = None) -> dict[int, Decimal]:
    """Weighted average purchase cost per design (OPENING + PURCHASE with a price), else the design's cost price."""
    q = (db.query(StockMovement.design_id, func.sum(StockMovement.quantity),
                  func.sum(StockMovement.quantity * StockMovement.unit_price))
         .filter(StockMovement.is_void.is_(False), StockMovement.unit_price.isnot(None),
                 StockMovement.type.in_([MovementType.OPENING, MovementType.PURCHASE]))
         .group_by(StockMovement.design_id))
    if design_ids is not None:
        q = q.filter(StockMovement.design_id.in_(design_ids))
    out = {did: Decimal(str(v)) / Decimal(qty) for did, qty, v in q.all() if qty}
    dq = db.query(Design.id, Design.cost_price)
    if design_ids is not None:
        dq = dq.filter(Design.id.in_(design_ids))
    for did, cost in dq.all():
        out.setdefault(did, Decimal(str(cost or 0)))
    return out


def design_profit(db: Session, start: date, end: date, design_ids: list[int] | None = None) -> dict[int, dict]:
    """Per-design profit numbers for [start, end] (only designs with sales or returns)."""
    q = (db.query(StockMovement.design_id, StockMovement.type, func.sum(StockMovement.quantity),
                  func.sum(StockMovement.quantity * func.coalesce(StockMovement.unit_price, 0)))
         .filter(StockMovement.is_void.is_(False), StockMovement.occurred_on >= start, StockMovement.occurred_on <= end,
                 StockMovement.type.in_([MovementType.SALE, MovementType.CUSTOMER_RETURN]))
         .group_by(StockMovement.design_id, StockMovement.type))
    if design_ids is not None:
        q = q.filter(StockMovement.design_id.in_(design_ids))
    raw: dict[int, dict] = defaultdict(lambda: {"sold": 0, "sales": ZERO, "returned": 0})
    for did, mtype, qty, value in q.all():
        r = raw[did]
        if mtype == MovementType.SALE:
            r["sold"] += int(qty or 0)
            r["sales"] += Decimal(str(value or 0))
        else:
            r["returned"] += int(qty or 0)
    if not raw:
        return {}
    ids = list(raw.keys())
    costs = avg_cost_map(db, ids)
    sell = {did: Decimal(str(p or 0)) for did, p in db.query(Design.id, Design.selling_price).filter(Design.id.in_(ids))}
    out = {}
    for did, r in raw.items():
        avg_sale = (r["sales"] / r["sold"]) if r["sold"] else sell.get(did, ZERO)
        returns_value = avg_sale * r["returned"]
        net_units = r["sold"] - r["returned"]
        net_revenue = r["sales"] - returns_value
        cogs = costs.get(did, ZERO) * net_units
        out[did] = {
            "units_sold": r["sold"], "units_returned": r["returned"], "net_units": net_units,
            "gross_sales": money(r["sales"]), "returns_value": money(returns_value),
            "net_revenue": money(net_revenue), "avg_unit_cost": money(costs.get(did, ZERO)),
            "cogs": money(cogs), "net_profit": money(net_revenue - cogs),
        }
    return out


def margin(net_profit, net_revenue) -> float | None:
    nr = Decimal(str(net_revenue or 0))
    return round(float(Decimal(str(net_profit or 0)) / nr * 100), 1) if nr else None


def _empty() -> dict:
    return {f: (0 if f in ("units_sold", "units_returned", "net_units") else ZERO) for f in NUM_FIELDS}


def _add(acc: dict, r: dict) -> None:
    for f in NUM_FIELDS:
        acc[f] += r[f]


def _finish(row: dict) -> dict:
    for f in NUM_FIELDS:
        if isinstance(row[f], Decimal):
            row[f] = float(money(row[f]))
    row["margin_pct"] = margin(row["net_profit"], row["net_revenue"])
    return row


def profitability(db: Session, p: period_service.Period, group_by: str = "category", category_id: int | None = None,
                  subcategory_id: int | None = None, limit: int = 500) -> dict:
    snap = metrics_service.snapshot(db)
    per_design = design_profit(db, p.start, p.effective_end)
    designs = [d for d in snap.designs.values()
               if (not category_id or d.category_id == category_id)
               and (not subcategory_id or d.subcategory_id == subcategory_id)]
    groups: dict[str, dict] = {}
    totals = _empty()

    for d in designs:
        r = per_design.get(d.id)
        if group_by == "design":
            if not r:
                continue
            key, row = str(d.id), {"key": str(d.id), "name": d.label, "label": d.label, "design_name": d.name,
                                   "design_id": d.id, "category": d.category.name,
                                   "subcategory": d.subcategory.name if d.subcategory else None,
                                   "photo_url": photo_url(d), "current_stock": snap.states[d.id].current_stock,
                                   "avg_unit_cost": float(r["avg_unit_cost"])}
        elif group_by == "subcategory":
            sid = d.subcategory_id or 0
            key = f"{d.category_id}:{sid}"
            row = {"key": key, "name": d.subcategory.name if d.subcategory else "(No subcategory)",
                   "category": d.category.name, "category_id": d.category_id, "subcategory_id": d.subcategory_id}
        else:
            key, row = str(d.category_id), {"key": str(d.category_id), "name": d.category.name,
                                            "category_id": d.category_id, "icon": d.category.icon}
        g = groups.setdefault(key, {**row, **_empty(), "designs": 0})
        g["designs"] += 1
        if r:
            _add(g, r)
            _add(totals, r)

    if group_by == "category":  # show empty categories too
        for c in db.query(Category).filter(Category.is_active.is_(True)):
            if (not category_id or c.id == category_id) and str(c.id) not in groups:
                groups[str(c.id)] = {"key": str(c.id), "name": c.name, "category_id": c.id, "icon": c.icon,
                                     **_empty(), "designs": 0}

    rows = sorted((_finish(g) for g in groups.values()), key=lambda r: (-r["net_profit"], -r["net_revenue"], r["name"]))
    return {"period": period_service.to_out(db, p), "group_by": group_by, "rows": rows[:limit],
            "total_rows": len(rows), "totals": _finish(totals)}


def totals_for(db: Session, start: date, end: date) -> dict:
    t = _empty()
    for r in design_profit(db, start, end).values():
        _add(t, r)
    return _finish(t)

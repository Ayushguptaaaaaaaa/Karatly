"""Rule-based reorder baseline (no AI).

Quantity rules (built to be sensible for a small retailer and a large showroom alike):
1. Monthly sales rate = pieces sold per 30 days over the last 90 days. Designs with less than 30 days of
   history use the pieces actually sold so far (no extrapolation from a day or two of sales).
2. Target stock = rate × cover months + minimum stock.
3. Cap: never restock above `max_stock_multiple` × the most stock this design has ever held
   (a design you usually keep 10 of will not get an order for 100).
4. Quantity = target − stock on hand.
5. Optional monthly purchase budget: high-priority lines are funded first, then medium, then low;
   lines that don't fit are reduced or skipped (see `fit_to_budget`).
"""
from __future__ import annotations

import math
from collections import defaultdict
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import StockMovement
from app.models.enums import Demand, Priority, StockStatus
from app.services import costing_service, metrics_service, settings_service
from app.services.serializers import photo_url

PRIO_ORDER = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}


def peak_stock_map(db: Session) -> dict[int, int]:
    """Highest stock level each design has ever held (running total over its non-void movements)."""
    rows = (db.query(StockMovement.design_id, StockMovement.signed_qty)
            .filter(StockMovement.is_void.is_(False))
            .order_by(StockMovement.design_id, StockMovement.occurred_on, StockMovement.id).all())
    peak: dict[int, int] = defaultdict(int)
    running: dict[int, int] = defaultdict(int)
    for did, q in rows:
        running[did] += int(q)
        if running[did] > peak[did]:
            peak[did] = running[did]
    return peak


def baseline(db: Session, category_id: int | None = None, snap: metrics_service.Snapshot | None = None) -> dict:
    snap = snap or metrics_service.snapshot(db)
    cover = float(settings_service.get(db, "reorder_cover_months") or 1.5)
    multiple = float(settings_service.get(db, "max_stock_multiple") or 1.5)
    infl_global = settings_service.get(db, "inflation_pct_global")
    peaks = peak_stock_map(db)
    items = []
    for d in snap.designs.values():
        if not d.is_active or (category_id and d.category_id != category_id):
            continue
        st = snap.states[d.id]
        if st.status not in (StockStatus.OUT, StockStatus.LOW):
            continue
        history_days = (snap.today - st.first_movement_on).days if st.first_movement_on else 0
        rate = st.velocity_30d
        wanted = math.ceil(rate * cover) + d.min_stock
        usual = max(peaks.get(d.id, 0), d.min_stock)
        cap = max(d.min_stock + 1, math.ceil(usual * multiple))
        target = min(wanted, cap)
        qty = max(target - st.current_stock, 0)
        if qty == 0 and st.status == StockStatus.OUT:
            qty = max(d.min_stock, 1)
        if qty == 0:
            continue
        if st.demand == Demand.HIGH or (st.status == StockStatus.OUT and st.demand in (Demand.HIGH, Demand.STEADY)):
            prio = Priority.HIGH
        elif st.status == StockStatus.OUT or st.demand == Demand.STEADY:
            prio = Priority.MEDIUM
        else:
            prio = Priority.LOW
        status_txt = "Out of stock" if st.status == StockStatus.OUT else f"Low stock ({st.current_stock} left)"
        demand_txt = {Demand.HIGH: "high demand", Demand.STEADY: "steady demand", Demand.LOW: "low demand",
                      Demand.NEW: "new design", Demand.DEAD: "not selling"}[st.demand]
        when = "today" if history_days == 0 else ("in its first day" if history_days == 1
                                                   else f"in its first {history_days} days")
        pace = f"sold {st.sold_total} {when}" if history_days < 30 else f"sells about {rate:g}/month"
        reason = f"{status_txt}; {demand_txt}, {pace}. Target {cover:g} months cover + min {d.min_stock}"
        reason += (f", capped at {cap} ({multiple:g}× your usual stock of {usual})." if wanted > cap
                   else f" = {target} pieces.")
        infl = costing_service.resolve_inflation(d, d.category, infl_global)
        cost = costing_service.line(st.last_unit_cost, infl, qty)
        items.append({
            "design": {"id": d.id, "label": d.label, "name": d.name, "photo_url": photo_url(d),
                       "category_name": d.category.name, "category_id": d.category_id},
            "current_stock": st.current_stock,
            "min_stock": d.min_stock,
            "usual_stock": usual,
            "max_qty": max(cap - st.current_stock, qty),
            "status": st.status.value,
            "demand_class": st.demand.value,
            "velocity_30d": st.velocity_30d,
            "suggested_qty": qty,
            "priority": prio.value,
            "reason": reason,
            **cost,
        })
    items.sort(key=lambda x: (PRIO_ORDER[Priority(x["priority"])], -float(x["line_total"])))
    by_cat: dict[str, float] = {}
    for it in items:
        by_cat[it["design"]["category_name"]] = by_cat.get(it["design"]["category_name"], 0) + float(it["line_total"])
    return {
        "items": items,
        "total_estimated": costing_service.money(sum(float(i["line_total"]) for i in items)),
        "by_category": [{"category": k, "amount": round(v, 2)} for k, v in sorted(by_cat.items(), key=lambda x: -x[1])],
        "budget": float(settings_service.get(db, "monthly_purchase_budget") or 0),
    }


def fit_to_budget(lines: list[dict], budget: float, qty_key: str = "qty", cost_key: str = "unit_cost",
                  prio_key: str = "priority") -> tuple[list[dict], dict]:
    """Fund lines in priority order (HIGH → MEDIUM → LOW, larger value first within a priority) until the
    budget runs out. The line that crosses the budget is reduced to what fits; the rest are skipped.
    Each line gets `fitted_qty`. Returns (lines, summary)."""
    if not budget or budget <= 0:
        for ln in lines:
            ln["fitted_qty"] = ln[qty_key]
        return lines, {"applied": False}
    order = sorted(range(len(lines)), key=lambda i: (PRIO_ORDER[Priority(lines[i][prio_key])],
                                                     -float(lines[i][cost_key]) * lines[i][qty_key]))
    remaining = Decimal(str(budget))
    reduced = skipped = 0
    for i in order:
        ln = lines[i]
        unit = Decimal(str(ln[cost_key])) or Decimal("1")
        want = int(ln[qty_key])
        can = int(remaining // unit) if unit > 0 else want
        got = max(0, min(want, can))
        ln["fitted_qty"] = got
        remaining -= unit * got
        if got == 0:
            skipped += 1
        elif got < want:
            reduced += 1
    total = sum(Decimal(str(ln[cost_key])) * ln["fitted_qty"] for ln in lines)
    before = sum(Decimal(str(ln[cost_key])) * int(ln[qty_key]) for ln in lines)
    return lines, {"applied": True, "budget": budget, "reduced": reduced, "skipped": skipped,
                   "total_after": float(costing_service.money(total)),
                   "total_before": float(costing_service.money(before))}

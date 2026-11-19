"""Rule-based reorder baseline (no AI)."""
from __future__ import annotations

import math

from sqlalchemy.orm import Session

from app.models.enums import Demand, Priority, StockStatus
from app.services import costing_service, metrics_service, settings_service
from app.services.serializers import photo_url

PRIO_ORDER = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}


def baseline(db: Session, category_id: int | None = None, snap: metrics_service.Snapshot | None = None) -> dict:
    snap = snap or metrics_service.snapshot(db)
    cover = float(settings_service.get(db, "reorder_cover_months") or 1.5)
    infl_global = settings_service.get(db, "inflation_pct_global")
    items = []
    for d in snap.designs.values():
        if not d.is_active or (category_id and d.category_id != category_id):
            continue
        st = snap.states[d.id]
        if st.status not in (StockStatus.OUT, StockStatus.LOW):
            continue
        target = math.ceil(st.velocity_30d * cover) + d.min_stock
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
        reason = (f"{status_txt}. Sold {st.sold_30d} in last 30 days ({demand_txt}). "
                  f"Target {cover:g} months cover + min {d.min_stock}.")
        infl = costing_service.resolve_inflation(d, d.category, infl_global)
        cost = costing_service.line(st.last_unit_cost, infl, qty)
        items.append({
            "design": {"id": d.id, "label": d.label, "name": d.name, "photo_url": photo_url(d),
                       "category_name": d.category.name},
            "current_stock": st.current_stock,
            "min_stock": d.min_stock,
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
    }

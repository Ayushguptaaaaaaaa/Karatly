"""Compact, exact facts handed to the AI (and used for rule-based fallbacks)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.clock import today as _today
from app.models import Category
from app.models.enums import Demand, StockStatus
from app.services import (
    anomaly_service,
    costing_service,
    dashboard_service,
    metrics_service,
    period_service,
    reorder_service,
    settings_service,
)


def upcoming_season(today: date) -> str:
    m = today.month
    if m in (8, 9):
        return "Dhanteras and Diwali in Oct–Nov: the busiest gold-buying season is coming."
    if m in (10, 11):
        return "Festive season (Dhanteras/Diwali) now, wedding season (Nov–Feb) next."
    if m in (12, 1, 2):
        return "Wedding season (Nov–Feb): necklaces, bangles and sets usually sell more."
    if m == 3:
        return "Akshaya Tritiya in Apr–May is coming: a big gold-buying day."
    if m in (4, 5):
        return "Akshaya Tritiya / summer wedding season."
    return "Monsoon months (Jun–Aug) are usually slower; festive season starts Aug–Sep."


def build_pack(db: Session, p: period_service.Period) -> dict:
    snap = metrics_service.snapshot(db)
    t = _today()
    prev = period_service.previous(db, p)
    sales_p = metrics_service.sales_by_design(db, p.start, p.effective_end)
    sales_prev = metrics_service.sales_by_design(db, prev.start, prev.effective_end)
    overview = dashboard_service.overview(db, p)
    kpis = {k: (float(v) if isinstance(v, Decimal) else v) for k, v in overview["kpis"].items()}

    from app.services import profit_service

    prof = profit_service.design_profit(db, p.start, p.effective_end)
    cats = db.query(Category).filter(Category.is_active.is_(True)).order_by(Category.sort_order).all()
    cat_rows = []
    for c in cats:
        mine = [d for d in snap.designs.values() if d.category_id == c.id and d.is_active]
        sp = sum(sales_p.get(d.id, (0, 0))[0] for d in mine)
        spp = sum(sales_prev.get(d.id, (0, 0))[0] for d in mine)
        sv = sum(float(sales_p.get(d.id, (0, 0))[1]) for d in mine)
        cat_rows.append({
            "name": c.name, "designs": len(mine),
            "pieces": sum(snap.states[d.id].current_stock for d in mine),
            "stock_value_cost": round(float(sum((snap.states[d.id].stock_value_cost for d in mine), Decimal("0"))), 2),
            "sold_period": sp, "sold_prev_period": spp, "sales_value_period": round(sv, 2),
            "change_pct": round((sp - spp) / spp * 100, 1) if spp else None,
            "net_revenue_period": round(sum(float(prof[d.id]["net_revenue"]) for d in mine if d.id in prof), 2),
            "net_profit_period": round(sum(float(prof[d.id]["net_profit"]) for d in mine if d.id in prof), 2),
        })

    starts, monthly = metrics_service.monthly_sales(db, 12, by_category=True)
    by_cat_name = {c.id: c.name for c in cats}
    monthly_by_cat = {}
    for cid, per in monthly.items():
        if cid in by_cat_name:
            monthly_by_cat[by_cat_name[cid]] = [[pt["month"], pt["units"], pt["value"]]
                                                for pt in metrics_service.series_points(starts, per)]

    def design_row(d):
        st = snap.states[d.id]
        return {
            "label": d.label, "name": d.name, "category": d.category.name,
            "subcategory": d.subcategory.name if d.subcategory else None,
            "stock": st.current_stock, "min_stock": d.min_stock, "status": st.status.value,
            "demand": st.demand.value, "sold_30d": st.sold_30d, "sold_period": sales_p.get(d.id, (0, 0))[0],
            "sold_prev_period": sales_prev.get(d.id, (0, 0))[0], "velocity_30d": st.velocity_30d,
            "days_since_last_sale": st.days_since_last_sale, "last_cost": float(st.last_unit_cost),
            "selling_price": float(d.selling_price), "value_tied_up": float(st.stock_value_cost),
        }

    active = [d for d in snap.designs.values() if d.is_active]
    buckets = [
        [d for d in active if snap.states[d.id].status == StockStatus.OUT],
        [d for d in active if snap.states[d.id].status == StockStatus.LOW],
        sorted([d for d in active if snap.states[d.id].demand == Demand.HIGH],
               key=lambda d: -snap.states[d.id].velocity_30d),
        sorted([d for d in active if snap.states[d.id].status == StockStatus.DEAD],
               key=lambda d: -snap.states[d.id].stock_value_cost),
        sorted([d for d in active if snap.states[d.id].demand == Demand.LOW],
               key=lambda d: snap.states[d.id].velocity_30d),
    ]
    picked, seen = [], set()
    for b in buckets:
        for d in b:
            if d.id not in seen and len(picked) < 60:
                picked.append(d)
                seen.add(d.id)

    base = reorder_service.baseline(db, snap=snap)
    demand_counts = {k.value: 0 for k in Demand}
    for d in active:
        demand_counts[snap.states[d.id].demand.value] += 1

    settings = settings_service.get_all(db)
    return {
        "shop": {"name": settings["shop_name"], "currency": "INR", "today": str(t),
                 "quarter_system": settings["quarter_system"]},
        "period": {"label": p.label, "start": str(p.start), "end": str(p.end), "is_current": p.is_current,
                   "previous_label": prev.label},
        "data_sufficiency": {"level": snap.data_sufficiency, "months_of_history": snap.extra["months_of_history"],
                             "total_sales": snap.extra["total_sales"], "designs": len(active)},
        "kpis": kpis,
        "categories": cat_rows,
        "monthly_sales_by_category": monthly_by_cat,
        "designs_of_interest": [design_row(d) for d in picked],
        "demand_counts": demand_counts,
        "reorder_baseline": [
            {"label": i["design"]["label"], "category": i["design"]["category_name"], "stock": i["current_stock"],
             "status": i["status"], "demand": i["demand_class"], "suggested_qty": i["suggested_qty"],
             "priority": i["priority"], "expected_unit_cost": float(i["expected_unit_cost"]),
             "line_total": float(i["line_total"]), "reason": i["reason"]} for i in base["items"][:40]],
        "reorder_total": float(base["total_estimated"]),
        "anomaly_candidates": anomaly_service.candidates(db, snap=snap),
        "upcoming_season": upcoming_season(t),
        "settings": {k: settings[k] for k in ("inflation_pct_global", "dead_stock_days", "reorder_cover_months",
                                               "default_min_stock")},
        "_facts": {
            "sales_trend_by_category": [
                {"name": name, "points": [{"month": m, "units": u, "value": v} for m, u, v in pts]}
                for name, pts in monthly_by_cat.items()],
            "kpis": kpis,
            "demand_counts": demand_counts,
            "stock_health": overview["stock_health"],
            "inr_total_reorder": costing_service.format_inr_compact(base["total_estimated"]),
        },
    }

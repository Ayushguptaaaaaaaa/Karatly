"""Dashboard overview (one call) + rule-based instant insights."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.clock import today as _today
from app.models import Category, InsightRun, PurchasePlan, StockMovement
from app.models.enums import Demand, MovementType, PlanSource, PlanStatus, RunStatus, StockStatus
from app.services import costing_service, data_version_service, metrics_service, period_service, reorder_service
from app.services.serializers import movement_out, photo_url

money = costing_service.money


def _pct(a: float, b: float) -> float | None:
    if not b:
        return None
    return round((a - b) / b * 100, 1)


def _comparable_prev(db: Session, p: period_service.Period) -> tuple[date, date, date, date]:
    """Current window and the same number of days in the previous period."""
    prev = period_service.previous(db, p)
    cur_end = p.effective_end
    span = (cur_end - p.start).days
    prev_end = min(prev.start + timedelta(days=span), prev.end)
    return p.start, cur_end, prev.start, prev_end


def stock_value_series(db: Session, snap: metrics_service.Snapshot, starts: list[date]) -> list[float]:
    month_expr = func.strftime("%Y-%m", StockMovement.occurred_on)
    rows = (db.query(StockMovement.design_id, month_expr, func.sum(StockMovement.signed_qty))
            .filter(StockMovement.is_void.is_(False)).group_by(StockMovement.design_id, month_expr).all())
    per_design: dict[int, dict[str, int]] = defaultdict(dict)
    for did, mk, s in rows:
        per_design[did][mk] = int(s or 0)
    out = []
    for s in starts:
        mk = metrics_service.month_key(s)
        total = Decimal("0")
        for did, months in per_design.items():
            st = snap.states.get(did)
            if not st:
                continue
            qty = sum(v for k, v in months.items() if k <= mk)
            total += st.last_unit_cost * max(qty, 0)
        out.append(float(money(total)))
    return out


def latest_run(db: Session) -> InsightRun | None:
    return (db.query(InsightRun).filter(InsightRun.status.in_([RunStatus.COMPLETE, RunStatus.PARTIAL]))
            .order_by(InsightRun.id.desc()).first())


def overview(db: Session, p: period_service.Period) -> dict:
    snap = metrics_service.snapshot(db)
    t = _today()
    active = [d for d in snap.designs.values() if d.is_active]
    states = [snap.states[d.id] for d in active]

    cs, ce, ps, pe = _comparable_prev(db, p)
    cur_sales = metrics_service.sales_by_design(db, cs, ce)
    prev_sales = metrics_service.sales_by_design(db, ps, pe)
    full_sales = metrics_service.sales_by_design(db, p.start, p.effective_end)
    sales_units = sum(q for q, _ in full_sales.values())
    sales_value = sum((v for _, v in full_sales.values()), Decimal("0"))
    cur_v = float(sum((v for _, v in cur_sales.values()), Decimal("0")))
    prev_v = float(sum((v for _, v in prev_sales.values()), Decimal("0")))

    health = {s.value: 0 for s in StockStatus}
    for st in states:
        health[st.status.value] += 1
    dead = [st for st in states if st.status == StockStatus.DEAD]
    kpis = {
        "total_designs": len(active),
        "total_pieces": sum(st.current_stock for st in states),
        "stock_value_cost": money(sum((st.stock_value_cost for st in states), Decimal("0"))),
        "stock_value_selling": money(sum((Decimal(d.selling_price) * snap.states[d.id].current_stock for d in active),
                                         Decimal("0"))),
        "sales_units": sales_units,
        "sales_value": money(sales_value),
        "sales_change_pct": _pct(cur_v, prev_v) if cur_v and prev_v else None,
        "out_of_stock": health["OUT"],
        "low_stock": health["LOW"],
        "dead_stock": health["DEAD"],
        "dead_stock_value": money(sum((st.stock_value_cost for st in dead), Decimal("0"))),
        "needs_attention": health["OUT"] + health["LOW"],
    }

    starts6, monthly = metrics_service.monthly_sales(db, 6)
    trend = metrics_service.series_points(starts6, monthly.get("total", {}))
    sparks = {
        "sales_value": [pt["value"] for pt in trend],
        "sales_units": [pt["units"] for pt in trend],
        "stock_value_cost": stock_value_series(db, snap, starts6) if active else [0.0] * 6,
    }

    cats = {c.id: c for c in db.query(Category).filter(Category.is_active.is_(True)).order_by(Category.sort_order)}
    breakdown = []
    total_sales_val = float(sales_value) or 0
    for cid, c in cats.items():
        mine = [d for d in active if d.category_id == cid]
        sold = sum(full_sales.get(d.id, (0, 0))[0] for d in mine)
        sval = sum(float(full_sales.get(d.id, (0, Decimal("0")))[1]) for d in mine)
        breakdown.append({
            "category_id": cid, "name": c.name, "icon": c.icon,
            "pieces": sum(snap.states[d.id].current_stock for d in mine),
            "stock_value_cost": float(sum((snap.states[d.id].stock_value_cost for d in mine), Decimal("0"))),
            "sold_units": sold, "sales_value": round(sval, 2),
            "share_pct": round(sval / total_sales_val * 100, 1) if total_sales_val else 0.0,
            "design_count": len(mine),
        })

    top = sorted(((did, q, v) for did, (q, v) in full_sales.items() if did in snap.designs),
                 key=lambda x: (-x[1], -x[2]))[:5]
    top_sellers = [{"design_id": did, "label": snap.designs[did].label, "name": snap.designs[did].name,
                    "photo_url": photo_url(snap.designs[did]), "category_name": snap.designs[did].category.name,
                    "sold_units": q, "sales_value": float(v), "current_stock": snap.states[did].current_stock}
                   for did, q, v in top]

    alert_rows = [d for d in active if snap.states[d.id].status in (StockStatus.OUT, StockStatus.LOW)]
    alert_rows.sort(key=lambda d: (snap.states[d.id].status != StockStatus.OUT,
                                   snap.states[d.id].demand != Demand.HIGH, d.label))
    alerts = [_alert(d, snap) for d in alert_rows[:8]]

    run = latest_run(db)
    dv = data_version_service.current(db)
    latest_ai = None
    if run:
        rep = run.report or {}
        conclusion = rep.get("conclusion") or ""
        latest_ai = {"run_id": run.id, "created_at": run.created_at, "period_label": run.period_label,
                     "headline": rep.get("headline") or "Insights ready",
                     "conclusion_short": conclusion[:220] + ("…" if len(conclusion) > 220 else ""),
                     "is_stale": dv > run.data_version, "changes_since": max(dv - run.data_version, 0),
                     "status": run.status.value}

    recent = (db.query(StockMovement).options(joinedload(StockMovement.design), joinedload(StockMovement.creator))
              .order_by(StockMovement.id.desc()).limit(10).all())
    pending = (db.query(PurchasePlan).filter(
        (PurchasePlan.status == PlanStatus.SUBMITTED)
        | ((PurchasePlan.status == PlanStatus.DRAFT) & (PurchasePlan.source == PlanSource.AI))).count())

    has_cat = bool(cats)
    has_designs = bool(active)
    has_opening = db.query(StockMovement.id).filter(StockMovement.is_void.is_(False)).first() is not None
    has_sale = db.query(StockMovement.id).filter(StockMovement.type == MovementType.SALE,
                                                 StockMovement.is_void.is_(False)).first() is not None
    has_ins = run is not None
    steps = [has_cat, has_designs, has_opening, has_sale, has_ins]

    ctx = {"snap": snap, "kpis": kpis, "cur_v": cur_v, "prev_v": prev_v, "breakdown": breakdown, "p": p,
           "has_cat": has_cat, "has_designs": has_designs, "has_sale": has_sale, "cats": cats}
    return {
        "period": period_service.to_out(db, p),
        "data_version": dv,
        "setup": {"has_category": has_cat, "has_designs": has_designs, "has_opening_stock": has_opening,
                  "has_sale": has_sale, "has_insights": has_ins, "completed_steps": sum(steps), "total_steps": 5},
        "kpis": kpis,
        "kpi_sparklines": sparks,
        "stock_health": health,
        "sales_trend": trend,
        "category_breakdown": breakdown,
        "top_sellers": top_sellers,
        "alerts": alerts,
        "instant_insights": instant_insights(db, ctx),
        "latest_ai": latest_ai,
        "recent_activity": [movement_out(m) for m in recent],
        "pending_approvals": pending,
        "today": t,
    }


def _alert(d, snap) -> dict:
    st = snap.states[d.id]
    return {"design_id": d.id, "label": d.label, "name": d.name, "photo_url": photo_url(d),
            "category_name": d.category.name, "status": st.status.value, "current_stock": st.current_stock,
            "min_stock": d.min_stock, "demand_class": st.demand.value, "sold_last_30d": st.sold_30d,
            "days_since_last_sale": st.days_since_last_sale, "value_tied_up": float(st.stock_value_cost),
            "selling_price": float(d.selling_price), "last_unit_cost": float(st.last_unit_cost)}


def alerts(db: Session, statuses: list[str] | None, category_id: int | None = None) -> list[dict]:
    snap = metrics_service.snapshot(db)
    statuses = statuses or ["OUT", "LOW", "DEAD"]
    rows = [d for d in snap.designs.values() if d.is_active and snap.states[d.id].status.value in statuses
            and (not category_id or d.category_id == category_id)]
    order = {"OUT": 0, "LOW": 1, "DEAD": 2}
    rows.sort(key=lambda d: (order[snap.states[d.id].status.value], snap.states[d.id].demand != Demand.HIGH, d.label))
    return [_alert(d, snap) for d in rows]


def _labels_text(labels: list[str], n_total: int) -> str:
    shown = ", ".join(labels[:3])
    return shown + (f" and {n_total - 3} more" if n_total > 3 else "")


def instant_insights(db: Session, ctx: dict) -> list[dict]:
    snap, kpis = ctx["snap"], ctx["kpis"]
    items: list[dict] = []
    sev_rank = {"critical": 0, "warning": 1, "info": 2, "success": 3}
    if not ctx["has_cat"]:
        items.append({"id": "setup_category", "severity": "info", "icon": "category-plus",
                      "title": "Add your first category", "detail": "Start with Earrings, Necklaces, Bangles…",
                      "action": {"label": "Add category", "route": "/app/inventory"}})
    elif not ctx["has_designs"]:
        first = next(iter(ctx["cats"].values()))
        items.append({"id": "setup_designs", "severity": "info", "icon": "diamond",
                      "title": f"Add designs to {first.name}", "detail": "Enter how many designs and their labels.",
                      "action": {"label": "Add designs", "route": f"/app/inventory/{first.id}"}})
    elif not ctx["has_sale"]:
        items.append({"id": "setup_sale", "severity": "info", "icon": "shopping-bag",
                      "title": "Record your first sale", "detail": "Tap − on any design to record a sale.",
                      "action": {"label": "Record a sale", "route": "/app/stock"}})

    active = [d for d in snap.designs.values() if d.is_active]
    out_d = sorted([d for d in active if snap.states[d.id].status == StockStatus.OUT], key=lambda d: d.label)
    if out_d:
        items.append({"id": "out_of_stock", "severity": "critical", "icon": "alert-triangle",
                      "title": f"{len(out_d)} design{'s are' if len(out_d) > 1 else ' is'} sold out",
                      "detail": _labels_text([d.label for d in out_d], len(out_d)),
                      "action": {"label": "View", "route": "/app/inventory?status=OUT"}})
        hot = [d for d in out_d if snap.states[d.id].demand == Demand.HIGH]
        if hot:
            base = reorder_service.baseline(db, snap=snap)
            hot_ids = {d.id for d in hot}
            cost = sum(float(i["line_total"]) for i in base["items"] if i["design"]["id"] in hot_ids)
            items.append({"id": "hot_out", "severity": "critical", "icon": "flame",
                          "title": f"{len(hot)} best-seller{'s need' if len(hot) > 1 else ' needs'} restocking · ≈ {costing_service.format_inr_compact(cost)}",
                          "detail": _labels_text([d.label for d in hot], len(hot)),
                          "action": {"label": "Plan purchase", "route": "/app/purchase-plans"}})
    low_d = [d for d in active if snap.states[d.id].status == StockStatus.LOW]
    if low_d:
        items.append({"id": "low_stock", "severity": "warning", "icon": "alert-circle",
                      "title": f"{len(low_d)} design{'s' if len(low_d) > 1 else ''} running low",
                      "detail": _labels_text(sorted(d.label for d in low_d), len(low_d)),
                      "action": {"label": "View", "route": "/app/inventory?status=LOW"}})
    if ctx["cur_v"] and ctx["prev_v"]:
        pct = _pct(ctx["cur_v"], ctx["prev_v"])
        if pct is not None and abs(pct) >= 1:
            up = pct > 0
            items.append({"id": "sales_change", "severity": "success" if up else "warning",
                          "icon": "trending-up" if up else "trending-down",
                          "title": f"Sales {'up' if up else 'down'} {abs(pct):.0f}% vs last {ctx['p'].period_type if ctx['p'].period_type != 'custom' else 'period'}",
                          "detail": f"{costing_service.format_inr_compact(ctx['cur_v'])} so far vs {costing_service.format_inr_compact(ctx['prev_v'])} in the same days before",
                          "action": {"label": "Reports", "route": "/app/reports?tab=sales"}})
    week = metrics_service.sales_by_design(db, _today() - timedelta(days=6), _today())
    if week:
        did, (q, v) = max(week.items(), key=lambda x: (x[1][0], x[1][1]))
        if did in snap.designs and q >= 2:
            d = snap.designs[did]
            items.append({"id": "best_week", "severity": "success", "icon": "flame",
                          "title": f"{d.label} is flying: {q} sold this week",
                          "detail": f"{d.name or d.category.name} · {costing_service.format_inr_compact(v)}",
                          "action": {"label": "Open", "route": f"/app/designs/{d.id}"}})
    if kpis["dead_stock"]:
        items.append({"id": "dead_stock", "severity": "warning", "icon": "zzz",
                      "title": f"{costing_service.format_inr_compact(kpis['dead_stock_value'])} tied up in {kpis['dead_stock']} slow design{'s' if kpis['dead_stock'] > 1 else ''}",
                      "detail": f"No sale for {snap.dead_days}+ days",
                      "action": {"label": "See list", "route": "/app/reports?tab=dead"}})
    top_cat = max(ctx["breakdown"], key=lambda b: b["sales_value"], default=None)
    if top_cat and top_cat["share_pct"] >= 25 and top_cat["sales_value"] > 0:
        items.append({"id": "top_category", "severity": "info", "icon": "chart-pie",
                      "title": f"{top_cat['name']} brought {top_cat['share_pct']:.0f}% of sales",
                      "detail": f"{top_cat['sold_units']} pieces · {costing_service.format_inr_compact(top_cat['sales_value'])} in {ctx['p'].short_label}",
                      "action": {"label": "Reports", "route": "/app/reports?tab=sales"}})
    items.sort(key=lambda x: sev_rank[x["severity"]])
    return items[:6]

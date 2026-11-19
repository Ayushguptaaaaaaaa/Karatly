from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from app.core.clock import now_utc, today as _today
from app.core.errors import AppError
from app.models import Design, PurchasePlan, PurchasePlanItem, User
from app.models.enums import (
    Decision,
    MovementSource,
    MovementType,
    PlanSource,
    PlanStatus,
    Priority,
    Role,
    StockStatus,
)
from app.services import (
    audit_service,
    costing_service,
    data_version_service,
    metrics_service,
    period_service,
    reorder_service,
    settings_service,
    stock_service,
)
from app.services.import_export_service import build_xlsx
from app.services.serializers import photo_url

money = costing_service.money


def _get(db: Session, plan_id: int) -> PurchasePlan:
    plan = db.get(PurchasePlan, plan_id, options=[joinedload(PurchasePlan.items).joinedload(PurchasePlanItem.design)])
    if not plan:
        raise AppError("PLAN_NOT_FOUND", "Purchase plan not found", 404)
    return plan


def recalc(plan: PurchasePlan) -> None:
    for it in plan.items:
        it.line_total = money(Decimal(it.expected_unit_cost) * it.final_qty)
    plan.total_estimated = money(sum((Decimal(i.line_total) for i in plan.items), Decimal("0")))
    plan.total_approved = money(sum((Decimal(i.line_total) for i in plan.items if i.decision == Decision.APPROVED),
                                    Decimal("0")))


def summary(plan: PurchasePlan) -> dict:
    return {
        "id": plan.id, "title": plan.title, "status": plan.status.value, "source": plan.source.value,
        "created_at": plan.created_at, "created_by": plan.creator.display_name if plan.creator else None,
        "item_count": len(plan.items), "total_estimated": money(plan.total_estimated),
        "total_approved": money(plan.total_approved),
        "approved_count": sum(1 for i in plan.items if i.decision == Decision.APPROVED),
        "rejected_count": sum(1 for i in plan.items if i.decision == Decision.REJECTED),
        "pending_count": sum(1 for i in plan.items if i.decision == Decision.PENDING),
        "period_label": plan.period_label,
        "scope": plan.scope or "ALL",
        "category_id": plan.category_id,
        "category_name": plan.category.name if plan.category_id and plan.category else None,
        "budget_limit": float(plan.budget_limit) if plan.budget_limit else None,
        "budget_note": plan.budget_note,
    }


def detail(db: Session, plan_id: int) -> dict:
    plan = _get(db, plan_id)
    snap = metrics_service.snapshot(db)
    items = []
    by_cat: dict[str, dict] = {}
    for it in plan.items:
        d = it.design
        st = snap.states.get(d.id)
        cat = d.category.name
        items.append({
            "id": it.id,
            "design": {"id": d.id, "label": d.label, "name": d.name, "photo_url": photo_url(d), "category_name": cat},
            "current_stock": st.current_stock if st else 0,
            "current_stock_at_creation": it.current_stock_at_creation,
            "status": st.status.value if st else "OUT",
            "demand_class": st.demand.value if st else "NEW",
            "suggested_qty": it.suggested_qty, "final_qty": it.final_qty,
            "last_unit_cost": money(it.last_unit_cost), "inflation_pct": money(it.inflation_pct),
            "expected_unit_cost": money(it.expected_unit_cost), "line_total": money(it.line_total),
            "priority": it.priority.value, "reason": it.reason, "decision": it.decision.value,
            "decision_note": it.decision_note, "received_qty": it.received_qty,
            "formula_text": costing_service.line(it.last_unit_cost, it.inflation_pct, it.final_qty)["formula_text"],
        })
        b = by_cat.setdefault(cat, {"category": cat, "amount_estimated": 0.0, "amount_approved": 0.0})
        b["amount_estimated"] += float(it.line_total)
        if it.decision == Decision.APPROVED:
            b["amount_approved"] += float(it.line_total)
    prio = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    cat_order = {c["category"]: i for i, c in enumerate(sorted(by_cat.values(), key=lambda x: -x["amount_estimated"]))}
    items.sort(key=lambda x: (cat_order.get(x["design"]["category_name"], 99), prio[x["priority"]], -float(x["line_total"])))
    total = float(money(plan.total_estimated))
    budget = float(plan.budget_limit) if plan.budget_limit else None
    return {**summary(plan), "notes": plan.notes, "insight_run_id": plan.insight_run_id,
            "items": items,
            "total_capital_required": total,
            "within_budget": (total <= budget + 0.01) if budget else None,
            "by_category": [{**v, "amount_estimated": round(v["amount_estimated"], 2),
                             "amount_approved": round(v["amount_approved"], 2)}
                            for v in sorted(by_cat.values(), key=lambda x: -x["amount_estimated"])]}


def list_plans(db: Session, status: str | None = None) -> list[dict]:
    q = db.query(PurchasePlan).options(joinedload(PurchasePlan.items), joinedload(PurchasePlan.creator))
    if status:
        q = q.filter(PurchasePlan.status.in_([PlanStatus(s.strip().upper()) for s in status.split(",")]))
    return [summary(p) for p in q.order_by(PurchasePlan.id.desc()).all()]


def _default_title(db: Session) -> str:
    p = period_service.resolve(db, "month")
    return f"Purchase plan – {p.short_label}"


def _make_item(design: Design, st, qty: int, priority: str, reason: str, infl_global,
               suggested: int | None = None) -> PurchasePlanItem:
    infl = costing_service.resolve_inflation(design, design.category, infl_global)
    c = costing_service.line(st.last_unit_cost, infl, qty)
    return PurchasePlanItem(design_id=design.id, current_stock_at_creation=st.current_stock,
                            suggested_qty=suggested if suggested is not None else qty,
                            final_qty=qty, last_unit_cost=c["last_unit_cost"], inflation_pct=c["inflation_pct"],
                            expected_unit_cost=c["expected_unit_cost"], line_total=c["line_total"],
                            priority=Priority(priority), reason=reason, decision=Decision.PENDING)


def _commit_new(db: Session, user_id: int | None, plan: PurchasePlan, action: str) -> PurchasePlan:
    recalc(plan)
    db.add(plan)
    db.flush()
    audit_service.log(db, db.get(User, user_id) if user_id else None, "CREATE", "purchase_plan", plan.id,
                      after={"source": plan.source.value, "items": len(plan.items)})
    ev = data_version_service.notify(db, "purchase_plan", action, plan.id)
    db.commit()
    data_version_service.publish(ev)
    return plan


def _apply_budget(plan: PurchasePlan, lines: list[dict], budget: float) -> list[dict]:
    """Trim lines to the monthly purchase budget (high priority funded first). Updates reasons and plan note."""
    lines, info = reorder_service.fit_to_budget(lines, budget)
    if not info["applied"]:
        return lines
    plan.budget_limit = budget
    for ln in lines:
        if ln["fitted_qty"] < ln["qty"]:
            ln["reason"] = (ln["reason"] + f" Reduced from {ln['qty']} to {ln['fitted_qty']} to fit your monthly budget."
                            if ln["fitted_qty"] else ln["reason"])
    kept = [ln for ln in lines if ln["fitted_qty"] > 0]
    if info["reduced"] or info["skipped"]:
        skipped = [ln.get("label", "?") for ln in lines if not ln["fitted_qty"]]
        plan.budget_note = (f"Trimmed to your monthly purchase budget of {costing_service.format_inr(budget, 0)}: "
                            f"{info['reduced']} line(s) reduced, {info['skipped']} skipped (lowest priority first)."
                            + (f" Not bought this month: {', '.join(skipped)}." if skipped else "")
                            + f" Buying everything would need {costing_service.format_inr(info['total_before'], 0)}.")
    else:
        plan.budget_note = f"Fits within your monthly purchase budget of {costing_service.format_inr(budget, 0)}."
    return kept


def _build_plan(db: Session, user_id: int | None, title: str, category_id: int | None, scope: str,
                source: PlanSource = PlanSource.MANUAL, apply_budget: bool = True) -> PurchasePlan | None:
    snap = metrics_service.snapshot(db)
    base = reorder_service.baseline(db, category_id, snap=snap)
    if not base["items"]:
        return None
    infl_global = settings_service.get(db, "inflation_pct_global")
    p = period_service.resolve(db, "month")
    plan = PurchasePlan(title=title, status=PlanStatus.DRAFT, source=source, scope=scope, category_id=category_id,
                        created_by=user_id, period_label=p.label, period_start=p.start, period_end=p.end)
    lines = [{"design_id": b["design"]["id"], "qty": b["suggested_qty"], "unit_cost": float(b["expected_unit_cost"]),
              "priority": b["priority"], "reason": b["reason"], "label": b["design"]["label"]} for b in base["items"]]
    budget = float(settings_service.get(db, "monthly_purchase_budget") or 0)
    if apply_budget and budget > 0:
        lines = _apply_budget(plan, lines, budget)
    for ln in lines:
        d = snap.designs[ln["design_id"]]
        plan.items.append(_make_item(d, snap.states[d.id], ln.get("fitted_qty", ln["qty"]), ln["priority"],
                                     ln["reason"], infl_global, suggested=ln["qty"]))
    return _commit_new(db, user_id, plan, "create") if plan.items else None


def create_from_baseline(db: Session, user: User, title: str | None, category_id: int | None) -> dict:
    """Without a category: the FINAL plan for all categories (budget applied). With one: that category's plan."""
    from app.models import Category

    if category_id:
        cat = db.get(Category, category_id)
        if not cat:
            raise AppError("CATEGORY_NOT_FOUND", "Category not found", 404)
        plan = _build_plan(db, user.id, title or f"{cat.name} plan – {_month_short(db)}", category_id, "CATEGORY",
                           apply_budget=False)
    else:
        plan = _build_plan(db, user.id, title or f"Final plan – {_month_short(db)} (all categories)", None, "ALL")
    if plan is None:
        raise AppError("NOTHING_TO_REORDER", "Nothing needs restocking right now. All designs are above their minimum.", 422)
    return detail(db, plan.id)


def create_per_category(db: Session, user: User) -> list[dict]:
    """One draft plan per category that needs restocking."""
    from app.models import Category

    out = []
    for cat in db.query(Category).filter(Category.is_active.is_(True)).order_by(Category.sort_order):
        plan = _build_plan(db, user.id, f"{cat.name} plan – {_month_short(db)}", cat.id, "CATEGORY", apply_budget=False)
        if plan:
            out.append(summary(_get(db, plan.id)))
    if not out:
        raise AppError("NOTHING_TO_REORDER", "Nothing needs restocking right now. All designs are above their minimum.", 422)
    return out


def _month_short(db: Session) -> str:
    return period_service.resolve(db, "month").short_label


def create_from_ai(db: Session, user_id: int | None, run_id: int, period: period_service.Period,
                   reorder_output: dict, notes: str | None) -> PurchasePlan | None:
    """AI quantities are clamped and every cost is recalculated by code."""
    snap = metrics_service.snapshot(db)
    by_label = {d.label: d for d in snap.designs.values() if d.is_active}
    infl_global = settings_service.get(db, "inflation_pct_global")
    base = {b["design"]["label"]: b for b in reorder_service.baseline(db, snap=snap)["items"]}
    plan = PurchasePlan(title=f"AI final purchase plan – {period.short_label} (all categories)", status=PlanStatus.DRAFT,
                        source=PlanSource.AI, scope="ALL", insight_run_id=run_id, created_by=user_id, notes=notes,
                        period_label=period.label, period_start=period.start, period_end=period.end)
    lines: list[dict] = []
    seen = set()
    for line in (reorder_output or {}).get("items", []):
        lbl = str(line.get("label", "")).strip().upper()
        d = by_label.get(lbl)
        if not d or lbl in seen:
            continue
        st = snap.states[d.id]
        if st.status == StockStatus.DEAD:
            continue
        b = base.get(lbl)
        if b is None:  # the system doesn't think this design needs restocking
            continue
        try:
            qty = int(line.get("suggested_qty") or 0)
        except (TypeError, ValueError):
            continue
        reason = str(line.get("reason") or b["reason"])[:600]
        # AI may adjust the baseline, but never beyond the usual-stock cap or below half the baseline
        lo, hi = max(1, b["suggested_qty"] // 2), max(b["suggested_qty"], b["max_qty"])
        if qty > hi:
            reason += f" (capped at {hi}: about {b['usual_stock']} is your usual stock for this design)"
        qty = max(lo, min(qty, hi))
        prio = str(line.get("priority") or b["priority"]).upper()
        prio = prio if prio in Priority.__members__ else b["priority"]
        lines.append({"design_id": d.id, "qty": qty, "unit_cost": float(b["expected_unit_cost"]),
                      "priority": prio, "reason": reason, "label": d.label})
        seen.add(lbl)
    budget = float(settings_service.get(db, "monthly_purchase_budget") or 0)
    if budget > 0:
        lines = _apply_budget(plan, lines, budget)
    for ln in lines:
        d = snap.designs[ln["design_id"]]
        plan.items.append(_make_item(d, snap.states[d.id], ln.get("fitted_qty", ln["qty"]), ln["priority"],
                                     ln["reason"], infl_global, suggested=ln["qty"]))
    if not plan.items:
        return None
    return _commit_new(db, user_id, plan, "create_ai")


def _editable(plan: PurchasePlan, statuses=(PlanStatus.DRAFT, PlanStatus.SUBMITTED)):
    if plan.status not in statuses:
        raise AppError("PLAN_LOCKED", f"This plan is {plan.status.value.lower()} and can't be changed.", 409)


def _save(db: Session, user: User, plan: PurchasePlan, action: str, after=None) -> dict:
    recalc(plan)
    audit_service.log(db, user, action, "purchase_plan", plan.id, after=after)
    if action == "RECEIVE":  # stock changed
        ev = data_version_service.bump(db, "purchase_plan", action.lower(), plan.id)
    else:
        ev = data_version_service.notify(db, "purchase_plan", action.lower(), plan.id)
    db.commit()
    data_version_service.publish(ev)
    return detail(db, plan.id)


def update(db: Session, user: User, plan_id: int, data: dict) -> dict:
    plan = _get(db, plan_id)
    _editable(plan)
    if data.get("title"):
        plan.title = data["title"].strip()[:120]
    if "notes" in data:
        plan.notes = data["notes"]
    return _save(db, user, plan, "UPDATE", data)


def add_item(db: Session, user: User, plan_id: int, design_id: int, qty: int) -> dict:
    plan = _get(db, plan_id)
    _editable(plan, (PlanStatus.DRAFT,))
    if any(i.design_id == design_id for i in plan.items):
        raise AppError("ITEM_EXISTS", "This design is already in the plan.", 409)
    snap = metrics_service.snapshot(db)
    d = snap.designs.get(design_id)
    if not d:
        raise AppError("DESIGN_NOT_FOUND", "Design not found", 404)
    plan.items.append(_make_item(d, snap.states[d.id], max(0, int(qty)), "MEDIUM", "Added manually",
                                 settings_service.get(db, "inflation_pct_global")))
    return _save(db, user, plan, "UPDATE", {"add": d.label})


def update_item(db: Session, user: User, plan_id: int, item_id: int, data: dict) -> dict:
    plan = _get(db, plan_id)
    item = next((i for i in plan.items if i.id == item_id), None)
    if not item:
        raise AppError("ITEM_NOT_FOUND", "Item not found", 404)
    if "final_qty" in data and data["final_qty"] is not None:
        _editable(plan)
        q = int(data["final_qty"])
        if q < 0 or q > 10000:
            raise AppError("VALIDATION_ERROR", "Quantity must be between 0 and 10,000", 422)
        item.final_qty = q
    if data.get("decision") is not None or data.get("decision_note") is not None:
        if user.role != Role.OWNER:
            raise AppError("FORBIDDEN", "Only the owner can approve or reject.", 403)
        _editable(plan)
        if data.get("decision"):
            item.decision = Decision(data["decision"])
        if data.get("decision_note") is not None:
            item.decision_note = data["decision_note"]
    return _save(db, user, plan, "UPDATE", data)


def remove_item(db: Session, user: User, plan_id: int, item_id: int) -> dict:
    plan = _get(db, plan_id)
    _editable(plan, (PlanStatus.DRAFT,))
    item = next((i for i in plan.items if i.id == item_id), None)
    if not item:
        raise AppError("ITEM_NOT_FOUND", "Item not found", 404)
    plan.items.remove(item)
    return _save(db, user, plan, "UPDATE", {"remove": item_id})


def submit(db: Session, user: User, plan_id: int) -> dict:
    plan = _get(db, plan_id)
    if plan.status != PlanStatus.DRAFT:
        raise AppError("PLAN_LOCKED", "Only draft plans can be submitted.", 409)
    if not plan.items:
        raise AppError("EMPTY_PLAN", "Add at least one item before submitting.", 422)
    plan.status = PlanStatus.SUBMITTED
    plan.submitted_by, plan.submitted_at = user.id, now_utc()
    return _save(db, user, plan, "SUBMIT")


def decide(db: Session, user: User, plan_id: int, approve_all: bool, decisions: list[dict]) -> dict:
    plan = _get(db, plan_id)
    _editable(plan)
    items = {i.id: i for i in plan.items}
    for dcs in decisions or []:
        it = items.get(dcs.get("item_id"))
        if not it:
            raise AppError("ITEM_NOT_FOUND", f"Item {dcs.get('item_id')} not in plan", 404)
        if dcs.get("final_qty") is not None:
            it.final_qty = max(0, int(dcs["final_qty"]))
        if dcs.get("decision"):
            it.decision = Decision(dcs["decision"])
        if dcs.get("decision_note") is not None:
            it.decision_note = dcs["decision_note"]
    if approve_all:
        for it in plan.items:
            if it.decision == Decision.PENDING:
                it.decision = Decision.APPROVED
    pending = [i.design.label for i in plan.items if i.decision == Decision.PENDING]
    if pending:
        raise AppError("UNDECIDED_ITEMS", f"Please approve or reject every line ({len(pending)} pending).", 422,
                       {"pending_item_ids": [i.id for i in plan.items if i.decision == Decision.PENDING]})
    plan.status = PlanStatus.DECIDED
    plan.decided_by, plan.decided_at = user.id, now_utc()
    return _save(db, user, plan, "DECIDE")


def receive(db: Session, user: User, plan_id: int, occurred_on: date | None, items: list[dict]) -> dict:
    plan = _get(db, plan_id)
    if plan.status != PlanStatus.DECIDED:
        raise AppError("PLAN_NOT_DECIDED", "The owner must approve the plan before stock is received.", 409)
    by_id = {i.id: i for i in plan.items}
    on = occurred_on or _today()
    count = 0
    for r in items:
        it = by_id.get(r.get("item_id"))
        if not it or it.decision != Decision.APPROVED:
            raise AppError("ITEM_NOT_APPROVED", "Only approved lines can be received.", 422)
        qty = int(r.get("quantity") or 0)
        if qty <= 0:
            continue
        cost = r.get("unit_cost")
        stock_service._add_movement(db, user, it.design, MovementType.PURCHASE, qty, on,
                                    cost if cost is not None else it.expected_unit_cost,
                                    note=f"Received from plan #{plan.id}", source=MovementSource.PURCHASE_PLAN,
                                    plan_item_id=it.id)
        it.received_qty += qty
        count += 1
    if not count:
        raise AppError("VALIDATION_ERROR", "Enter a received quantity for at least one line.", 422)
    approved = [i for i in plan.items if i.decision == Decision.APPROVED]
    if approved and all(i.received_qty >= i.final_qty for i in approved):
        plan.status = PlanStatus.RECEIVED
        plan.received_at = now_utc()
    return _save(db, user, plan, "RECEIVE", {"lines": count})


def delete(db: Session, user: User, plan_id: int) -> None:
    plan = _get(db, plan_id)
    if plan.status != PlanStatus.DRAFT:
        raise AppError("PLAN_LOCKED", "Only draft plans can be deleted.", 409)
    db.delete(plan)
    audit_service.log(db, user, "DELETE", "purchase_plan", plan_id)
    ev = data_version_service.notify(db, "purchase_plan", "delete", plan_id)
    db.commit()
    data_version_service.publish(ev)


def export_xlsx(db: Session, plan_id: int) -> tuple[str, bytes]:
    data = detail(db, plan_id)
    heads = ["Label", "Name", "Category", "Stock now", "Suggested qty", "Final qty", "Last cost", "Inflation %",
             "Expected unit cost", "Line total", "Priority", "Decision", "Received", "Reason"]
    rows = [[i["design"]["label"], i["design"]["name"], i["design"]["category_name"], i["current_stock"],
             i["suggested_qty"], i["final_qty"], float(i["last_unit_cost"]), float(i["inflation_pct"]),
             float(i["expected_unit_cost"]), float(i["line_total"]), i["priority"], i["decision"], i["received_qty"],
             i["reason"]] for i in data["items"]]
    rows.append(["TOTAL", "", "", "", "", "", "", "", "", float(data["total_estimated"]), "", "", "", ""])
    return f"purchase_plan_{plan_id}.xlsx", build_xlsx("Purchase plan", heads, rows, {6, 8, 9})

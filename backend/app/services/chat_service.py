from __future__ import annotations

import json
import logging
import threading

from sqlalchemy.orm import Session

from app.core.clock import today as _today
from app.core.database import SessionLocal
from app.core.errors import AppError
from app.models import ChatMessage, ChatSession, Design, User
from app.models.enums import ChatRole, Demand, JobType, MessageStatus, Role, StockStatus
from app.services import dashboard_service, job_service, metrics_service, period_service, settings_service

log = logging.getLogger("app.chat")


def message_out(m: ChatMessage) -> dict:
    return {"id": m.id, "role": m.role.value, "content": m.content, "status": m.status.value,
            "payload": m.payload or {}, "job_id": m.job_id, "created_at": m.created_at}


def _session(db: Session, user: User, session_id: int) -> ChatSession:
    s = db.get(ChatSession, session_id)
    if not s or s.user_id != user.id:
        raise AppError("SESSION_NOT_FOUND", "Chat not found", 404)
    return s


def list_sessions(db: Session, user: User) -> list[dict]:
    rows = db.query(ChatSession).filter(ChatSession.user_id == user.id).order_by(ChatSession.updated_at.desc()).all()
    return [{"id": s.id, "title": s.title, "updated_at": s.updated_at, "message_count": len(s.messages)} for s in rows]


def create_session(db: Session, user: User, title: str | None) -> dict:
    s = ChatSession(user_id=user.id, title=(title or "New chat")[:80])
    db.add(s)
    db.commit()
    return {"id": s.id, "title": s.title, "updated_at": s.updated_at, "message_count": 0}


def get_session(db: Session, user: User, session_id: int) -> dict:
    s = _session(db, user, session_id)
    return {"session": {"id": s.id, "title": s.title, "updated_at": s.updated_at, "message_count": len(s.messages)},
            "messages": [message_out(m) for m in s.messages]}


def delete_session(db: Session, user: User, session_id: int) -> None:
    s = _session(db, user, session_id)
    db.delete(s)
    db.commit()


def post_message(db: Session, user: User, session_id: int, text: str) -> dict:
    s = _session(db, user, session_id)
    text = (text or "").strip()
    if not text:
        raise AppError("VALIDATION_ERROR", "Please type a question.", 422)
    if any(m.status == MessageStatus.PENDING for m in s.messages):
        raise AppError("ANSWER_PENDING", "Please wait for the current answer.", 409)
    if s.title == "New chat" or not s.messages:
        s.title = text[:60] + ("…" if len(text) > 60 else "")
    um = ChatMessage(session_id=s.id, role=ChatRole.USER, content=text, status=MessageStatus.COMPLETE)
    job = job_service.create(db, JobType.CHAT_ANSWER, user.id,
                             [("think", "Reading your question"), ("answer", "Preparing the answer")])
    am = ChatMessage(session_id=s.id, role=ChatRole.ASSISTANT, content="", status=MessageStatus.PENDING,
                     job_id=job.id, payload={})
    db.add_all([um, am])
    db.commit()
    history = [f"{m.role.value.lower()}: {m.content[:400]}" for m in s.messages
               if m.status == MessageStatus.COMPLETE and m.id != um.id][-6:]
    threading.Thread(target=_answer, args=(job.id, am.id, user.id, user.role.value, text, history),
                     daemon=True, name=f"chat-{am.id}").start()
    return {"user_message": message_out(um), "assistant_message": message_out(am), "job_id": job.id}


def shop_snapshot(db: Session) -> dict:
    """Everything a typical question needs, pre-computed so the chat model rarely has to call tools."""
    from app.services import profit_service, reorder_service, report_service

    month = period_service.resolve(db, "month")
    day = period_service.resolve(db, "day")
    ov = dashboard_service.overview(db, month)
    latest = ov.get("latest_ai")
    k = {key: (float(v) if hasattr(v, "quantize") else v) for key, v in ov["kpis"].items()}
    today_p = profit_service.profitability(db, day, "design", limit=10)
    cat_p = profit_service.profitability(db, month, "category")
    sub_p = profit_service.profitability(db, month, "subcategory", limit=15)
    des_p = profit_service.profitability(db, month, "design", limit=10)
    base = reorder_service.baseline(db)
    dead = report_service.dead_stock(db)
    pick = ("name", "category", "units_sold", "units_returned", "net_revenue", "cogs", "net_profit", "margin_pct")

    def rows(rep):
        return [{f: r.get(f) for f in pick if f in r} for r in rep["rows"]]

    return {
        "shop": settings_service.get(db, "shop_name"),
        "today": {"date": day.label, "totals": today_p["totals"], "designs_sold_today": rows(today_p)},
        "this_month": {"period": month.label, "kpis": k, "profit_by_category": rows(cat_p),
                       "profit_by_subcategory": rows(sub_p), "top_designs_by_profit": rows(des_p),
                       "top_sellers": [{"label": t["label"], "sold": t["sold_units"], "sales_value": t["sales_value"]}
                                       for t in ov["top_sellers"]]},
        "stock_health": ov["stock_health"],
        "sold_out_and_low": [{"label": a["label"], "category": a["category_name"], "status": a["status"],
                              "stock": a["current_stock"], "demand": a["demand_class"], "sold_30d": a["sold_last_30d"]}
                             for a in ov["alerts"]],
        "restock_suggestion": {"total_budget": float(base["total_estimated"]), "by_category": base["by_category"],
                               "lines": [{"label": i["design"]["label"], "qty": i["suggested_qty"],
                                          "priority": i["priority"], "line_total": float(i["line_total"])}
                                         for i in base["items"][:12]]},
        "dead_stock": {"total_value": dead["total_value"], "not_selling_days": dead["dead_stock_days"],
                       "designs": [{"label": r["design"]["label"], "stock": r["current_stock"],
                                    "days_since_sale": r["days_since_last_sale"], "value": r["value_tied_up"]}
                                   for r in dead["items"][:10]]},
        "sales_trend_6_months": [{"month": t["label"], "units": t["units"], "value": t["value"]} for t in ov["sales_trend"]],
        "categories": [{"name": c["name"], "pieces_in_stock": c["pieces"], "sold_this_month": c["sold_units"]}
                       for c in ov["category_breakdown"]],
        "latest_insights_headline": latest["headline"] if latest else None,
    }


def _answer(job_id: str, msg_id: int, user_id: int, role: str, question: str, history: list[str]) -> None:
    """Never waits for the insights report (no shared AI lock).
    1. Common questions -> instant answer from exact data (well under a second).
    2. Everything else -> fast chat model with the snapshot in the prompt (usually one LLM call).
    3. AI busy / over quota -> instant answer or a quick summary instead of an error."""
    import time

    from app.ai import instant_answers
    from app.ai.llm import model_manager
    from app.core.config import get_settings

    t0 = time.time()
    try:
        job_service.start(job_id)
        with SessionLocal() as db:
            snap = shop_snapshot(db)
        job_service.update_step(job_id, "think", "DONE")
        quick = instant_answers.answer(question, snap) if get_settings().CHAT_INSTANT_ANSWERS else None
        if quick is not None:
            ans, model = quick, "instant"
            job_service.update_step(job_id, "answer", "DONE", model_used="instant")
        else:
            model_manager.count("chat")
            outs, model = _ai_answer(job_id, role, question, history, snap)
            ans = outs[0]
        _save_answer(job_id, msg_id, ans, model, t0)
    except Exception as e:  # noqa: BLE001
        log.exception("Chat answer failed")
        with SessionLocal() as db:
            m = db.get(ChatMessage, msg_id)
            if m:
                m.status = MessageStatus.FAILED
                m.content = "I couldn't answer that right now."
                db.commit()
        job_service.fail(job_id, str(e)[:200], JobType.CHAT_ANSWER.value)


def _ai_answer(job_id: str, role: str, question: str, history: list[str], snap: dict):
    from app.ai import instant_answers
    from app.ai.crews.assistant_crew.crew import AssistantCrew
    from app.ai.llm import model_manager
    from app.ai.outputs import ChatAnswer
    from app.ai.runner import run_crew_step

    return run_crew_step(
        job_id=job_id, step_keys=["answer"],
        build_crew=lambda llm, sc, tc: AssistantCrew(llm, sc, tc),
        inputs={"shop_name": snap["shop"], "user_role": "owner" if role == "OWNER" else "admin",
                "today": str(_today()),
                "shop_snapshot": json.dumps(snap, default=str, ensure_ascii=False, separators=(",", ":")),
                "chat_history": "\n".join(history) or "(none)", "question": question},
        output_models=[ChatAnswer],
        fallback=lambda: [instant_answers.answer(question, snap, strict=False)],
        kinds=model_manager.chat_kinds(),
        retries=1,
    )


def _save_answer(job_id: str, msg_id: int, ans, model: str, t0: float) -> None:
    import time

    with SessionLocal() as db:
        m = db.get(ChatMessage, msg_id)
        m.content = ans.answer_markdown
        m.payload = {"table": ans.table.model_dump() if ans.table else None,
                     "chart": ans.chart.model_dump() if ans.chart else None,
                     "follow_up_questions": ans.follow_up_questions[:3], "model_used": model,
                     "seconds": round(time.time() - t0, 1)}
        m.status = MessageStatus.COMPLETE
        db.commit()
    log.info("Chat answered in %.1fs with %s", time.time() - t0, model)
    job_service.finish(job_id, "chat_message", msg_id, JobType.CHAT_ANSWER.value)


def suggestions(db: Session, user: User) -> list[str]:
    if not db.query(Design.id).first():
        return ["How do I get started?", "What will the AI insights show me?"]
    if user.role == Role.OWNER:
        out = ["What should I restock this month and how much money do I need?", "Which designs are not selling?",
               "What was my net profit this month, by category?", "Which designs made the most profit today?"]
    else:
        out = ["Which designs are running low?", "Show today's sales", "Are there any unusual entries I should check?",
               "Summarise stock by category"]
    snap = metrics_service.snapshot(db, include_inactive=False)
    states = snap.states
    hot = [d for d in snap.designs.values() if states[d.id].status == StockStatus.OUT and states[d.id].demand == Demand.HIGH]
    if hot:
        out.append(f"Why is {hot[0].label} selling so fast?")
    low = [d for d in snap.designs.values() if states[d.id].status == StockStatus.LOW]
    if low:
        out.append(f"Should I reorder {low[0].label}?")
    if any(states[d.id].status == StockStatus.DEAD for d in snap.designs.values()):
        out.append("How much money is stuck in dead stock?")
    p = period_service.resolve(db, "quarter")
    cats = {c.id: c for c in snap.categories.values() if c.is_active}
    if cats:
        sales = metrics_service.sales_by_design(db, p.start, p.effective_end)
        by_cat: dict[int, float] = {}
        for did, (_, v) in sales.items():
            d = snap.designs.get(did)
            if d:
                by_cat[d.category_id] = by_cat.get(d.category_id, 0) + float(v)
        if by_cat:
            top = max(by_cat, key=by_cat.get)
            if top in cats:
                out.append(f"How did {cats[top].name} do this quarter?")
    return out[:8]

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
    ov = dashboard_service.overview(db, period_service.resolve(db, "month"))
    latest = ov.get("latest_ai")
    k = {key: (float(v) if hasattr(v, "quantize") else v) for key, v in ov["kpis"].items()}
    return {
        "shop": settings_service.get(db, "shop_name"), "month": ov["period"]["label"], "kpis": k,
        "stock_health": ov["stock_health"],
        "top_sellers_this_month": [{"label": t["label"], "sold": t["sold_units"]} for t in ov["top_sellers"]],
        "alerts": [{"label": a["label"], "status": a["status"], "stock": a["current_stock"], "demand": a["demand_class"]}
                   for a in ov["alerts"]],
        "categories": [{"name": c["name"], "pieces": c["pieces"], "sold_this_month": c["sold_units"]}
                       for c in ov["category_breakdown"]],
        "latest_insights_headline": latest["headline"] if latest else None,
    }


def _answer(job_id: str, msg_id: int, user_id: int, role: str, question: str, history: list[str]) -> None:
    from app.ai import fallbacks
    from app.ai.crews.assistant_crew.crew import AssistantCrew
    from app.ai.llm import AI_LOCK, model_manager
    from app.ai.outputs import ChatAnswer
    from app.ai.runner import run_crew_step

    if not AI_LOCK.acquire(blocking=False):
        job_service.update_step(job_id, "think", "RUNNING", note="Waiting for the AI to finish the insights report…")
        AI_LOCK.acquire()
    try:
        job_service.start(job_id)
        job_service.update_step(job_id, "think", "DONE")
        with SessionLocal() as db:
            snap = shop_snapshot(db)
        model_manager.count("chat")
        outs, model = run_crew_step(
            job_id=job_id, step_keys=["answer"],
            build_crew=lambda llm, sc, tc: AssistantCrew(llm, sc, tc),
            inputs={"shop_name": snap["shop"], "user_role": "owner" if role == "OWNER" else "admin",
                    "today": str(_today()), "shop_snapshot": json.dumps(snap, default=str, ensure_ascii=False),
                    "chat_history": "\n".join(history) or "(none)", "question": question},
            output_models=[ChatAnswer],
            fallback=lambda: [fallbacks.chat_answer(snap, question)],
        )
        ans: ChatAnswer = outs[0]
        with SessionLocal() as db:
            m = db.get(ChatMessage, msg_id)
            m.content = ans.answer_markdown
            m.payload = {"table": ans.table.model_dump() if ans.table else None,
                         "chart": ans.chart.model_dump() if ans.chart else None,
                         "follow_up_questions": ans.follow_up_questions[:3], "model_used": model}
            m.status = MessageStatus.COMPLETE
            db.commit()
        job_service.finish(job_id, "chat_message", msg_id, JobType.CHAT_ANSWER.value)
    except Exception as e:  # noqa: BLE001
        log.exception("Chat answer failed")
        with SessionLocal() as db:
            m = db.get(ChatMessage, msg_id)
            if m:
                m.status = MessageStatus.FAILED
                m.content = "I couldn't answer that right now."
                db.commit()
        job_service.fail(job_id, str(e)[:200], JobType.CHAT_ANSWER.value)
    finally:
        AI_LOCK.release()


def suggestions(db: Session, user: User) -> list[str]:
    if not db.query(Design.id).first():
        return ["How do I get started?", "What will the AI insights show me?"]
    if user.role == Role.OWNER:
        out = ["What should I restock this month and how much money do I need?", "Which designs are not selling?",
               "How are sales this month compared to last month?", "Which category earns the most?"]
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

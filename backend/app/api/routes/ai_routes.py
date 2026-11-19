"""Insights, chat and admin-tool routes."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Response
from pydantic import Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, OwnerOnly
from app.core.errors import AppError
from app.models import User
from app.schemas.common import In
from app.services import chat_service, demo_data_service, insights_service

router = APIRouter()


class RunIn(In):
    period_type: str = "month"
    anchor: date | None = None


@router.post("/insights/runs", status_code=202, tags=["insights"])
def start_run(body: RunIn, db: Session = Depends(get_db), user: User = CurrentUser):
    return insights_service.start_run(db, user, body.period_type, body.anchor)


@router.get("/insights/latest", tags=["insights"])
def latest(db: Session = Depends(get_db), _: User = CurrentUser):
    return insights_service.latest(db)


@router.get("/insights/running", tags=["insights"])
def running(db: Session = Depends(get_db), _: User = CurrentUser):
    return insights_service.running_job(db)


@router.get("/insights/runs", tags=["insights"])
def runs(limit: int = 20, db: Session = Depends(get_db), _: User = CurrentUser):
    return insights_service.list_runs(db, limit)


@router.get("/insights/runs/{run_id}", tags=["insights"])
def run(run_id: int, db: Session = Depends(get_db), _: User = CurrentUser):
    return insights_service.get(db, run_id)


# ---- chat ---------------------------------------------------------------------------
class SessionIn(In):
    title: str | None = Field(default=None, max_length=80)


class MessageIn(In):
    text: str = Field(min_length=1, max_length=1000)


@router.get("/chat/sessions", tags=["chat"])
def sessions(db: Session = Depends(get_db), user: User = CurrentUser):
    return chat_service.list_sessions(db, user)


@router.post("/chat/sessions", status_code=201, tags=["chat"])
def new_session(body: SessionIn | None = None, db: Session = Depends(get_db), user: User = CurrentUser):
    return chat_service.create_session(db, user, body.title if body else None)


@router.get("/chat/suggestions", tags=["chat"])
def suggestions(db: Session = Depends(get_db), user: User = CurrentUser):
    return {"questions": chat_service.suggestions(db, user)}


@router.get("/chat/sessions/{session_id}", tags=["chat"])
def get_session(session_id: int, db: Session = Depends(get_db), user: User = CurrentUser):
    return chat_service.get_session(db, user, session_id)


@router.delete("/chat/sessions/{session_id}", status_code=204, tags=["chat"])
def delete_session(session_id: int, db: Session = Depends(get_db), user: User = CurrentUser):
    chat_service.delete_session(db, user, session_id)
    return Response(status_code=204)


@router.post("/chat/sessions/{session_id}/messages", status_code=202, tags=["chat"])
def post_message(session_id: int, body: MessageIn, db: Session = Depends(get_db), user: User = CurrentUser):
    return chat_service.post_message(db, user, session_id, body.text)


# ---- admin tools ----------------------------------------------------------------------
class DemoIn(In):
    force: bool = False


class ResetIn(In):
    confirm: str


@router.post("/admin/demo-data", tags=["admin"])
def demo_data(body: DemoIn | None = None, db: Session = Depends(get_db), user: User = CurrentUser):
    return demo_data_service.load(db, user, body.force if body else False)


@router.post("/admin/reset", tags=["admin"])
def reset(body: ResetIn, db: Session = Depends(get_db), user: User = OwnerOnly):
    if body.confirm != "RESET":
        raise AppError("CONFIRM_REQUIRED", 'Type RESET to confirm.', 422)
    return demo_data_service.reset(db, user)

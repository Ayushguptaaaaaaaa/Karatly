"""Background job bookkeeping + SSE progress events.

All functions open their own short DB session so they are safe to call from worker threads.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.clock import now_utc
from app.core.database import SessionLocal
from app.core.events import bus
from app.models import Job
from app.models.enums import JobStatus, JobType


def job_out(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "type": job.type.value,
        "status": job.status.value,
        "steps": job.steps or [],
        "error": job.error,
        "result_type": job.result_type,
        "result_id": job.result_id,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }


def create(db: Session, job_type: JobType, user_id: int | None, steps: list[tuple[str, str]]) -> Job:
    job = Job(
        id=str(uuid.uuid4()),
        type=job_type,
        status=JobStatus.QUEUED,
        created_by=user_id,
        steps=[
            {"key": k, "label": label, "status": "PENDING", "started_at": None, "finished_at": None,
             "model_used": None, "note": None}
            for k, label in steps
        ],
    )
    db.add(job)
    db.flush()
    return job


def get(db: Session, job_id: str) -> Job | None:
    return db.get(Job, job_id)


def _mutate(job_id: str, fn) -> dict | None:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job:
            return None
        fn(job)
        flag_modified(job, "steps")
        db.commit()
        return job_out(job)


def start(job_id: str) -> None:
    def fn(job: Job):
        job.status = JobStatus.RUNNING
        job.started_at = now_utc()

    _mutate(job_id, fn)


def update_step(job_id: str, key: str, status: str, model_used: str | None = None, note: str | None = None) -> None:
    payload: dict[str, Any] = {}

    def fn(job: Job):
        steps = [dict(s) for s in (job.steps or [])]
        for s in steps:
            if s["key"] == key:
                s["status"] = status
                ts = now_utc().isoformat()
                if status == "RUNNING":
                    s["started_at"] = ts
                elif status in ("DONE", "FAILED", "SKIPPED"):
                    s["finished_at"] = ts
                if model_used is not None:
                    s["model_used"] = model_used
                if note is not None:
                    s["note"] = note
                payload.update(s)
        job.steps = steps

    _mutate(job_id, fn)
    if payload:
        bus.publish(f"job:{job_id}", "step", payload)


def tool_event(job_id: str, label: str) -> None:
    bus.publish(f"job:{job_id}", "tool", {"label": label})


def finish(job_id: str, result_type: str | None, result_id: int | None, job_type: str) -> None:
    def fn(job: Job):
        job.status = JobStatus.SUCCEEDED
        job.finished_at = now_utc()
        job.result_type = result_type
        job.result_id = result_id

    _mutate(job_id, fn)
    data = {"status": "SUCCEEDED", "result_type": result_type, "result_id": result_id}
    bus.publish(f"job:{job_id}", "done", data)
    bus.publish("global", "job_finished", {"job_id": job_id, "type": job_type, "result_id": result_id})


def fail(job_id: str, message: str, job_type: str) -> None:
    def fn(job: Job):
        job.status = JobStatus.FAILED
        job.finished_at = now_utc()
        job.error = message

    _mutate(job_id, fn)
    bus.publish(f"job:{job_id}", "error", {"message": message})
    bus.publish("global", "job_finished", {"job_id": job_id, "type": job_type, "result_id": None, "failed": True})


def fail_orphans(db: Session) -> None:
    """Jobs left running when the server stopped can never finish."""
    from app.models import ChatMessage, InsightRun
    from app.models.enums import MessageStatus, RunStatus

    for job in db.query(Job).filter(Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING])).all():
        job.status = JobStatus.FAILED
        job.error = "Server restarted"
        job.finished_at = now_utc()
    for run in db.query(InsightRun).filter(InsightRun.status == RunStatus.RUNNING).all():
        run.status = RunStatus.FAILED
    for msg in db.query(ChatMessage).filter(ChatMessage.status == MessageStatus.PENDING).all():
        msg.status = MessageStatus.FAILED
        msg.content = "This answer was interrupted. Please ask again."
    db.commit()

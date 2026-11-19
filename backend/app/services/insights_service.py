"""Start insights runs in the background and read them back."""
from __future__ import annotations

import logging
import threading
from datetime import date

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.errors import AppError
from app.models import Design, InsightRun, Job, User
from app.models.enums import JobStatus, JobType, RunStatus
from app.services import data_version_service, job_service, period_service, purchase_plan_service

log = logging.getLogger("app.insights")


def start_run(db: Session, user: User, period_type: str, anchor: date | None) -> dict:
    from app.ai.flows.insights_flow import STEPS

    if not db.query(Design.id).filter(Design.is_active.is_(True)).first():
        raise AppError("NO_DATA", "Add some designs and stock first. The AI needs something to analyse.", 422)
    busy = (db.query(Job).filter(Job.type == JobType.INSIGHTS_RUN,
                                 Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING])).first())
    if busy:
        raise AppError("AI_BUSY", "Insights are already being generated.", 409, {"job_id": busy.id})
    p = period_service.resolve(db, period_type, anchor)
    job = job_service.create(db, JobType.INSIGHTS_RUN, user.id, STEPS)
    run = InsightRun(job_id=job.id, period_type=p.period_type.upper(), period_start=p.start, period_end=p.end,
                     period_label=p.label, data_version=data_version_service.current(db), status=RunStatus.RUNNING,
                     created_by=user.id)
    db.add(run)
    db.commit()
    args = (job.id, run.id, user.id, p.period_type, (anchor or p.start).isoformat())
    threading.Thread(target=_run_insights, args=args, daemon=True, name=f"insights-{run.id}").start()
    return {"job_id": job.id, "run_id": run.id}


def _run_insights(job_id: str, run_id: int, user_id: int, period_type: str, anchor: str) -> None:
    from app.ai.flows.insights_flow import InsightsFlow
    from app.ai.llm import AI_LOCK, model_manager

    try:
        from crewai_core.printer import set_suppress_console_output

        set_suppress_console_output(True)  # no Rich flow panels in the server log
    except Exception:  # pragma: no cover
        pass
    with AI_LOCK:
        try:
            job_service.start(job_id)
            model_manager.count("run")
            flow = InsightsFlow()
            flow.kickoff(inputs={"run_id": run_id, "job_id": job_id, "user_id": user_id,
                                 "period_type": period_type, "anchor": anchor})
            job_service.finish(job_id, "insight_run", run_id, JobType.INSIGHTS_RUN.value)
        except Exception as e:  # noqa: BLE001
            log.exception("Insights run failed")
            with SessionLocal() as db:
                run = db.get(InsightRun, run_id)
                if run:
                    run.status = RunStatus.FAILED
                    db.commit()
            job_service.fail(job_id, f"Insights could not be generated: {str(e)[:200]}", JobType.INSIGHTS_RUN.value)


def run_out(db: Session, run: InsightRun) -> dict:
    dv = data_version_service.current(db)
    pack = run.analysis_pack or {}
    facts = pack.get("_facts", {})
    plan = None
    if run.purchase_plan_id:
        try:
            plan = purchase_plan_service.summary(purchase_plan_service._get(db, run.purchase_plan_id))  # noqa: SLF001
        except AppError:
            plan = None
    return {
        "id": run.id, "job_id": run.job_id, "status": run.status.value, "period_type": run.period_type,
        "period_label": run.period_label, "period_start": run.period_start, "period_end": run.period_end,
        "created_at": run.created_at, "finished_at": run.finished_at, "models_used": run.models_used or [],
        "is_stale": dv > run.data_version, "changes_since": max(dv - run.data_version, 0),
        "data_sufficiency": (pack.get("data_sufficiency") or {}).get("level", "LOW"),
        "report": run.report, "stock_position": run.stock_position, "demand": run.demand,
        "anomalies": run.anomalies, "reorder": run.reorder, "budget": run.budget, "purchase_plan": plan,
        "facts": facts,
        "evidence": {"designs_of_interest": (pack.get("designs_of_interest") or [])[:40],
                     "categories": pack.get("categories") or [],
                     "anomaly_candidates": pack.get("anomaly_candidates") or [],
                     "reorder_baseline": (pack.get("reorder_baseline") or [])[:20]},
    }


def latest(db: Session) -> dict | None:
    run = (db.query(InsightRun).filter(InsightRun.status.in_([RunStatus.COMPLETE, RunStatus.PARTIAL]))
           .order_by(InsightRun.id.desc()).first())
    return run_out(db, run) if run else None


def get(db: Session, run_id: int) -> dict:
    run = db.get(InsightRun, run_id)
    if not run:
        raise AppError("RUN_NOT_FOUND", "Insights run not found", 404)
    return run_out(db, run)


def list_runs(db: Session, limit: int = 20) -> list[dict]:
    rows = db.query(InsightRun).order_by(InsightRun.id.desc()).limit(max(1, min(limit, 50))).all()
    return [{"id": r.id, "period_label": r.period_label, "status": r.status.value, "created_at": r.created_at,
             "models_used": r.models_used or [], "headline": (r.report or {}).get("headline"), "job_id": r.job_id}
            for r in rows]


def running_job(db: Session) -> dict | None:
    job = (db.query(Job).filter(Job.type == JobType.INSIGHTS_RUN, Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]))
           .order_by(Job.created_at.desc()).first())
    return job_service.job_out(job) if job else None

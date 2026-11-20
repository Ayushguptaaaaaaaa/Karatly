"""Dashboard, alerts, reports, reorder, settings, SSE events and jobs routes."""
from __future__ import annotations

import asyncio
import json
from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import Field
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.api.routes.periods import period_dep
from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.errors import AppError
from app.core.events import bus
from app.models import User
from app.schemas.common import In
from app.services import (
    dashboard_service,
    data_version_service,
    job_service,
    period_service,
    reorder_service,
    report_service,
    settings_service,
)

router = APIRouter()


@router.get("/dashboard/overview", tags=["dashboard"])
def dashboard_overview(p: period_service.Period = Depends(period_dep), db: Session = Depends(get_db),
                       _: User = CurrentUser):
    return dashboard_service.overview(db, p)


@router.get("/alerts", tags=["dashboard"])
def get_alerts(status: str | None = None, category_id: int | None = None, db: Session = Depends(get_db),
               _: User = CurrentUser):
    statuses = [s.strip().upper() for s in status.split(",")] if status else None
    return dashboard_service.alerts(db, statuses, category_id)


# ---- reports ------------------------------------------------------------------
@router.get("/reports/sales-trend", tags=["reports"])
def r_sales_trend(months: int = 12, category_id: int | None = None, group_by: str = "total",
                  db: Session = Depends(get_db), _: User = CurrentUser):
    return report_service.sales_trend(db, months, category_id, group_by)


@router.get("/reports/category-breakdown", tags=["reports"])
def r_breakdown(p: period_service.Period = Depends(period_dep), db: Session = Depends(get_db), _: User = CurrentUser):
    return report_service.category_breakdown(db, p)


@router.get("/reports/top-sellers", tags=["reports"])
def r_top(p: period_service.Period = Depends(period_dep), limit: int = 10, order: str = "desc",
          db: Session = Depends(get_db), _: User = CurrentUser):
    return report_service.top_sellers(db, p, limit, order)


@router.get("/reports/period-comparison", tags=["reports"])
def r_compare(period_type: str = "month", anchor_a: date | None = None, anchor_b: date | None = None,
              group_by: str = "category", db: Session = Depends(get_db), _: User = CurrentUser):
    a = period_service.resolve(db, period_type, anchor_a)
    b = period_service.resolve(db, period_type, anchor_b) if anchor_b else period_service.previous(db, a)
    return report_service.period_comparison(db, a, b, group_by)


@router.get("/reports/profitability", tags=["reports"])
def r_profitability(p: period_service.Period = Depends(period_dep), group_by: str = "category",
                    category_id: int | None = None, subcategory_id: int | None = None, limit: int = 500,
                    db: Session = Depends(get_db), _: User = CurrentUser):
    from app.services import profit_service

    if group_by not in ("category", "subcategory", "design"):
        raise AppError("VALIDATION_ERROR", "group_by must be category, subcategory or design", 422)
    return profit_service.profitability(db, p, group_by, category_id, subcategory_id, limit)


@router.get("/reports/dead-stock", tags=["reports"])
def r_dead(db: Session = Depends(get_db), _: User = CurrentUser):
    return report_service.dead_stock(db)


@router.get("/reports/stock-turnover", tags=["reports"])
def r_turnover(p: period_service.Period = Depends(period_dep), db: Session = Depends(get_db), _: User = CurrentUser):
    return report_service.stock_turnover(db, p)


@router.get("/reports/export", tags=["reports"])
def r_export(report: str, p: period_service.Period = Depends(period_dep), category_id: int | None = None,
             status: str | None = None, order: str | None = None, plan_id: int | None = None,
             group_by: str = "category",
             db: Session = Depends(get_db), _: User = CurrentUser):
    if report == "purchase_plan":
        from app.services import purchase_plan_service

        if not plan_id:
            raise AppError("VALIDATION_ERROR", "plan_id is required", 422)
        fname, data = purchase_plan_service.export_xlsx(db, plan_id)
    else:
        fname, data = report_service.export(db, report, p, category_id=category_id, status=status, order=order,
                                            group_by=group_by)
    return StreamingResponse(iter([data]),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{fname.replace(" ", "_")}"'})


@router.get("/reorder/baseline", tags=["reorder"])
def reorder_baseline(category_id: int | None = None, db: Session = Depends(get_db), _: User = CurrentUser):
    return reorder_service.baseline(db, category_id)


# ---- settings -------------------------------------------------------------------
class SettingsPatch(In):
    shop_name: str | None = Field(default=None, max_length=80)
    owner_name: str | None = Field(default=None, max_length=80)
    inflation_pct_global: float | None = None
    default_min_stock: int | None = None
    dead_stock_days: int | None = None
    reorder_cover_months: float | None = None
    quarter_system: str | None = None
    monthly_purchase_budget: float | None = None
    max_stock_multiple: float | None = None
    shop_address: str | None = Field(default=None, max_length=200)
    shop_phone: str | None = Field(default=None, max_length=30)
    shop_gstin: str | None = Field(default=None, max_length=20)
    gst_pct: float | None = None


@router.get("/settings", tags=["settings"])
def get_settings_route(db: Session = Depends(get_db), _: User = CurrentUser):
    return settings_service.get_all(db)


@router.patch("/settings", tags=["settings"])
def patch_settings(body: SettingsPatch, db: Session = Depends(get_db), user: User = CurrentUser):
    settings_service.update(db, user, body.model_dump(exclude_unset=True))
    ev = data_version_service.bump(db, "settings", "update")
    db.commit()
    data_version_service.publish(ev)
    return settings_service.get_all(db)


@router.get("/settings/ai-status", tags=["settings"])
def ai_status(_: User = CurrentUser):
    from app.ai.llm import model_manager

    return model_manager.status()


# ---- jobs + SSE -----------------------------------------------------------------
@router.get("/jobs/{job_id}", tags=["jobs"])
def get_job(job_id: str, db: Session = Depends(get_db), _: User = CurrentUser):
    job = job_service.get(db, job_id)
    if not job:
        raise AppError("JOB_NOT_FOUND", "Job not found", 404)
    return job_service.job_out(job)


def _sse(event: str, data) -> dict:
    return {"event": event, "data": json.dumps(data, default=str)}


@router.get("/jobs/{job_id}/events", tags=["jobs"])
async def job_events(job_id: str, request: Request, db: Session = Depends(get_db), _: User = CurrentUser):
    job = job_service.get(db, job_id)
    if not job:
        raise AppError("JOB_NOT_FOUND", "Job not found", 404)
    topic = f"job:{job_id}"
    queue = bus.subscribe(topic)
    snapshot = job_service.job_out(job)
    db.close()

    async def gen():
        try:
            yield _sse("snapshot", snapshot)
            if snapshot["status"] in ("SUCCEEDED", "FAILED"):
                yield _sse("done" if snapshot["status"] == "SUCCEEDED" else "error",
                           {"status": snapshot["status"], "result_type": snapshot["result_type"],
                            "result_id": snapshot["result_id"], "message": snapshot["error"]})
                return
            while True:
                if await request.is_disconnected():
                    return
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield {"comment": "keep-alive"}
                    continue
                yield _sse(item["event"], item["data"])
                if item["event"] in ("done", "error"):
                    return
        finally:
            bus.unsubscribe(topic, queue)

    return EventSourceResponse(gen(), ping=15)


@router.get("/events/stream", tags=["jobs"])
async def global_events(request: Request, db: Session = Depends(get_db), _: User = CurrentUser):
    queue = bus.subscribe("global")
    dv = data_version_service.current(db)
    db.close()

    async def gen():
        try:
            yield _sse("hello", {"data_version": dv})
            while True:
                if await request.is_disconnected():
                    return
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=20)
                except asyncio.TimeoutError:
                    yield _sse("ping", {})
                    continue
                yield _sse(item["event"], item["data"])
        finally:
            bus.unsubscribe("global", queue)

    return EventSourceResponse(gen(), ping=20)

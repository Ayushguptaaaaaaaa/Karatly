"""CrewAI Flow: prepare → stock+demand → audit → plan → report → save. Each step degrades gracefully."""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel

from app.ai import fallbacks
from app.ai.analysis_pack import build_pack
from app.ai.crews.audit_crew.crew import AuditCrew
from app.ai.crews.inventory_analysis_crew.crew import InventoryAnalysisCrew
from app.ai.crews.purchase_planning_crew.crew import PurchasePlanningCrew
from app.ai.crews.reporting_crew.crew import ReportingCrew
from app.ai.outputs import (
    AnomalyOutput,
    BudgetOutput,
    DemandOutput,
    InsightsReport,
    ReorderOutput,
    StockPositionOutput,
)
from app.ai.runner import run_crew_step
from app.core.clock import now_utc
from app.core.database import SessionLocal
from app.models import InsightRun
from app.models.enums import RunStatus
from app.services import costing_service, job_service, period_service, purchase_plan_service

log = logging.getLogger("app.ai.flow")

STEPS = [
    ("prepare", "Preparing your shop data"),
    ("stock", "Analysing stock levels"),
    ("demand", "Understanding demand and trends"),
    ("audit", "Checking records for anything unusual"),
    ("plan", "Planning purchases and budget"),
    ("report", "Writing the accountant's conclusion"),
    ("save", "Saving insights"),
]


def _j(obj) -> str:
    return json.dumps(obj, default=str, separators=(",", ":"), ensure_ascii=False)


class InsightsState(BaseModel):
    run_id: int = 0
    job_id: str = ""
    user_id: int | None = None
    period_type: str = "month"
    anchor: str = ""
    pack: dict[str, Any] = {}
    outputs: dict[str, Any] = {}
    models: list[str] = []
    plan_id: int | None = None
    plan_total: float | None = None


class InsightsFlow(Flow[InsightsState]):
    def _period(self, db):
        return period_service.resolve(db, self.state.period_type, date.fromisoformat(self.state.anchor))

    def _base_inputs(self) -> dict:
        p = self.state.pack
        return {"shop_name": p["shop"]["name"], "period_label": p["period"]["label"],
                "upcoming_season": p.get("upcoming_season", "")}

    def _note(self, model: str):
        if model not in self.state.models:
            self.state.models.append(model)

    @start()
    def prepare(self):
        job_service.update_step(self.state.job_id, "prepare", "RUNNING")
        with SessionLocal() as db:
            pack = build_pack(db, self._period(db))
            run = db.get(InsightRun, self.state.run_id)
            run.analysis_pack = {k: v for k, v in pack.items() if k != "_facts"} | {"_facts": pack["_facts"]}
            db.commit()
        self.state.pack = pack
        job_service.update_step(self.state.job_id, "prepare", "DONE", model_used="system")

    @listen(prepare)
    def stock_and_demand(self):
        pack = self.state.pack
        lean = {k: v for k, v in pack.items() if k not in ("_facts", "reorder_baseline", "anomaly_candidates")}

        def on_task(key):
            if key == "stock":
                job_service.update_step(self.state.job_id, "stock", "DONE")
                job_service.update_step(self.state.job_id, "demand", "RUNNING")

        outs, model = run_crew_step(
            job_id=self.state.job_id, step_keys=["stock", "demand"],
            build_crew=lambda llm, sc, tc: InventoryAnalysisCrew(llm, sc, tc),
            inputs={**self._base_inputs(), "analysis_pack": _j(lean)},
            output_models=[StockPositionOutput, DemandOutput],
            fallback=lambda: [fallbacks.stock_position(pack), fallbacks.demand(pack)],
            task_callback=on_task,
        )
        self.state.outputs["stock_position"] = outs[0].model_dump()
        self.state.outputs["demand"] = outs[1].model_dump()
        self._note(model)

    @listen(stock_and_demand)
    def audit(self):
        pack = self.state.pack
        if not pack["anomaly_candidates"]:
            job_service.update_step(self.state.job_id, "audit", "RUNNING")
            self.state.outputs["anomalies"] = AnomalyOutput(summary="No unusual entries found.", items=[]).model_dump()
            job_service.update_step(self.state.job_id, "audit", "DONE", model_used="system",
                                    note="Nothing unusual to review")
            return
        outs, model = run_crew_step(
            job_id=self.state.job_id, step_keys=["audit"],
            build_crew=lambda llm, sc, tc: AuditCrew(llm, sc, tc),
            inputs={**self._base_inputs(), "anomaly_candidates": _j(pack["anomaly_candidates"])},
            output_models=[AnomalyOutput], fallback=lambda: [fallbacks.anomalies(pack)],
        )
        self.state.outputs["anomalies"] = outs[0].model_dump()
        self._note(model)

    @listen(audit)
    def plan(self):
        pack = self.state.pack
        if not pack["reorder_baseline"]:
            job_service.update_step(self.state.job_id, "plan", "RUNNING")
            self.state.outputs["reorder"] = ReorderOutput(summary="Nothing needs restocking right now.").model_dump()
            self.state.outputs["budget"] = BudgetOutput(notes="No purchases needed.").model_dump()
            job_service.update_step(self.state.job_id, "plan", "DONE", model_used="system",
                                    note="Nothing to restock")
            return
        demand = self.state.outputs.get("demand", {})
        outs, model = run_crew_step(
            job_id=self.state.job_id, step_keys=["plan"],
            build_crew=lambda llm, sc, tc: PurchasePlanningCrew(llm, sc, tc),
            inputs={**self._base_inputs(), "reorder_baseline": _j(pack["reorder_baseline"]),
                    "demand_summary": demand.get("summary", "")},
            output_models=[ReorderOutput, BudgetOutput],
            fallback=lambda: [fallbacks.reorder(pack), fallbacks.budget(pack)],
        )
        reorder, ai_budget = outs[0], outs[1]
        self._note(model)
        with SessionLocal() as db:
            plan = purchase_plan_service.create_from_ai(db, self.state.user_id, self.state.run_id, self._period(db),
                                                        reorder.model_dump(), ai_budget.notes or None)
            if plan is None:  # AI returned nothing usable → baseline lines
                plan = purchase_plan_service.create_from_ai(db, self.state.user_id, self.state.run_id,
                                                            self._period(db), fallbacks.reorder(pack).model_dump(),
                                                            None)
            if plan:
                detail = purchase_plan_service.detail(db, plan.id)
                self.state.plan_id = plan.id
                self.state.plan_total = float(detail["total_estimated"])
                by_cat = [{"category": b["category"], "amount": b["amount_estimated"]} for b in detail["by_category"]]
                budget = BudgetOutput(
                    items=[{"label": i["design"]["label"], "quantity": i["final_qty"],
                            "expected_unit_cost": float(i["expected_unit_cost"]), "line_total": float(i["line_total"])}
                           for i in detail["items"]],
                    total_budget=self.state.plan_total, by_category=by_cat,
                    notes=ai_budget.notes or f"Cost = last purchase price + {pack['settings']['inflation_pct_global']}% inflation.")
            else:
                budget = BudgetOutput(notes="No purchases needed.")
        self.state.outputs["reorder"] = reorder.model_dump()
        self.state.outputs["budget"] = budget.model_dump()

    @listen(plan)
    def report(self):
        pack = self.state.pack
        o = self.state.outputs
        budget = o.get("budget", {})
        plan_summary = {"total_budget": costing_service.format_inr_compact(budget.get("total_budget", 0)),
                        "lines": len(budget.get("items", [])),
                        "top_lines": [{"label": i["label"], "qty": i["quantity"], "total": i["line_total"]}
                                      for i in budget.get("items", [])[:5]]}
        outs, model = run_crew_step(
            job_id=self.state.job_id, step_keys=["report"],
            build_crew=lambda llm, sc, tc: ReportingCrew(llm, sc, tc),
            inputs={**self._base_inputs(), "kpis": _j(pack["kpis"]),
                    "stock_summary": o.get("stock_position", {}).get("summary", ""),
                    "demand_summary": _j({k: o.get("demand", {}).get(k) for k in
                                          ("summary", "seasonal_notes", "trend_notes")}
                                         | {"high": [d["label"] for d in o.get("demand", {}).get("high_demand", [])][:8],
                                            "low": [d["label"] for d in o.get("demand", {}).get("low_demand", [])][:8]}),
                    "anomaly_summary": o.get("anomalies", {}).get("summary", ""),
                    "plan_summary": _j(plan_summary), "data_sufficiency": _j(pack["data_sufficiency"]),
                    "who_summary": _j({k: (v[:3] if isinstance(v, list) else v)
                                       for k, v in pack.get("customers_regions_dealers", {}).items()})},
            output_models=[InsightsReport],
            fallback=lambda: [fallbacks.report(pack, self.state.plan_total)],
        )
        self.state.outputs["report"] = outs[0].model_dump()
        self._note(model)

    @listen(report)
    def save(self):
        job_service.update_step(self.state.job_id, "save", "RUNNING")
        with SessionLocal() as db:
            run = db.get(InsightRun, self.state.run_id)
            o = self.state.outputs
            run.stock_position, run.demand, run.anomalies = o.get("stock_position"), o.get("demand"), o.get("anomalies")
            run.reorder, run.budget, run.report = o.get("reorder"), o.get("budget"), o.get("report")
            run.purchase_plan_id = self.state.plan_id
            run.models_used = self.state.models
            run.status = RunStatus.PARTIAL if "rule-based" in self.state.models else RunStatus.COMPLETE
            run.finished_at = now_utc()
            db.commit()
        job_service.update_step(self.state.job_id, "save", "DONE", model_used="system")
        return self.state.run_id

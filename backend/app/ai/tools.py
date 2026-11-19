"""Read-only CrewAI tools. Each opens its own DB session and returns compact JSON (≤ 6000 chars)."""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.core.database import SessionLocal
from app.services import (
    anomaly_service,
    costing_service,
    dashboard_service,
    design_service,
    metrics_service,
    period_service,
    reorder_service,
    report_service,
)

log = logging.getLogger("app.ai.tools")
MAX_CHARS = 6000

FRIENDLY = {
    "get_shop_overview": "Reading the shop overview…",
    "search_designs": "Searching designs…",
    "get_label_details": "Looking up design details…",
    "get_period_stock": "Checking stock for the period…",
    "get_sales_summary": "Adding up sales…",
    "compare_periods": "Comparing periods…",
    "get_stock_alerts": "Checking stock levels…",
    "get_demand_classification": "Checking what's selling…",
    "get_reorder_baseline": "Working out what to restock…",
    "calculate_purchase_cost": "Calculating purchase cost…",
    "get_anomaly_candidates": "Looking for unusual entries…",
    "get_sales_trend": "Reading the sales trend…",
}


def _dump(obj: Any) -> str:
    text = json.dumps(obj, default=str, separators=(",", ":"), ensure_ascii=False)
    if len(text) <= MAX_CHARS:
        return text
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, list) and len(v) > 5:
                obj = {**obj, k: v[: max(5, len(v) // 2)], "truncated": True}
                return _dump(obj)
    if isinstance(obj, list) and len(obj) > 5:
        return _dump({"items": obj[: len(obj) // 2], "truncated": True})
    return text[:MAX_CHARS]


class JsonTool(BaseTool):
    def _run(self, **kwargs) -> str:  # type: ignore[override]
        try:
            with SessionLocal() as db:
                return _dump(self.fetch(db, **kwargs))
        except Exception as e:  # tools never raise into the agent
            log.warning("Tool %s failed: %s", self.name, e)
            return json.dumps({"error": str(e)[:300]})

    def fetch(self, db, **kwargs):  # pragma: no cover - overridden
        raise NotImplementedError


def _period(db, period_type: str | None, anchor: str | None):
    a = date.fromisoformat(anchor) if anchor else None
    return period_service.resolve(db, (period_type or "month").lower(), a)


def _compact_design(item: dict) -> dict:
    return {k: item.get(k) for k in ("label", "name", "current_stock", "min_stock", "status", "demand_class",
                                     "sold_last_30d", "selling_price", "last_unit_cost")} | {
        "category": item["category"]["name"], "subcategory": (item.get("subcategory") or {}).get("name")}


class NoArgs(BaseModel):
    pass


class GetShopOverview(JsonTool):
    name: str = "get_shop_overview"
    description: str = "Shop KPIs for the current month: stock value, pieces, sales, sold-out/low/dead counts. Numbers are exact."
    args_schema: type[BaseModel] = NoArgs

    def fetch(self, db):
        ov = dashboard_service.overview(db, period_service.resolve(db, "month"))
        return {"kpis": ov["kpis"], "stock_health": ov["stock_health"], "period": ov["period"]["label"],
                "top_sellers": [{"label": t["label"], "sold": t["sold_units"], "value": t["sales_value"]}
                                for t in ov["top_sellers"]]}


class SearchArgs(BaseModel):
    query: str | None = Field(default=None, description="Text in label or name, e.g. 'ER-10' or 'jhumka'")
    category: str | None = Field(default=None, description="Category name, e.g. 'Earrings'")
    status: str | None = Field(default=None, description="IN, LOW, OUT or DEAD")
    demand: str | None = Field(default=None, description="HIGH, STEADY, LOW, DEAD or NEW")
    limit: int = Field(default=15, ge=1, le=20)


def _cat_id(db, name: str | None) -> int | None:
    if not name:
        return None
    from app.models import Category

    c = db.query(Category).filter(Category.name_key == " ".join(name.strip().lower().split())).first()
    if not c:
        c = db.query(Category).filter(Category.name.ilike(f"%{name.strip()}%")).first()
    return c.id if c else -1


class SearchDesigns(JsonTool):
    name: str = "search_designs"
    description: str = "Find designs by text, category, stock status or demand class. Returns stock and sales per design."
    args_schema: type[BaseModel] = SearchArgs

    def fetch(self, db, query=None, category=None, status=None, demand=None, limit=15):
        res = design_service.list_designs(db, category_id=_cat_id(db, category), search=query,
                                          statuses=[status.upper()] if status else None,
                                          demands=[demand.upper()] if demand else None,
                                          sort="-sold_last_30d", page_size=limit)
        return {"total": res["total"], "items": [_compact_design(i) for i in res["items"]]}


class LabelArgs(BaseModel):
    label: str = Field(description="Design label, e.g. ER-1012")


class GetLabelDetails(JsonTool):
    name: str = "get_label_details"
    description: str = "Full details of one design label: stock, status, demand, prices, last 10 entries, 6-month sales."
    args_schema: type[BaseModel] = LabelArgs

    def fetch(self, db, label):
        d = design_service.by_label(db, label)
        h = design_service.history(db, d["id"], 6)
        return {"design": {k: d[k] for k in ("label", "name", "current_stock", "min_stock", "status", "demand_class",
                                             "sold_last_30d", "velocity_30d", "days_since_last_sale", "selling_price",
                                             "last_unit_cost", "metal", "purity")} | {"category": d["category"]["name"]},
                "monthly": [{"month": m["month"], "sold": m["sold"], "received": m["received"]} for m in h["monthly"]],
                "last_entries": [{"date": m["occurred_on"], "type": m["type"], "qty": m["quantity"], "void": m["is_void"]}
                                 for m in h["movements"][:10]]}


class PeriodArgs(BaseModel):
    period_type: str = Field(default="month", description="month or quarter")
    anchor: str | None = Field(default=None, description="Any date inside the period, YYYY-MM-DD. Default today.")
    category: str | None = Field(default=None, description="Optional category name")


class GetPeriodStock(JsonTool):
    name: str = "get_period_stock"
    description: str = "Opening, received, sold and closing stock per design for a month or quarter (top 40 by sold)."
    args_schema: type[BaseModel] = PeriodArgs

    def fetch(self, db, period_type="month", anchor=None, category=None):
        from app.api.routes.periods import period_stock

        p = _period(db, period_type, anchor)
        data = period_stock(db, p, _cat_id(db, category), None, None, None, "-sold", 1, 40)
        return {"period": p.label, "totals": data["totals"],
                "rows": [{"label": r["design"]["label"], "category": r["design"]["category_name"],
                          "opening": r["opening"] + r["opening_added"], "received": r["received"], "sold": r["sold"],
                          "closing": r["closing"]} for r in data["rows"]["items"]]}


class SalesArgs(BaseModel):
    period_type: str = Field(default="month", description="month or quarter")
    anchor: str | None = Field(default=None, description="Any date in the period, YYYY-MM-DD")
    group_by: str = Field(default="category", description="category, subcategory or design")
    limit: int = Field(default=15, ge=1, le=20)


class GetSalesSummary(JsonTool):
    name: str = "get_sales_summary"
    description: str = "Sales (pieces and ₹) in a month/quarter grouped by category, subcategory or design."
    args_schema: type[BaseModel] = SalesArgs

    def fetch(self, db, period_type="month", anchor=None, group_by="category", limit=15):
        p = _period(db, period_type, anchor)
        snap = metrics_service.snapshot(db)
        sales = metrics_service.sales_by_design(db, p.start, p.effective_end)
        groups: dict[str, list] = {}
        for did, (q, v) in sales.items():
            d = snap.designs.get(did)
            if not d:
                continue
            key = (d.label if group_by == "design" else
                   (d.subcategory.name if group_by == "subcategory" and d.subcategory else d.category.name))
            g = groups.setdefault(key, [0, 0.0])
            g[0] += q
            g[1] += float(v)
        rows = sorted(({"name": k, "pieces": v[0], "value": round(v[1], 2)} for k, v in groups.items()),
                      key=lambda r: -r["value"])
        return {"period": p.label, "total_pieces": sum(r["pieces"] for r in rows),
                "total_value": round(sum(r["value"] for r in rows), 2), "rows": rows[:limit]}


class CompareArgs(BaseModel):
    period_type: str = Field(default="month", description="month or quarter")
    anchor_a: str | None = Field(default=None, description="Date in the first period (default: current)")
    anchor_b: str | None = Field(default=None, description="Date in the second period (default: the one before)")
    group_by: str = Field(default="category", description="category or design")


class ComparePeriods(JsonTool):
    name: str = "compare_periods"
    description: str = "Compare sales of two months/quarters, grouped by category or design."
    args_schema: type[BaseModel] = CompareArgs

    def fetch(self, db, period_type="month", anchor_a=None, anchor_b=None, group_by="category"):
        a = _period(db, period_type, anchor_a)
        b = _period(db, period_type, anchor_b) if anchor_b else period_service.previous(db, a)
        res = report_service.period_comparison(db, a, b, group_by)
        res["rows"] = res["rows"][:20]
        return res


class StatusArgs(BaseModel):
    status: str | None = Field(default=None, description="OUT, LOW or DEAD (default: all three)")


class GetStockAlerts(JsonTool):
    name: str = "get_stock_alerts"
    description: str = "Designs that are sold out (OUT), low (LOW) or not selling (DEAD), with demand and value tied up."
    args_schema: type[BaseModel] = StatusArgs

    def fetch(self, db, status=None):
        rows = dashboard_service.alerts(db, [status.upper()] if status else None)
        return {"count": len(rows), "items": [{k: r[k] for k in ("label", "category_name", "status", "current_stock",
                                                                "min_stock", "demand_class", "sold_last_30d",
                                                                "days_since_last_sale", "value_tied_up")}
                                              for r in rows[:30]]}


class DemandArgs(BaseModel):
    category: str | None = None
    demand_class: str | None = Field(default=None, description="HIGH, STEADY, LOW, DEAD or NEW")


class GetDemandClassification(JsonTool):
    name: str = "get_demand_classification"
    description: str = "System-computed demand class per design (HIGH/STEADY/LOW/DEAD/NEW) with sales velocity."
    args_schema: type[BaseModel] = DemandArgs

    def fetch(self, db, category=None, demand_class=None):
        res = design_service.list_designs(db, category_id=_cat_id(db, category),
                                          demands=[demand_class.upper()] if demand_class else None,
                                          sort="-sold_last_30d", page_size=30)
        snap = metrics_service.snapshot(db)
        return {"total": res["total"], "items": [
            {"label": i["label"], "category": i["category"]["name"], "demand": i["demand_class"],
             "sold_30d": i["sold_last_30d"], "velocity_30d": snap.states[i["id"]].velocity_30d,
             "stock": i["current_stock"]} for i in res["items"]]}


class CategoryArgs(BaseModel):
    category: str | None = None


class GetReorderBaseline(JsonTool):
    name: str = "get_reorder_baseline"
    description: str = "The system's rule-based restock suggestions with exact quantities, costs and total budget."
    args_schema: type[BaseModel] = CategoryArgs

    def fetch(self, db, category=None):
        base = reorder_service.baseline(db, _cat_id(db, category))
        return {"total_estimated": base["total_estimated"], "by_category": base["by_category"],
                "items": [{"label": i["design"]["label"], "category": i["design"]["category_name"],
                           "stock": i["current_stock"], "suggested_qty": i["suggested_qty"], "priority": i["priority"],
                           "expected_unit_cost": i["expected_unit_cost"], "line_total": i["line_total"],
                           "reason": i["reason"]} for i in base["items"][:30]]}


class CostArgs(BaseModel):
    label: str = Field(description="Design label, e.g. ER-1012")
    quantity: int = Field(ge=1, le=10000, description="Pieces to buy")


class CalculatePurchaseCost(JsonTool):
    name: str = "calculate_purchase_cost"
    description: str = "Exact expected purchase cost for a label and quantity (last cost + inflation %). Always use this instead of doing arithmetic."
    args_schema: type[BaseModel] = CostArgs

    def fetch(self, db, label, quantity):
        return costing_service.calculate_purchase_cost(db, label, int(quantity))


class DaysArgs(BaseModel):
    days: int = Field(default=90, ge=7, le=365)


class GetAnomalyCandidates(JsonTool):
    name: str = "get_anomaly_candidates"
    description: str = "Rule-detected unusual entries (big sales, cost jumps, price below cost, frequent undo…)."
    args_schema: type[BaseModel] = DaysArgs

    def fetch(self, db, days=90):
        return {"items": anomaly_service.candidates(db, days)}


class TrendArgs(BaseModel):
    months: int = Field(default=12, ge=1, le=24)
    category: str | None = None


class GetSalesTrend(JsonTool):
    name: str = "get_sales_trend"
    description: str = "Monthly sales (pieces and ₹) for the last N months, optionally for one category."
    args_schema: type[BaseModel] = TrendArgs

    def fetch(self, db, months=12, category=None):
        cid = _cat_id(db, category)
        res = report_service.sales_trend(db, months, cid if cid and cid > 0 else None, "total")
        return {"category": category or "all", "points": res["series"][0]["points"] if res["series"] else []}


def all_tools() -> list[BaseTool]:
    return [GetShopOverview(), SearchDesigns(), GetLabelDetails(), GetPeriodStock(), GetSalesSummary(),
            ComparePeriods(), GetStockAlerts(), GetDemandClassification(), GetReorderBaseline(),
            CalculatePurchaseCost(), GetAnomalyCandidates(), GetSalesTrend()]

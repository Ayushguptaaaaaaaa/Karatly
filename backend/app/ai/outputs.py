"""Pydantic output models for every CrewAI task."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["HIGH", "MEDIUM", "LOW"]


class LabelNote(BaseModel):
    label: str
    category: str = ""
    stock: int = 0
    note: str = ""


class CategoryNote(BaseModel):
    category: str
    note: str


class StockPositionOutput(BaseModel):
    summary: str = Field(description="2-4 sentences on the overall stock position")
    out_of_stock: list[LabelNote] = Field(default_factory=list, description="Sold-out designs (max 15)")
    low_stock: list[LabelNote] = Field(default_factory=list, description="Low-stock designs (max 15)")
    dead_stock: list[LabelNote] = Field(default_factory=list, description="Dead stock designs (max 15)")
    category_notes: list[CategoryNote] = Field(default_factory=list)


class DemandNote(BaseModel):
    label: str
    category: str = ""
    sold_period: int = 0
    velocity_30d: float = 0
    reason: str = ""


class DemandOutput(BaseModel):
    summary: str
    high_demand: list[DemandNote] = Field(default_factory=list, description="max 10")
    low_demand: list[DemandNote] = Field(default_factory=list, description="max 10")
    seasonal_notes: list[str] = Field(default_factory=list, description="max 4")
    trend_notes: list[str] = Field(default_factory=list, description="max 4")


class AnomalyItem(BaseModel):
    label: str | None = None
    severity: Severity = "LOW"
    issue: str
    evidence: str = ""
    suggested_check: str = ""


class AnomalyOutput(BaseModel):
    summary: str
    items: list[AnomalyItem] = Field(default_factory=list, description="max 10")


class ReorderLine(BaseModel):
    label: str
    suggested_qty: int
    priority: Severity = "MEDIUM"
    reason: str = ""


class SkippedLine(BaseModel):
    label: str
    reason: str


class ReorderOutput(BaseModel):
    summary: str = ""
    items: list[ReorderLine] = Field(default_factory=list)
    skipped: list[SkippedLine] = Field(default_factory=list)


class BudgetLine(BaseModel):
    label: str
    quantity: int
    expected_unit_cost: float
    line_total: float


class CategoryAmount(BaseModel):
    category: str
    amount: float


class BudgetOutput(BaseModel):
    items: list[BudgetLine] = Field(default_factory=list)
    total_budget: float = 0
    by_category: list[CategoryAmount] = Field(default_factory=list)
    notes: str = ""


class KeyNumber(BaseModel):
    label: str
    value: str


ActionTarget = Literal["PURCHASE_PLAN", "OUT_OF_STOCK", "LOW_STOCK", "DEAD_STOCK", "ANOMALIES", "INVENTORY", "REPORTS"]


class Action(BaseModel):
    title: str
    why: str
    priority: Severity = "MEDIUM"
    target: ActionTarget = "INVENTORY"


class InsightsReport(BaseModel):
    headline: str = Field(description="<= 120 chars, plain language: what changed + biggest issue")
    conclusion: str = Field(description="3-6 sentences: the accountant's conclusion")
    confidence: Severity = "MEDIUM"
    confidence_reason: str = ""
    key_numbers: list[KeyNumber] = Field(default_factory=list, description="4-6 items")
    recommended_actions: list[Action] = Field(default_factory=list, description="3-6 items")
    whats_selling: str = ""
    whats_not_selling: str = ""
    money_view: str = ""
    risks: str = ""
    data_quality_notes: list[str] = Field(default_factory=list)


class ChartPoint(BaseModel):
    label: str
    value: float


class ChatChart(BaseModel):
    type: Literal["bar", "line", "pie"] = "bar"
    title: str = ""
    data: list[ChartPoint] = Field(default_factory=list)
    value_format: Literal["number", "inr"] = "number"


class ChatTable(BaseModel):
    columns: list[str]
    rows: list[list[str | float | int | None]]


class ChatAnswer(BaseModel):
    answer_markdown: str
    table: ChatTable | None = None
    chart: ChatChart | None = None
    follow_up_questions: list[str] = Field(default_factory=list, description="max 3 short follow-up questions")

"""Settings, purchase plans, jobs, insight runs, chat and audit log models."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._base import TimestampMixin, enum_col
from app.models.design import Design
from app.models.enums import (
    ChatRole,
    Decision,
    JobStatus,
    JobType,
    MessageStatus,
    PlanSource,
    PlanStatus,
    Priority,
    RunStatus,
)
from app.models.user import User


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class PurchasePlan(TimestampMixin, Base):
    __tablename__ = "purchase_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    status: Mapped[PlanStatus] = mapped_column(enum_col(PlanStatus), default=PlanStatus.DRAFT)
    source: Mapped[PlanSource] = mapped_column(enum_col(PlanSource), default=PlanSource.MANUAL)
    insight_run_id: Mapped[int | None] = mapped_column(ForeignKey("insight_runs.id", ondelete="SET NULL"), nullable=True)
    period_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_estimated: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_approved: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    submitted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["PurchasePlanItem"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="PurchasePlanItem.id"
    )
    creator: Mapped[User | None] = relationship(foreign_keys=[created_by])


class PurchasePlanItem(Base):
    __tablename__ = "purchase_plan_items"
    __table_args__ = (UniqueConstraint("plan_id", "design_id", name="uq_plan_design"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("purchase_plans.id", ondelete="CASCADE"), index=True)
    design_id: Mapped[int] = mapped_column(ForeignKey("designs.id", ondelete="CASCADE"))
    current_stock_at_creation: Mapped[int] = mapped_column(Integer, default=0)
    suggested_qty: Mapped[int] = mapped_column(Integer, default=0)
    final_qty: Mapped[int] = mapped_column(Integer, default=0)
    last_unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    inflation_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    expected_unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    priority: Mapped[Priority] = mapped_column(enum_col(Priority), default=Priority.MEDIUM)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[Decision] = mapped_column(enum_col(Decision), default=Decision.PENDING)
    decision_note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    received_qty: Mapped[int] = mapped_column(Integer, default=0)

    plan: Mapped[PurchasePlan] = relationship(back_populates="items")
    design: Mapped[Design] = relationship()


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[JobType] = mapped_column(enum_col(JobType))
    status: Mapped[JobStatus] = mapped_column(enum_col(JobStatus), default=JobStatus.QUEUED)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    result_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    result_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InsightRun(Base):
    __tablename__ = "insight_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    period_type: Mapped[str] = mapped_column(String(10))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    period_label: Mapped[str] = mapped_column(String(80))
    data_version: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[RunStatus] = mapped_column(enum_col(RunStatus), default=RunStatus.RUNNING)
    models_used: Mapped[list] = mapped_column(JSON, default=list)
    analysis_pack: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    stock_position: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    demand: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    anomalies: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reorder: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    budget: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    purchase_plan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChatSession(TimestampMixin, Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(80), default="New chat")

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.id"
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[ChatRole] = mapped_column(enum_col(ChatRole))
    content: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[MessageStatus] = mapped_column(enum_col(MessageStatus), default=MessageStatus.COMPLETE)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[ChatSession] = relationship(back_populates="messages")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(20))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    before: Mapped[Any] = mapped_column(JSON, nullable=True)
    after: Mapped[Any] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._base import enum_col
from app.models.design import Design
from app.models.enums import MovementSource, MovementType
from app.models.user import User


class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        Index("ix_mov_design_date", "design_id", "occurred_on"),
        Index("ix_mov_type_date", "type", "occurred_on"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    design_id: Mapped[int] = mapped_column(ForeignKey("designs.id", ondelete="CASCADE"), index=True)
    type: Mapped[MovementType] = mapped_column(enum_col(MovementType))
    quantity: Mapped[int] = mapped_column(Integer)
    signed_qty: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    occurred_on: Mapped[date] = mapped_column(Date, index=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    source: Mapped[MovementSource] = mapped_column(enum_col(MovementSource), default=MovementSource.MANUAL)
    purchase_plan_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_plan_items.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_void: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    design: Mapped[Design] = relationship()
    creator: Mapped[User | None] = relationship(foreign_keys=[created_by])

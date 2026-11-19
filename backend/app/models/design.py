from __future__ import annotations

from decimal import Decimal

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._base import TimestampMixin, enum_col
from app.models.category import Category, Subcategory
from app.models.enums import Metal


class Design(TimestampMixin, Base):
    __tablename__ = "designs"
    __table_args__ = (Index("ix_designs_cat_sub", "category_id", "subcategory_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    subcategory_id: Mapped[int | None] = mapped_column(ForeignKey("subcategories.id", ondelete="RESTRICT"), nullable=True)
    label: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metal: Mapped[Metal] = mapped_column(enum_col(Metal), default=Metal.GOLD)
    purity: Mapped[str | None] = mapped_column(String(10), nullable=True)
    weight_g: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    supplier: Mapped[str | None] = mapped_column(String(100), nullable=True)
    min_stock: Mapped[int] = mapped_column(Integer, default=3)
    inflation_pct_override: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    photo_filename: Mapped[str | None] = mapped_column(String(200), nullable=True)
    custom_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    category: Mapped[Category] = relationship()
    subcategory: Mapped[Subcategory | None] = relationship()

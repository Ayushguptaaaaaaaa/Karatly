from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._base import TimestampMixin


class Category(TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    name_key: Mapped[str] = mapped_column(String(60), unique=True)
    label_prefix: Mapped[str] = mapped_column(String(5), unique=True)
    icon: Mapped[str] = mapped_column(String(30), default="other")
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    inflation_pct_override: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    subcategories: Mapped[list["Subcategory"]] = relationship(
        back_populates="category", order_by="Subcategory.sort_order"
    )


class Subcategory(TimestampMixin, Base):
    __tablename__ = "subcategories"
    __table_args__ = (UniqueConstraint("category_id", "name_key", name="uq_subcategory_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    name_key: Mapped[str] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    category: Mapped[Category] = relationship(back_populates="subcategories")

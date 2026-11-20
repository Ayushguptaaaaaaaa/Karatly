"""Customers, dealers (suppliers) and bills.

A bill groups SALE stock movements (its lines). The customer's name and region are copied onto the bill
so reports by city / state / country stay correct even if the customer's details change later.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._base import TimestampMixin


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    name_key: Mapped[str] = mapped_column(String(120), index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    country: Mapped[str | None] = mapped_column(String(80), nullable=True, default="India")
    notes: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Dealer(TimestampMixin, Base):
    __tablename__ = "dealers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    name_key: Mapped[str] = mapped_column(String(120), index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    country: Mapped[str | None] = mapped_column(String(80), nullable=True, default="India")
    gstin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Bill(Base):
    __tablename__ = "bills"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    bill_date: Mapped[date] = mapped_column(Date, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True,
                                                    index=True)
    # snapshot at the time of sale (region filters use these)
    customer_name: Mapped[str] = mapped_column(String(120), default="Walk-in customer")
    customer_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    state: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    country: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)   # list prices × qty
    discount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    taxable: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)    # subtotal − discount (= revenue)
    gst_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    gst_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)      # amount the customer pays
    payment_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_void: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer: Mapped[Customer | None] = relationship()
    items: Mapped[list["StockMovement"]] = relationship(  # noqa: F821
        "StockMovement", back_populates="bill", order_by="StockMovement.id")

    @property
    def line_count(self) -> int:
        return len(self.items)


"""Schemas for categories, subcategories, designs, stock movements and periods."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import Demand, Metal, MovementType, StockStatus
from app.schemas.common import In, Money

Icon = Literal["necklace", "earring", "ring", "bangle", "bracelet", "anklet", "chain", "pendant", "nosepin", "set",
               "coin", "other"]


# ---- categories -------------------------------------------------------------
class CategoryCreate(In):
    name: str = Field(min_length=1, max_length=60)
    label_prefix: str | None = Field(default=None, max_length=5)
    icon: Icon = "other"
    description: str | None = Field(default=None, max_length=300)
    inflation_pct_override: float | None = Field(default=None, ge=0, le=50)
    subcategories: list[str] = Field(default_factory=list, max_length=30)


class CategoryUpdate(In):
    name: str | None = Field(default=None, max_length=60)
    label_prefix: str | None = Field(default=None, max_length=5)
    icon: Icon | None = None
    description: str | None = Field(default=None, max_length=300)
    inflation_pct_override: float | None = Field(default=None, ge=0, le=50)
    sort_order: int | None = None
    is_active: bool | None = None


class SubRef(BaseModel):
    id: int
    name: str


class SubcategoryOut(BaseModel):
    id: int
    category_id: int
    name: str
    description: str | None = None
    is_active: bool
    sort_order: int
    design_count: int | None = None
    total_pieces: int | None = None


class CategoryCard(BaseModel):
    id: int
    name: str
    label_prefix: str
    icon: str
    description: str | None = None
    is_active: bool
    sort_order: int
    inflation_pct_override: float | None = None
    subcategory_count: int
    subcategories: list[SubRef]
    design_count: int
    total_pieces: int
    stock_value_cost: Money
    in_stock_count: int
    out_of_stock_count: int
    low_stock_count: int
    dead_stock_count: int
    sold_last_30d: int


class CategoryDetail(CategoryCard):
    subcategories: list[SubcategoryOut]  # type: ignore[assignment]


class SubcategoryCreate(In):
    name: str = Field(min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=300)


class SubcategoryUpdate(In):
    name: str | None = Field(default=None, max_length=60)
    description: str | None = Field(default=None, max_length=300)
    is_active: bool | None = None
    sort_order: int | None = None


class PrefixSuggestion(BaseModel):
    prefix: str
    available: bool


# ---- designs ----------------------------------------------------------------
class CategoryRef(BaseModel):
    id: int
    name: str
    icon: str


class DesignListItem(BaseModel):
    id: int
    label: str
    name: str | None = None
    category: CategoryRef
    subcategory: SubRef | None = None
    metal: Metal
    purity: str | None = None
    weight_g: float | None = None
    cost_price: Money
    selling_price: Money
    last_unit_cost: Money
    min_stock: int
    current_stock: int
    status: StockStatus
    demand_class: Demand
    sold_last_30d: int
    stock_value_cost: Money
    photo_url: str | None = None
    is_active: bool
    updated_at: datetime | None = None


class DesignDetail(DesignListItem):
    description: str | None = None
    supplier: str | None = None
    inflation_pct_override: float | None = None
    custom_fields: dict = {}
    velocity_30d: float
    days_since_last_sale: int | None = None
    first_movement_on: date | None = None
    last_sale_on: date | None = None
    created_at: datetime | None = None


class DesignPage(BaseModel):
    items: list[DesignListItem]
    total: int
    page: int
    page_size: int


class DesignCreateRow(BaseModel):
    label: str = ""
    name: str | None = None
    metal: str | None = "GOLD"
    purity: str | None = None
    weight_g: float | str | None = None
    cost_price: float | str | None = None
    selling_price: float | str | None = None
    min_stock: int | str | None = None
    opening_stock: int | str | None = 0
    supplier: str | None = None
    description: str | None = None


class DesignBulkCreate(In):
    category_id: int
    subcategory_id: int | None = None
    opening_date: date | None = None
    designs: list[DesignCreateRow] = Field(min_length=1, max_length=100)


class DesignBulkOut(BaseModel):
    created: list[DesignListItem]


class DesignUpdate(In):
    label: str | None = None
    name: str | None = None
    description: str | None = None
    metal: Metal | None = None
    purity: str | None = None
    weight_g: float | None = Field(default=None, ge=0)
    cost_price: float | None = Field(default=None, ge=0)
    selling_price: float | None = Field(default=None, ge=0)
    supplier: str | None = None
    min_stock: int | None = Field(default=None, ge=0)
    inflation_pct_override: float | None = Field(default=None, ge=0, le=50)
    custom_fields: dict | None = None
    category_id: int | None = None
    subcategory_id: int | None = None


class LabelCheck(BaseModel):
    label: str
    valid: bool
    available: bool
    message: str | None = None


class NextLabels(BaseModel):
    labels: list[str]


class DesignSearchHit(BaseModel):
    id: int
    label: str
    name: str | None = None
    category_name: str
    current_stock: int
    status: StockStatus
    photo_url: str | None = None
    selling_price: float
    cost_price: float
    min_stock: int


class PhotoOut(BaseModel):
    photo_url: str | None


# ---- movements --------------------------------------------------------------
class DesignMini(BaseModel):
    id: int
    label: str
    name: str | None = None
    photo_url: str | None = None


class UserMini(BaseModel):
    id: int
    display_name: str


class MovementOut(BaseModel):
    id: int
    design: DesignMini
    type: MovementType
    direction: Literal["IN", "OUT"]
    quantity: int
    unit_price: Money | None = None
    value: Money | None = None
    occurred_on: date
    note: str | None = None
    source: str
    created_by: UserMini | None = None
    created_at: datetime | None = None
    is_void: bool
    voided_at: datetime | None = None
    void_reason: str | None = None


class MovementPage(BaseModel):
    items: list[MovementOut]
    total: int
    page: int
    page_size: int


class MovementCreate(In):
    design_id: int | None = None
    label: str | None = None
    type: MovementType
    quantity: int = Field(ge=1, le=100000)
    occurred_on: date | None = None
    unit_price: float | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=300)


class MovementBatch(In):
    items: list[MovementCreate] = Field(min_length=1, max_length=100)


class DesignBrief(BaseModel):
    id: int
    label: str
    current_stock: int
    status: StockStatus
    demand_class: Demand


class MovementResult(BaseModel):
    movement: MovementOut
    design: DesignBrief


class MovementBatchResult(BaseModel):
    movements: list[MovementOut]
    designs: list[DesignBrief]


class VoidIn(In):
    reason: str | None = Field(default=None, max_length=300)


class TodayTotals(BaseModel):
    sold_units: int
    sold_value: float
    received_units: int


class TodayOut(BaseModel):
    entries: list[MovementOut]
    totals: TodayTotals


class HistoryMonth(BaseModel):
    month: str
    label: str
    sold: int
    received: int
    sales_value: float


class DesignHistory(BaseModel):
    monthly: list[HistoryMonth]
    movements: list[MovementOut]

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, PlainSerializer

T = TypeVar("T")

Money = Annotated[Decimal, PlainSerializer(lambda v: float(round(Decimal(v), 2)), return_type=float, when_used="always")]


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class In(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = {}


class ErrorBody(BaseModel):
    error: ErrorDetail


PeriodType = Literal["month", "quarter", "custom"]


class PeriodOut(BaseModel):
    period_type: PeriodType
    start: date
    end: date
    effective_end: date
    label: str
    short_label: str
    is_current: bool
    previous: dict


class IdName(BaseModel):
    id: int
    name: str

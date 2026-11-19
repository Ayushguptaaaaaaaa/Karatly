from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.models import User
from app.schemas.catalog import (
    MovementBatch,
    MovementBatchResult,
    MovementCreate,
    MovementPage,
    MovementResult,
    TodayOut,
    VoidIn,
)
from app.services import stock_service

router = APIRouter(prefix="/stock", tags=["stock"])


@router.post("/movements", response_model=MovementResult, status_code=201)
def create_movement(body: MovementCreate, db: Session = Depends(get_db), user: User = CurrentUser):
    return stock_service.record(db, user, body.model_dump())


@router.post("/movements/batch", response_model=MovementBatchResult, status_code=201)
def create_batch(body: MovementBatch, db: Session = Depends(get_db), user: User = CurrentUser):
    return stock_service.record_batch(db, user, [i.model_dump() for i in body.items])


@router.get("/movements", response_model=MovementPage)
def list_movements(
    design_id: int | None = None,
    label: str | None = None,
    category_id: int | None = None,
    type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    include_void: bool = True,
    created_by: int | None = None,
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db),
    _: User = CurrentUser,
):
    types = [t.strip().upper() for t in type.split(",") if t.strip()] if type else None
    return stock_service.list_movements(
        db, design_id=design_id, label=label, category_id=category_id, types=types, date_from=date_from,
        date_to=date_to, include_void=include_void, created_by=created_by, page=page, page_size=page_size,
    )


@router.post("/movements/{movement_id}/void", response_model=MovementResult)
def void_movement(movement_id: int, body: VoidIn | None = None, db: Session = Depends(get_db),
                  user: User = CurrentUser):
    return stock_service.void(db, user, movement_id, body.reason if body else None)


@router.get("/today", response_model=TodayOut)
def today(db: Session = Depends(get_db), user: User = CurrentUser):
    return stock_service.today_entries(db, user)

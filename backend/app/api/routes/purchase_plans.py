from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from pydantic import Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, OwnerOnly
from app.models import User
from app.models.enums import Decision
from app.schemas.common import In
from app.services import purchase_plan_service as svc

router = APIRouter(prefix="/purchase-plans", tags=["purchase-plans"])


class PlanCreate(In):
    title: str | None = Field(default=None, max_length=120)
    from_baseline: bool = True
    category_id: int | None = None


class PlanPatch(In):
    title: str | None = Field(default=None, max_length=120)
    notes: str | None = None


class ItemAdd(In):
    design_id: int
    final_qty: int = Field(ge=0, le=10000)


class ItemPatch(In):
    final_qty: int | None = Field(default=None, ge=0, le=10000)
    decision: Decision | None = None
    decision_note: str | None = Field(default=None, max_length=300)


class DecisionIn(In):
    item_id: int
    decision: Decision | None = None
    final_qty: int | None = Field(default=None, ge=0, le=10000)
    decision_note: str | None = None


class DecideIn(In):
    approve_all: bool = False
    decisions: list[DecisionIn] = []


class ReceiveLine(In):
    item_id: int
    quantity: int = Field(ge=0)
    unit_cost: float | None = Field(default=None, ge=0)


class ReceiveIn(In):
    occurred_on: date | None = None
    items: list[ReceiveLine]


@router.get("")
def list_plans(status: str | None = None, db: Session = Depends(get_db), _: User = CurrentUser):
    return svc.list_plans(db, status)


@router.post("", status_code=201)
def create_plan(body: PlanCreate, db: Session = Depends(get_db), user: User = CurrentUser):
    return svc.create_from_baseline(db, user, body.title, body.category_id)


@router.get("/{plan_id}")
def get_plan(plan_id: int, db: Session = Depends(get_db), _: User = CurrentUser):
    return svc.detail(db, plan_id)


@router.patch("/{plan_id}")
def patch_plan(plan_id: int, body: PlanPatch, db: Session = Depends(get_db), user: User = CurrentUser):
    return svc.update(db, user, plan_id, body.model_dump(exclude_unset=True))


@router.post("/{plan_id}/items")
def add_item(plan_id: int, body: ItemAdd, db: Session = Depends(get_db), user: User = CurrentUser):
    return svc.add_item(db, user, plan_id, body.design_id, body.final_qty)


@router.patch("/{plan_id}/items/{item_id}")
def patch_item(plan_id: int, item_id: int, body: ItemPatch, db: Session = Depends(get_db), user: User = CurrentUser):
    return svc.update_item(db, user, plan_id, item_id, body.model_dump(exclude_unset=True))


@router.delete("/{plan_id}/items/{item_id}")
def delete_item(plan_id: int, item_id: int, db: Session = Depends(get_db), user: User = CurrentUser):
    return svc.remove_item(db, user, plan_id, item_id)


@router.post("/{plan_id}/submit")
def submit(plan_id: int, db: Session = Depends(get_db), user: User = CurrentUser):
    return svc.submit(db, user, plan_id)


@router.post("/{plan_id}/decide")
def decide(plan_id: int, body: DecideIn, db: Session = Depends(get_db), user: User = OwnerOnly):
    return svc.decide(db, user, plan_id, body.approve_all, [d.model_dump() for d in body.decisions])


@router.post("/{plan_id}/receive")
def receive(plan_id: int, body: ReceiveIn, db: Session = Depends(get_db), user: User = CurrentUser):
    return svc.receive(db, user, plan_id, body.occurred_on, [i.model_dump() for i in body.items])


@router.delete("/{plan_id}", status_code=204)
def delete_plan(plan_id: int, db: Session = Depends(get_db), user: User = CurrentUser):
    svc.delete(db, user, plan_id)
    return Response(status_code=204)


@router.get("/{plan_id}/export")
def export_plan(plan_id: int, db: Session = Depends(get_db), _: User = CurrentUser):
    fname, data = svc.export_xlsx(db, plan_id)
    return StreamingResponse(iter([data]),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})

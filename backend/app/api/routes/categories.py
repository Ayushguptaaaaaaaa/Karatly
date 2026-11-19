from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.models import User
from app.schemas.catalog import (
    CategoryCard,
    CategoryCreate,
    CategoryDetail,
    CategoryUpdate,
    PrefixSuggestion,
    SubcategoryCreate,
    SubcategoryOut,
    SubcategoryUpdate,
)
from app.services import category_service
from app.services.serializers import subcategory_out

router = APIRouter(tags=["categories"])


@router.get("/categories", response_model=list[CategoryCard])
def list_categories(include_inactive: bool = False, db: Session = Depends(get_db), _: User = CurrentUser):
    return category_service.cards(db, include_inactive)


@router.get("/categories/suggest-prefix", response_model=PrefixSuggestion)
def suggest_prefix(name: str, db: Session = Depends(get_db), _: User = CurrentUser):
    return {"prefix": category_service.suggest_prefix(db, name), "available": True}


@router.post("/categories", response_model=CategoryDetail, status_code=201)
def create_category(body: CategoryCreate, db: Session = Depends(get_db), user: User = CurrentUser):
    c = category_service.create(db, user, body.model_dump())
    return category_service.card(db, c.id)


@router.get("/categories/{category_id}", response_model=CategoryDetail)
def get_category(category_id: int, db: Session = Depends(get_db), _: User = CurrentUser):
    return category_service.card(db, category_id)


@router.patch("/categories/{category_id}", response_model=CategoryDetail)
def update_category(category_id: int, body: CategoryUpdate, db: Session = Depends(get_db), user: User = CurrentUser):
    category_service.update(db, user, category_id, body.model_dump(exclude_unset=True))
    return category_service.card(db, category_id)


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: int, db: Session = Depends(get_db), user: User = CurrentUser):
    category_service.delete(db, user, category_id)
    return Response(status_code=204)


@router.get("/categories/{category_id}/subcategories", response_model=list[SubcategoryOut])
def list_subcategories(category_id: int, db: Session = Depends(get_db), _: User = CurrentUser):
    return [subcategory_out(s) for s in category_service.list_subs(db, category_id)]


@router.post("/categories/{category_id}/subcategories", response_model=SubcategoryOut, status_code=201)
def create_subcategory(category_id: int, body: SubcategoryCreate, db: Session = Depends(get_db),
                       user: User = CurrentUser):
    return subcategory_out(category_service.create_sub(db, user, category_id, body.name, body.description))


@router.patch("/subcategories/{sub_id}", response_model=SubcategoryOut)
def update_subcategory(sub_id: int, body: SubcategoryUpdate, db: Session = Depends(get_db), user: User = CurrentUser):
    return subcategory_out(category_service.update_sub(db, user, sub_id, body.model_dump(exclude_unset=True)))


@router.delete("/subcategories/{sub_id}", status_code=204)
def delete_subcategory(sub_id: int, db: Session = Depends(get_db), user: User = CurrentUser):
    category_service.delete_sub(db, user, sub_id)
    return Response(status_code=204)

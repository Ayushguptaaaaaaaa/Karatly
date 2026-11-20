from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.models import User
from app.schemas.catalog import (
    DesignBulkCreate,
    DesignBulkOut,
    DesignDetail,
    DesignHistory,
    DesignPage,
    DesignSearchHit,
    DesignUpdate,
    LabelCheck,
    NextLabels,
    PhotoOut,
)
from app.services import design_service, import_export_service, metrics_service
from app.services.serializers import design_list_item

router = APIRouter(prefix="/designs", tags=["designs"])


def _csv(v: str | None) -> list[str] | None:
    return [x.strip().upper() for x in v.split(",") if x.strip()] if v else None


@router.get("", response_model=DesignPage)
def list_designs(
    category_id: int | None = None,
    subcategory_id: int | None = None,
    status: str | None = Query(default=None, description="Comma list of IN,LOW,OUT,DEAD"),
    demand: str | None = Query(default=None, description="Comma list of HIGH,STEADY,LOW,DEAD,NEW"),
    search: str | None = None,
    include_inactive: bool = False,
    sort: str = "label",
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db),
    _: User = CurrentUser,
):
    return design_service.list_designs(
        db, category_id=category_id, subcategory_id=subcategory_id, statuses=_csv(status), demands=_csv(demand),
        search=search, include_inactive=include_inactive, sort=sort, page=page, page_size=page_size,
    )


@router.get("/next-labels", response_model=NextLabels)
def next_labels(category_id: int, count: int = 10, db: Session = Depends(get_db), _: User = CurrentUser):
    return {"labels": design_service.next_labels(db, category_id, count)}


@router.get("/check-label", response_model=LabelCheck)
def check_label(label: str, exclude_id: int | None = None, db: Session = Depends(get_db), _: User = CurrentUser):
    return design_service.check_label(db, label, exclude_id)


@router.get("/search", response_model=list[DesignSearchHit])
def search(q: str = "", limit: int = 8, db: Session = Depends(get_db), _: User = CurrentUser):
    return design_service.search(db, q, limit)


@router.get("/{design_id}/parties")
def design_parties(design_id: int, db: Session = Depends(get_db), _: User = CurrentUser):
    """Who supplied this design and who bought it (all time)."""
    from app.services import explorer_service

    design_service.get(db, design_id)
    return explorer_service.parties_for_design(db, design_id)


@router.get("/import-template")
def import_template(_: User = CurrentUser):
    data = import_export_service.template_xlsx()
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="designs_import_template.xlsx"'},
    )


@router.post("/import")
async def import_designs(dry_run: bool = True, file: UploadFile = File(...), db: Session = Depends(get_db),
                         user: User = CurrentUser):
    content = await file.read()
    return import_export_service.import_designs(db, user, content, dry_run)


@router.post("/bulk", response_model=DesignBulkOut, status_code=201)
def bulk_create(body: DesignBulkCreate, db: Session = Depends(get_db), user: User = CurrentUser):
    created = design_service.bulk_create(db, user, body.category_id, body.subcategory_id,
                                         [r.model_dump() for r in body.designs], body.opening_date)
    snap = metrics_service.snapshot(db)
    return {"created": [design_list_item(snap.designs[d.id], snap.states[d.id]) for d in created]}


@router.get("/by-label/{label}", response_model=DesignDetail)
def by_label(label: str, db: Session = Depends(get_db), _: User = CurrentUser):
    return design_service.by_label(db, label)


@router.get("/{design_id}", response_model=DesignDetail)
def get_design(design_id: int, db: Session = Depends(get_db), _: User = CurrentUser):
    return design_service.detail(db, design_id)


@router.patch("/{design_id}", response_model=DesignDetail)
def update_design(design_id: int, body: DesignUpdate, db: Session = Depends(get_db), user: User = CurrentUser):
    return design_service.update(db, user, design_id, body.model_dump(exclude_unset=True))


@router.post("/{design_id}/archive", response_model=DesignDetail)
def archive(design_id: int, db: Session = Depends(get_db), user: User = CurrentUser):
    return design_service.set_active(db, user, design_id, False)


@router.post("/{design_id}/unarchive", response_model=DesignDetail)
def unarchive(design_id: int, db: Session = Depends(get_db), user: User = CurrentUser):
    return design_service.set_active(db, user, design_id, True)


@router.delete("/{design_id}", status_code=204)
def delete_design(design_id: int, db: Session = Depends(get_db), user: User = CurrentUser):
    design_service.delete(db, user, design_id)
    return Response(status_code=204)


@router.post("/{design_id}/photo", response_model=PhotoOut)
async def upload_photo(design_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                       user: User = CurrentUser):
    data = await file.read()
    return design_service.save_photo(db, user, design_id, file.content_type or "", data)


@router.delete("/{design_id}/photo", status_code=204)
def delete_photo(design_id: int, db: Session = Depends(get_db), user: User = CurrentUser):
    design_service.delete_photo(db, user, design_id)
    return Response(status_code=204)


@router.get("/{design_id}/history", response_model=DesignHistory)
def history(design_id: int, months: int = 12, db: Session = Depends(get_db), _: User = CurrentUser):
    return design_service.history(db, design_id, months)

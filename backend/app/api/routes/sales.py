"""Customers, dealers, bills and the sales / purchases explorer."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from pydantic import Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.models import User
from app.models.enums import Metal
from app.schemas.common import In
from app.services import billing_service, contacts_service, explorer_service

router = APIRouter(tags=["sales"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class CustomerIn(In):
    name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=80)
    state: str | None = Field(default=None, max_length=80)
    country: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=300)


class DealerIn(In):
    name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=80)
    state: str | None = Field(default=None, max_length=80)
    country: str | None = Field(default=None, max_length=80)
    gstin: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=300)


class BillLineIn(In):
    design_id: int | None = None
    label: str | None = None
    quantity: int = Field(ge=1, le=100000)
    unit_price: float | None = Field(default=None, ge=0)


class BillIn(In):
    customer_id: int | None = None
    customer: CustomerIn | None = None
    bill_date: date | None = None
    items: list[BillLineIn] = Field(min_length=1, max_length=100)
    discount: float = Field(default=0, ge=0)
    gst_pct: float | None = Field(default=None, ge=0, le=28)
    payment_mode: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=300)


class VoidBillIn(In):
    reason: str | None = Field(default=None, max_length=300)


# ---------------------------------------------------------------- customers
@router.get("/customers")
def list_customers(q: str | None = None, db: Session = Depends(get_db), _: User = CurrentUser):
    return contacts_service.list_customers(db, q)


@router.post("/customers", status_code=201)
def create_customer(body: CustomerIn, db: Session = Depends(get_db), user: User = CurrentUser):
    c = contacts_service.create_customer(db, user, body.model_dump(exclude_unset=True))
    return contacts_service.customer_out(c)


@router.patch("/customers/{cid}")
def update_customer(cid: int, body: CustomerIn, db: Session = Depends(get_db), user: User = CurrentUser):
    return contacts_service.update_customer(db, user, cid, body.model_dump(exclude_unset=True))


@router.delete("/customers/{cid}", status_code=204)
def delete_customer(cid: int, db: Session = Depends(get_db), user: User = CurrentUser):
    contacts_service.delete_customer(db, user, cid)
    return Response(status_code=204)


# ---------------------------------------------------------------- dealers
@router.get("/dealers")
def list_dealers(q: str | None = None, db: Session = Depends(get_db), _: User = CurrentUser):
    return contacts_service.list_dealers(db, q)


@router.post("/dealers", status_code=201)
def create_dealer(body: DealerIn, db: Session = Depends(get_db), user: User = CurrentUser):
    d = contacts_service.create_dealer(db, user, body.model_dump(exclude_unset=True))
    return contacts_service.dealer_out(d)


@router.patch("/dealers/{did}")
def update_dealer(did: int, body: DealerIn, db: Session = Depends(get_db), user: User = CurrentUser):
    return contacts_service.update_dealer(db, user, did, body.model_dump(exclude_unset=True))


@router.delete("/dealers/{did}", status_code=204)
def delete_dealer(did: int, db: Session = Depends(get_db), user: User = CurrentUser):
    contacts_service.delete_dealer(db, user, did)
    return Response(status_code=204)


# ---------------------------------------------------------------- bills
@router.get("/bills")
def list_bills(date_from: date | None = None, date_to: date | None = None, customer_id: int | None = None,
               q: str | None = None, city: str | None = None, state: str | None = None, country: str | None = None,
               include_void: bool = False, page: int = 1, page_size: int = 50,
               db: Session = Depends(get_db), _: User = CurrentUser):
    return billing_service.list_bills(db, date_from=date_from, date_to=date_to, customer_id=customer_id, q=q,
                                      city=city, state=state, country=country, include_void=include_void,
                                      page=page, page_size=page_size)


@router.post("/bills", status_code=201)
def create_bill(body: BillIn, db: Session = Depends(get_db), user: User = CurrentUser):
    data = body.model_dump()
    data["customer"] = body.customer.model_dump(exclude_unset=True) if body.customer else None
    return billing_service.create(db, user, data)


@router.get("/bills/{bill_id}")
def get_bill(bill_id: int, db: Session = Depends(get_db), _: User = CurrentUser):
    return billing_service.get_bill(db, bill_id)


@router.post("/bills/{bill_id}/void")
def void_bill(bill_id: int, body: VoidBillIn | None = None, db: Session = Depends(get_db), user: User = CurrentUser):
    return billing_service.void_bill(db, user, bill_id, body.reason if body else None)


@router.get("/bills/{bill_id}/pdf")
def bill_pdf(bill_id: int, db: Session = Depends(get_db), _: User = CurrentUser):
    name, data = billing_service.bill_pdf(db, bill_id)
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ---------------------------------------------------------------- explorer
def _filters(date_from: date | None, date_to: date | None, category_id: int | None, design_id: int | None,
             label: str | None, metal: Metal | None, customer_id: int | None, walk_in: bool, city: str | None,
             state: str | None, country: str | None, payment_mode: str | None, dealer_id: int | None,
             no_dealer: bool, dealer_city: str | None, dealer_state: str | None, purchases_only: bool) -> dict:
    return {k: v for k, v in dict(
        date_from=date_from, date_to=date_to, category_id=category_id, design_id=design_id, label=label,
        metal=metal, customer_id=customer_id, walk_in=walk_in, city=city, state=state, country=country,
        payment_mode=payment_mode, dealer_id=dealer_id, no_dealer=no_dealer, dealer_city=dealer_city,
        dealer_state=dealer_state, purchases_only=purchases_only).items() if v not in (None, "", False)}


def explorer_filters(date_from: date | None = None, date_to: date | None = None, category_id: int | None = None,
                     design_id: int | None = None, label: str | None = None, metal: Metal | None = None,
                     customer_id: int | None = None, walk_in: bool = False, city: str | None = None,
                     state: str | None = None, country: str | None = None, payment_mode: str | None = None,
                     dealer_id: int | None = None, no_dealer: bool = False, dealer_city: str | None = None,
                     dealer_state: str | None = None, purchases_only: bool = False) -> dict:
    return _filters(date_from, date_to, category_id, design_id, label, metal, customer_id, walk_in, city, state,
                    country, payment_mode, dealer_id, no_dealer, dealer_city, dealer_state, purchases_only)


@router.get("/explore/facets")
def explore_facets(db: Session = Depends(get_db), _: User = CurrentUser):
    return explorer_service.facets(db)


@router.get("/explore/{kind}")
def explore(kind: str, group_by: str | None = None, sort_by: str | None = None, sort_dir: str | None = None,
            page: int = 1, page_size: int = 50, f: dict = Depends(explorer_filters),
            db: Session = Depends(get_db), _: User = CurrentUser):
    kind = "sales" if kind == "sales" else "purchases"
    return explorer_service.explore(db, kind, f, group_by or None, sort_by, sort_dir, page, page_size)


@router.get("/explore/{kind}/export")
def explore_export(kind: str, group_by: str | None = None, sort_by: str | None = None, sort_dir: str | None = None,
                   f: dict = Depends(explorer_filters), db: Session = Depends(get_db), _: User = CurrentUser):
    kind = "sales" if kind == "sales" else "purchases"
    name, data = explorer_service.export_xlsx(db, kind, f, group_by or None, sort_by, sort_dir)
    return StreamingResponse(iter([data]), media_type=XLSX,
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.models import User
from app.services import metrics_service, period_service
from app.services.serializers import photo_url

router = APIRouter(prefix="/periods", tags=["periods"])


def period_dep(period_type: str = "month", anchor: date | None = None, start: date | None = None,
               end: date | None = None, db: Session = Depends(get_db)) -> period_service.Period:
    return period_service.resolve(db, period_type, anchor, start, end)


@router.get("/resolve")
def resolve(p: period_service.Period = Depends(period_dep), db: Session = Depends(get_db), _: User = CurrentUser):
    return period_service.to_out(db, p)


@router.get("/options")
def options(db: Session = Depends(get_db), _: User = CurrentUser):
    return period_service.options(db)


def period_stock(db: Session, p: period_service.Period, category_id=None, subcategory_id=None, status=None,
                 search=None, sort="label", page=1, page_size=50, dealer_id=None, customer_id=None) -> dict:
    from app.models import Bill, StockMovement
    from app.models.enums import MovementType
    from app.services import explorer_service, profit_service

    parties = explorer_service.design_parties(db, p.start, p.effective_end)
    only: set[int] | None = None
    if dealer_id:  # designs bought from this dealer (any time)
        only = {d for (d,) in db.query(StockMovement.design_id).filter(
            StockMovement.dealer_id == dealer_id, StockMovement.is_void.is_(False)).distinct()}
    if customer_id:  # designs this customer bought in the period
        sold = {d for (d,) in db.query(StockMovement.design_id).join(Bill, Bill.id == StockMovement.bill_id).filter(
            Bill.customer_id == customer_id, StockMovement.type == MovementType.SALE, StockMovement.is_void.is_(False),
            StockMovement.occurred_on >= p.start, StockMovement.occurred_on <= p.effective_end).distinct()}
        only = sold if only is None else only & sold

    snap = metrics_service.snapshot(db)
    rows_map = period_service.period_rows(db, p)
    profit = profit_service.design_profit(db, p.start, p.effective_end)
    statuses = [s.strip().upper() for s in status.split(",")] if status else None
    s_l = (search or "").strip().lower()
    rows = []
    for d in snap.designs.values():
        st = snap.states[d.id]
        if not d.is_active and d.id not in rows_map:
            continue
        if category_id and d.category_id != category_id:
            continue
        if subcategory_id and d.subcategory_id != subcategory_id:
            continue
        if statuses and st.status.value not in statuses:
            continue
        if s_l and s_l not in d.label.lower() and s_l not in (d.name or "").lower():
            continue
        if only is not None and d.id not in only:
            continue
        pt = parties.get(d.id, {})
        r = rows_map.get(d.id) or {f: 0 for f in period_service.FIELDS} | {"sales_value": 0}
        rows.append({
            "design": {"id": d.id, "label": d.label, "name": d.name, "category_name": d.category.name,
                       "subcategory_name": d.subcategory.name if d.subcategory else None, "photo_url": photo_url(d)},
            **{f: r[f] for f in period_service.FIELDS},
            "sales_value": float(r["sales_value"]),
            "net_revenue": float(profit[d.id]["net_revenue"]) if d.id in profit else 0.0,
            "net_profit": float(profit[d.id]["net_profit"]) if d.id in profit else 0.0,
            "margin_pct": profit_service.margin(profit[d.id]["net_profit"], profit[d.id]["net_revenue"]) if d.id in profit else None,
            "status_now": st.status.value,
            "dealer": pt.get("dealer") or d.supplier, "dealers": pt.get("dealers", 0),
            "customers": pt.get("customers", 0), "top_customer": pt.get("top_customer"),
        })
    # sort: any column, "-" in front = highest first (e.g. -net_profit, sold, -customers, dealer)
    desc = (sort or "").startswith("-")
    field = (sort or "label").lstrip("-")
    text_fields = {"label": lambda r: r["design"]["label"], "category": lambda r: r["design"]["category_name"],
                   "dealer": lambda r: (r["dealer"] or "~").lower(), "top_customer": lambda r: (r["top_customer"] or "~").lower(),
                   "status_now": lambda r: r["status_now"]}
    if field in text_fields:
        getter = text_fields[field]
    elif rows and field in rows[0] and isinstance(rows[0][field], (int, float)) or field == "opening":
        getter = (lambda r: r["opening"] + r["opening_added"]) if field == "opening" else (lambda r: r[field] or 0)
    else:
        getter = text_fields["label"]
    rows.sort(key=lambda r: (getter(r), r["design"]["label"]), reverse=desc)
    totals = {f: sum(r[f] for r in rows) for f in period_service.FIELDS}
    totals["sales_value"] = round(sum(r["sales_value"] for r in rows), 2)
    totals["net_revenue"] = round(sum(r["net_revenue"] for r in rows), 2)
    totals["net_profit"] = round(sum(r["net_profit"] for r in rows), 2)
    totals["margin_pct"] = profit_service.margin(totals["net_profit"], totals["net_revenue"])
    page_size = max(1, min(int(page_size), 500))
    page = max(1, int(page))
    who = explorer_service.summary(db, p.start, p.effective_end, n=1)
    return {
        "period": period_service.to_out(db, p),
        "rows": {"items": rows[(page - 1) * page_size: page * page_size], "total": len(rows), "page": page,
                 "page_size": page_size},
        "totals": totals,
        "top_customer": (who["top_customers"] or [None])[0],
        "top_dealer": (who["top_dealers"] or [None])[0],
    }


@router.get("/stock")
def get_period_stock(
    p: period_service.Period = Depends(period_dep),
    category_id: int | None = None,
    subcategory_id: int | None = None,
    status: str | None = None,
    search: str | None = None,
    sort: str = "label",
    page: int = 1,
    page_size: int = 50,
    dealer_id: int | None = None,
    customer_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = CurrentUser,
):
    return period_stock(db, p, category_id, subcategory_id, status, search, sort, page, page_size, dealer_id,
                        customer_id)

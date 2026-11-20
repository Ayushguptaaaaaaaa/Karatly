from __future__ import annotations

import re
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session, joinedload

from app.core.clock import today as _today
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import Category, Design, StockMovement, Subcategory, User
from app.models.enums import Metal, MovementSource, MovementType
from app.services import audit_service, data_version_service, metrics_service, settings_service, stock_service
from app.services.serializers import design_detail, design_list_item, movement_out, photo_url

def period_service_month_end(start: date) -> date:
    import calendar

    return start.replace(day=calendar.monthrange(start.year, start.month)[1])


LABEL_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-/]{1,19}$")
EDITABLE = ["name", "description", "metal", "purity", "weight_g", "cost_price", "selling_price", "supplier",
            "min_stock", "inflation_pct_override", "custom_fields", "subcategory_id", "category_id"]
SORTS = {
    "label": (lambda d, s: d.label, False),
    "name": (lambda d, s: (d.name or "").lower(), False),
    "current_stock": (lambda d, s: s.current_stock, False),
    "-current_stock": (lambda d, s: s.current_stock, True),
    "-sold_last_30d": (lambda d, s: s.sold_30d, True),
    "-stock_value": (lambda d, s: s.stock_value_cost, True),
    "-updated_at": (lambda d, s: d.updated_at or d.created_at, True),
    "-created_at": (lambda d, s: d.id, True),
}


def norm_label(label: str) -> str:
    return (label or "").strip().upper().replace(" ", "")


def label_error(label: str) -> str | None:
    if not label:
        return "Label is required"
    if not LABEL_RE.match(label):
        return "Use 2–20 letters, numbers, - or / (e.g. ER-1012)"
    return None


def get(db: Session, design_id: int) -> Design:
    d = db.get(Design, design_id, options=[joinedload(Design.category), joinedload(Design.subcategory)])
    if not d:
        raise AppError("DESIGN_NOT_FOUND", "Design not found", 404)
    return d


def detail(db: Session, design_id: int) -> dict:
    from datetime import timedelta

    from app.services import profit_service

    d = get(db, design_id)
    snap = metrics_service.snapshot(db)
    out = design_detail(d, snap.states[d.id])
    t = _today()
    pr = profit_service.design_profit(db, t - timedelta(days=29), t, [d.id]).get(d.id)
    out["avg_unit_cost"] = profit_service.avg_cost_map(db, [d.id]).get(d.id)
    out["net_revenue_30d"] = pr["net_revenue"] if pr else 0
    out["net_profit_30d"] = pr["net_profit"] if pr else 0
    out["margin_pct_30d"] = profit_service.margin(pr["net_profit"], pr["net_revenue"]) if pr else None
    return out


def by_label(db: Session, label: str) -> dict:
    d = db.query(Design).filter(Design.label == norm_label(label)).first()
    if not d:
        raise AppError("DESIGN_NOT_FOUND", f"No design with label {norm_label(label)}", 404)
    return detail(db, d.id)


def list_designs(db: Session, *, category_id=None, subcategory_id=None, statuses=None, demands=None, search=None,
                 include_inactive=False, sort="label", page=1, page_size=25) -> dict:
    snap = metrics_service.snapshot(db)
    items = []
    s_l = (search or "").strip().lower()
    for d in snap.designs.values():
        st = snap.states[d.id]
        if not include_inactive and not d.is_active:
            continue
        if category_id and d.category_id != category_id:
            continue
        if subcategory_id and d.subcategory_id != subcategory_id:
            continue
        if statuses and st.status.value not in statuses:
            continue
        if demands and st.demand.value not in demands:
            continue
        if s_l and s_l not in d.label.lower() and s_l not in (d.name or "").lower():
            continue
        items.append((d, st))
    key, rev = SORTS.get(sort or "label", SORTS["label"])
    items.sort(key=lambda x: key(*x), reverse=rev)
    page_size = max(1, min(int(page_size), 200))
    page = max(1, int(page))
    chunk = items[(page - 1) * page_size: page * page_size]
    return {"items": [design_list_item(d, st) for d, st in chunk], "total": len(items), "page": page,
            "page_size": page_size}


def search(db: Session, q: str, limit: int = 8) -> list[dict]:
    snap = metrics_service.snapshot(db, include_inactive=False)
    ql = (q or "").strip().lower()
    hits = []
    for d in snap.designs.values():
        lbl = d.label.lower()
        name = (d.name or "").lower()
        if ql and ql not in lbl and ql not in name:
            continue
        score = 0 if lbl == ql else (1 if lbl.startswith(ql) else (2 if ql in lbl else 3))
        hits.append((score, d.label, d))
    hits.sort(key=lambda x: (x[0], x[1]))
    out = []
    for _, _, d in hits[: max(1, min(limit, 30))]:
        st = snap.states[d.id]
        out.append({"id": d.id, "label": d.label, "name": d.name, "category_name": d.category.name,
                    "current_stock": st.current_stock, "status": st.status.value, "photo_url": photo_url(d),
                    "selling_price": float(d.selling_price), "cost_price": float(st.last_unit_cost),
                    "min_stock": d.min_stock})
    return out


def next_labels(db: Session, category_id: int, count: int) -> list[str]:
    c = db.get(Category, category_id)
    if not c:
        raise AppError("CATEGORY_NOT_FOUND", "Category not found", 404)
    count = max(1, min(int(count), 100))
    pat = re.compile(rf"^{re.escape(c.label_prefix)}-(\d+)$")
    existing = {lbl for (lbl,) in db.query(Design.label).all()}
    nums = [int(m.group(1)) for lbl in existing if (m := pat.match(lbl))]
    n = max(nums) + 1 if nums else 1001
    out = []
    while len(out) < count:
        lbl = f"{c.label_prefix}-{n}"
        if lbl not in existing:
            out.append(lbl)
        n += 1
    return out


def check_label(db: Session, label: str, exclude_id: int | None = None) -> dict:
    lbl = norm_label(label)
    err = label_error(lbl)
    if err:
        return {"label": lbl, "valid": False, "available": False, "message": err}
    q = db.query(Design).filter(Design.label == lbl)
    if exclude_id:
        q = q.filter(Design.id != exclude_id)
    taken = q.first() is not None
    return {"label": lbl, "valid": True, "available": not taken, "message": "Already used" if taken else None}


def _dec(v, field: str, errors: list, idx: int, required: bool = False, minimum: float = 0):
    if v is None or v == "":
        if required:
            errors.append({"index": idx, "field": field, "message": "Required"})
        return None
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError):
        errors.append({"index": idx, "field": field, "message": "Must be a number"})
        return None
    if d < Decimal(str(minimum)):
        errors.append({"index": idx, "field": field, "message": f"Must be ≥ {minimum}"})
        return None
    return d


def validate_rows(db: Session, rows: list[dict], default_min: int) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    clean: list[dict] = []
    seen: dict[str, int] = {}
    existing = {lbl for (lbl,) in db.query(Design.label).all()}
    for idx, r in enumerate(rows):
        lbl = norm_label(r.get("label") or "")
        err = label_error(lbl)
        if err:
            errors.append({"index": idx, "field": "label", "message": err})
        elif lbl in seen:
            errors.append({"index": idx, "field": "label", "message": f"Duplicate of row {seen[lbl] + 1}"})
        elif lbl in existing:
            errors.append({"index": idx, "field": "label", "message": "Already used"})
        seen.setdefault(lbl, idx)
        cost = _dec(r.get("cost_price"), "cost_price", errors, idx, required=True)
        sell = _dec(r.get("selling_price"), "selling_price", errors, idx, required=True)
        weight = _dec(r.get("weight_g"), "weight_g", errors, idx)
        opening = r.get("opening_stock") or 0
        try:
            opening = int(opening)
            if opening < 0:
                raise ValueError
        except (TypeError, ValueError):
            errors.append({"index": idx, "field": "opening_stock", "message": "Whole number ≥ 0"})
            opening = 0
        min_stock = r.get("min_stock")
        try:
            min_stock = default_min if min_stock in (None, "") else int(min_stock)
            if min_stock < 0:
                raise ValueError
        except (TypeError, ValueError):
            errors.append({"index": idx, "field": "min_stock", "message": "Whole number ≥ 0"})
            min_stock = default_min
        metal = (r.get("metal") or "GOLD").upper()
        if metal not in Metal.__members__:
            errors.append({"index": idx, "field": "metal", "message": "GOLD, SILVER, PLATINUM, IMITATION or OTHER"})
            metal = "GOLD"
        clean.append({
            "label": lbl, "name": (r.get("name") or None), "metal": Metal(metal),
            "purity": (r.get("purity") or None), "weight_g": weight, "cost_price": cost, "selling_price": sell,
            "min_stock": min_stock, "opening_stock": opening,
            "supplier": (str(r.get("supplier") or r.get("dealer") or "").strip() or None),
            "description": r.get("description") or None,
        })
    return clean, errors


def bulk_create(db: Session, user: User, category_id: int, subcategory_id: int | None, rows: list[dict],
                opening_date: date | None = None, source: MovementSource = MovementSource.OPENING,
                commit: bool = True) -> list[Design]:
    c = db.get(Category, category_id)
    if not c:
        raise AppError("CATEGORY_NOT_FOUND", "Category not found", 404)
    if subcategory_id:
        s = db.get(Subcategory, subcategory_id)
        if not s or s.category_id != c.id:
            raise AppError("VALIDATION_ERROR", "Subcategory does not belong to this category", 422)
    if not rows:
        raise AppError("VALIDATION_ERROR", "Add at least one design", 422)
    if len(rows) > 100:
        raise AppError("VALIDATION_ERROR", "At most 100 designs at a time", 422)
    on = opening_date or _today()
    if on > _today():
        raise AppError("FUTURE_DATE", "Opening date cannot be in the future.", 422)
    default_min = int(settings_service.get(db, "default_min_stock") or 3)
    clean, errors = validate_rows(db, rows, default_min)
    if errors:
        raise AppError("BULK_VALIDATION_FAILED", f"{len(errors)} problem(s) found. Please fix the highlighted cells.",
                       422, {"rows": errors})
    created = []
    for r in clean:
        opening = r.pop("opening_stock")
        d = Design(category_id=c.id, subcategory_id=subcategory_id, custom_fields={}, **r)
        d.category = c
        db.add(d)
        db.flush()
        if opening > 0:
            m = stock_service._add_movement(db, user, d, MovementType.OPENING, opening, on, d.cost_price,
                                            source=source, check=False)
            if d.supplier:  # the supplier is a dealer: link the opening stock to it
                from app.services import contacts_service

                m.dealer_id = contacts_service.get_or_create_dealer(db, user, d.supplier).id
        created.append(d)
    audit_service.log(db, user, "CREATE", "design_batch", c.id,
                      after={"count": len(created), "labels": [d.label for d in created][:50]})
    if commit:
        ev = data_version_service.bump(db, "design", "create_batch", c.id)
        db.commit()
        data_version_service.publish(ev)
    return created


def update(db: Session, user: User, design_id: int, data: dict) -> dict:
    d = get(db, design_id)
    before = {k: getattr(d, k) for k in ("label", "cost_price", "selling_price", "min_stock")}
    if "label" in data and data["label"]:
        chk = check_label(db, data["label"], exclude_id=d.id)
        if not chk["valid"] or not chk["available"]:
            raise AppError("LABEL_TAKEN" if chk["valid"] else "VALIDATION_ERROR", chk["message"] or "Invalid label",
                           409 if chk["valid"] else 422, {"fields": {"label": chk["message"]}})
        d.label = chk["label"]
    cat_id = data.get("category_id") or d.category_id
    if data.get("category_id"):
        if not db.get(Category, cat_id):
            raise AppError("CATEGORY_NOT_FOUND", "Category not found", 404)
    if "subcategory_id" in data and data["subcategory_id"]:
        s = db.get(Subcategory, data["subcategory_id"])
        if not s or s.category_id != cat_id:
            raise AppError("VALIDATION_ERROR", "Subcategory does not belong to the category", 422)
    for f in EDITABLE:
        if f in data:
            v = data[f]
            if f in ("cost_price", "selling_price") and (v is None or Decimal(str(v)) < 0):
                raise AppError("VALIDATION_ERROR", f"{f} must be ≥ 0", 422, {"fields": {f: "≥ 0"}})
            if f == "min_stock" and (v is None or int(v) < 0):
                raise AppError("VALIDATION_ERROR", "Min stock must be ≥ 0", 422)
            setattr(d, f, v)
    audit_service.log(db, user, "UPDATE", "design", d.id, before=before, after=data)
    ev = data_version_service.bump(db, "design", "update", d.id)
    db.commit()
    data_version_service.publish(ev)
    return detail(db, d.id)


def set_active(db: Session, user: User, design_id: int, active: bool) -> dict:
    d = get(db, design_id)
    d.is_active = active
    audit_service.log(db, user, "ARCHIVE" if not active else "UPDATE", "design", d.id, after={"is_active": active})
    ev = data_version_service.bump(db, "design", "archive" if not active else "unarchive", d.id)
    db.commit()
    data_version_service.publish(ev)
    return detail(db, d.id)


def delete(db: Session, user: User, design_id: int) -> None:
    d = get(db, design_id)
    other = db.query(StockMovement).filter(StockMovement.design_id == d.id,
                                           StockMovement.type != MovementType.OPENING).first()
    if other:
        raise AppError("DESIGN_HAS_HISTORY", "This design has sales or stock history. Archive it instead.", 409)
    db.query(StockMovement).filter(StockMovement.design_id == d.id).delete()
    _remove_photo_file(d)
    db.delete(d)
    audit_service.log(db, user, "DELETE", "design", design_id, before={"label": d.label})
    ev = data_version_service.bump(db, "design", "delete", design_id)
    db.commit()
    data_version_service.publish(ev)


def _remove_photo_file(d: Design) -> None:
    if d.photo_filename:
        p = get_settings().photo_dir / d.photo_filename
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass


ALLOWED_PHOTO = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def save_photo(db: Session, user: User, design_id: int, content_type: str, data: bytes) -> dict:
    d = get(db, design_id)
    ext = ALLOWED_PHOTO.get((content_type or "").lower())
    if not ext:
        raise AppError("UNSUPPORTED_FILE", "Please upload a JPG, PNG or WEBP image.", 422)
    max_mb = get_settings().MAX_PHOTO_MB
    if len(data) > max_mb * 1024 * 1024:
        raise AppError("FILE_TOO_LARGE", f"Photo must be under {max_mb} MB.", 422)
    _remove_photo_file(d)
    fname = f"{d.id}_{uuid.uuid4().hex[:8]}.{ext}"
    folder = get_settings().photo_dir
    folder.mkdir(parents=True, exist_ok=True)
    (folder / fname).write_bytes(data)
    d.photo_filename = fname
    audit_service.log(db, user, "UPDATE", "design_photo", d.id)
    ev = data_version_service.bump(db, "design", "photo", d.id)
    db.commit()
    data_version_service.publish(ev)
    return {"photo_url": photo_url(d)}


def delete_photo(db: Session, user: User, design_id: int) -> None:
    d = get(db, design_id)
    _remove_photo_file(d)
    d.photo_filename = None
    ev = data_version_service.bump(db, "design", "photo", d.id)
    db.commit()
    data_version_service.publish(ev)


def history(db: Session, design_id: int, months: int = 12) -> dict:
    d = get(db, design_id)
    starts = metrics_service.month_starts(_today(), max(1, min(months, 36)))
    rows = (db.query(StockMovement).options(joinedload(StockMovement.design), joinedload(StockMovement.creator))
            .filter(StockMovement.design_id == d.id).order_by(StockMovement.occurred_on.desc(),
                                                              StockMovement.id.desc()).all())
    monthly = {metrics_service.month_key(s): {"sold": 0, "received": 0, "sales_value": 0.0} for s in starts}
    for m in rows:
        if m.is_void:
            continue
        mk = metrics_service.month_key(m.occurred_on)
        if mk not in monthly:
            continue
        if m.type == MovementType.SALE:
            monthly[mk]["sold"] += m.quantity
            monthly[mk]["sales_value"] += float((m.unit_price or 0) * m.quantity)
        elif m.type in (MovementType.PURCHASE, MovementType.OPENING):
            monthly[mk]["received"] += m.quantity
    from app.services import profit_service

    for s_ in starts:
        mk = metrics_service.month_key(s_)
        end_ = period_service_month_end(s_)
        pr = profit_service.design_profit(db, s_, end_, [d.id]).get(d.id)
        monthly[mk]["net_revenue"] = float(pr["net_revenue"]) if pr else 0.0
        monthly[mk]["net_profit"] = float(pr["net_profit"]) if pr else 0.0
    return {
        "monthly": [{"month": metrics_service.month_key(s), "label": metrics_service.MONTH_ABBR[s.month - 1],
                     **monthly[metrics_service.month_key(s)]} for s in starts],
        "movements": [movement_out(m) for m in rows[:50]],
    }

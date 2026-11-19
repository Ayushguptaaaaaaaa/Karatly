from __future__ import annotations

import re

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Category, Design, Subcategory, User
from app.models.enums import CATEGORY_ICONS
from app.services import audit_service, data_version_service, metrics_service
from app.services.serializers import category_card, subcategory_out

PREFIX_RE = re.compile(r"^[A-Z]{1,5}$")
VOWELS = set("AEIOU")


def _key(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _prefix_taken(db: Session, prefix: str, exclude_id: int | None = None) -> bool:
    q = db.query(Category).filter(Category.label_prefix == prefix)
    if exclude_id:
        q = q.filter(Category.id != exclude_id)
    return db.query(q.exists()).scalar()


def suggest_prefix(db: Session, name: str) -> str:
    letters = re.sub(r"[^A-Za-z]", "", name).upper() or "X"
    candidates = [letters[:2]]
    consonants = [ch for ch in letters[1:] if ch not in VOWELS]
    candidates += [letters[0] + c for c in consonants]
    candidates += [letters[:3]]
    for cand in candidates:
        if cand and not _prefix_taken(db, cand):
            return cand
    base = letters[:2]
    for n in range(2, 10):
        cand = f"{base}{chr(64 + n)}"
        if not _prefix_taken(db, cand):
            return cand
    return letters[:4]


def cards(db: Session, include_inactive: bool = False) -> list[dict]:
    snap = metrics_service.snapshot(db)
    q = db.query(Category).order_by(Category.sort_order, Category.id)
    if not include_inactive:
        q = q.filter(Category.is_active.is_(True))
    designs = list(snap.designs.values())
    return [category_card(c, designs, snap.states) for c in q.all()]


def card(db: Session, category_id: int) -> dict:
    c = get(db, category_id)
    snap = metrics_service.snapshot(db)
    designs = list(snap.designs.values())
    out = category_card(c, designs, snap.states)
    subs = []
    for s in c.subcategories:
        mine = [d for d in designs if d.subcategory_id == s.id and d.is_active]
        subs.append({**subcategory_out(s), "design_count": len(mine),
                     "total_pieces": sum(snap.states[d.id].current_stock for d in mine)})
    out["subcategories"] = subs
    return out


def get(db: Session, category_id: int) -> Category:
    c = db.get(Category, category_id)
    if not c:
        raise AppError("CATEGORY_NOT_FOUND", "Category not found", 404)
    return c


def _validate(db: Session, name: str | None, prefix: str | None, icon: str | None, exclude_id: int | None = None):
    if name is not None:
        if not name.strip():
            raise AppError("VALIDATION_ERROR", "Name is required", 422, {"fields": {"name": "Required"}})
        q = db.query(Category).filter(Category.name_key == _key(name))
        if exclude_id:
            q = q.filter(Category.id != exclude_id)
        if q.first():
            raise AppError("CATEGORY_EXISTS", f"A category named '{name.strip()}' already exists.", 409,
                           {"fields": {"name": "Already exists"}})
    if prefix is not None:
        if not PREFIX_RE.match(prefix):
            raise AppError("VALIDATION_ERROR", "Prefix must be 1–5 letters (A–Z).", 422,
                           {"fields": {"label_prefix": "1–5 letters"}})
        if _prefix_taken(db, prefix, exclude_id):
            raise AppError("PREFIX_TAKEN", f"Prefix {prefix} is already used by another category.", 409,
                           {"fields": {"label_prefix": "Already used"}})
    if icon is not None and icon not in CATEGORY_ICONS:
        raise AppError("VALIDATION_ERROR", "Unknown icon", 422, {"fields": {"icon": "Unknown icon"}})


def create(db: Session, user: User, data: dict) -> Category:
    name = data["name"].strip()
    prefix = (data.get("label_prefix") or "").strip().upper() or suggest_prefix(db, name)
    icon = data.get("icon") or "other"
    _validate(db, name, prefix, icon)
    next_order = (db.query(func.max(Category.sort_order)).scalar() or 0) + 1
    c = Category(
        name=name, name_key=_key(name), label_prefix=prefix, icon=icon,
        description=data.get("description"), inflation_pct_override=data.get("inflation_pct_override"),
        sort_order=next_order,
    )
    db.add(c)
    db.flush()
    for i, sub_name in enumerate(data.get("subcategories") or []):
        if sub_name and sub_name.strip():
            _add_sub(db, c, sub_name.strip(), None, i)
    audit_service.log(db, user, "CREATE", "category", c.id, after={"name": name, "prefix": prefix})
    ev = data_version_service.bump(db, "category", "create", c.id)
    db.commit()
    data_version_service.publish(ev)
    return c


def update(db: Session, user: User, category_id: int, data: dict) -> Category:
    c = get(db, category_id)
    before = {"name": c.name, "label_prefix": c.label_prefix, "icon": c.icon}
    name = data.get("name")
    prefix = data.get("label_prefix")
    prefix = prefix.strip().upper() if prefix else None
    _validate(db, name, prefix, data.get("icon"), exclude_id=c.id)
    if name:
        c.name, c.name_key = name.strip(), _key(name)
    if prefix:
        c.label_prefix = prefix
    for f in ("icon", "description", "sort_order", "is_active"):
        if f in data and data[f] is not None:
            setattr(c, f, data[f])
    if "inflation_pct_override" in data:
        c.inflation_pct_override = data["inflation_pct_override"]
    audit_service.log(db, user, "UPDATE", "category", c.id, before=before, after=data)
    ev = data_version_service.bump(db, "category", "update", c.id)
    db.commit()
    data_version_service.publish(ev)
    return c


def delete(db: Session, user: User, category_id: int) -> None:
    c = get(db, category_id)
    if db.query(Design).filter(Design.category_id == c.id).first():
        raise AppError("CATEGORY_NOT_EMPTY", "This category has designs. Archive it instead.", 409)
    for s in list(c.subcategories):
        db.delete(s)
    db.delete(c)
    audit_service.log(db, user, "DELETE", "category", category_id, before={"name": c.name})
    ev = data_version_service.bump(db, "category", "delete", category_id)
    db.commit()
    data_version_service.publish(ev)


# --- subcategories ----------------------------------------------------------

def _add_sub(db: Session, c: Category, name: str, description: str | None, order: int | None = None) -> Subcategory:
    if db.query(Subcategory).filter(Subcategory.category_id == c.id, Subcategory.name_key == _key(name)).first():
        raise AppError("SUBCATEGORY_EXISTS", f"'{name}' already exists in {c.name}.", 409,
                       {"fields": {"name": "Already exists"}})
    if order is None:
        order = (db.query(func.max(Subcategory.sort_order)).filter(Subcategory.category_id == c.id).scalar() or 0) + 1
    s = Subcategory(category_id=c.id, name=name, name_key=_key(name), description=description, sort_order=order)
    db.add(s)
    db.flush()
    return s


def list_subs(db: Session, category_id: int) -> list[Subcategory]:
    c = get(db, category_id)
    return [s for s in c.subcategories]


def create_sub(db: Session, user: User, category_id: int, name: str, description: str | None) -> Subcategory:
    c = get(db, category_id)
    if not name or not name.strip():
        raise AppError("VALIDATION_ERROR", "Name is required", 422, {"fields": {"name": "Required"}})
    s = _add_sub(db, c, name.strip(), description)
    audit_service.log(db, user, "CREATE", "subcategory", s.id, after={"name": s.name, "category": c.name})
    ev = data_version_service.bump(db, "subcategory", "create", s.id)
    db.commit()
    data_version_service.publish(ev)
    return s


def get_sub(db: Session, sub_id: int) -> Subcategory:
    s = db.get(Subcategory, sub_id)
    if not s:
        raise AppError("SUBCATEGORY_NOT_FOUND", "Subcategory not found", 404)
    return s


def update_sub(db: Session, user: User, sub_id: int, data: dict) -> Subcategory:
    s = get_sub(db, sub_id)
    if data.get("name"):
        name = data["name"].strip()
        dup = db.query(Subcategory).filter(Subcategory.category_id == s.category_id,
                                           Subcategory.name_key == _key(name), Subcategory.id != s.id).first()
        if dup:
            raise AppError("SUBCATEGORY_EXISTS", f"'{name}' already exists.", 409, {"fields": {"name": "Already exists"}})
        s.name, s.name_key = name, _key(name)
    for f in ("description", "is_active", "sort_order"):
        if f in data and data[f] is not None:
            setattr(s, f, data[f])
    audit_service.log(db, user, "UPDATE", "subcategory", s.id, after=data)
    ev = data_version_service.bump(db, "subcategory", "update", s.id)
    db.commit()
    data_version_service.publish(ev)
    return s


def delete_sub(db: Session, user: User, sub_id: int) -> None:
    s = get_sub(db, sub_id)
    if db.query(Design).filter(Design.subcategory_id == s.id).first():
        raise AppError("SUBCATEGORY_NOT_EMPTY", "This subcategory has designs. Move or archive them first.", 409)
    db.delete(s)
    audit_service.log(db, user, "DELETE", "subcategory", sub_id)
    ev = data_version_service.bump(db, "subcategory", "delete", sub_id)
    db.commit()
    data_version_service.publish(ev)

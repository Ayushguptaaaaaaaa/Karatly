from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models import Setting, User

PUBLIC_KEYS = [
    "shop_name",
    "owner_name",
    "inflation_pct_global",
    "default_min_stock",
    "dead_stock_days",
    "reorder_cover_months",
    "quarter_system",
    "monthly_purchase_budget",
    "max_stock_multiple",
]


def defaults() -> dict[str, Any]:
    s = get_settings()
    return {
        "shop_name": s.SHOP_NAME,
        "owner_name": s.OWNER_NAME,
        "inflation_pct_global": float(s.DEFAULT_INFLATION_PCT),
        "default_min_stock": int(s.DEFAULT_MIN_STOCK),
        "dead_stock_days": int(s.DEAD_STOCK_DAYS),
        "reorder_cover_months": float(s.REORDER_COVER_MONTHS),
        "quarter_system": s.QUARTER_SYSTEM,
        "monthly_purchase_budget": 0.0,   # 0 = no limit
        "max_stock_multiple": 1.5,        # never restock above this × the most stock a design has held
        "data_version": 0,
        "milestones": {},
    }


def seed(db: Session) -> None:
    existing = {row.key for row in db.query(Setting.key).all()}
    for key, value in defaults().items():
        if key not in existing:
            db.add(Setting(key=key, value=value))
    db.commit()


def get(db: Session, key: str) -> Any:
    row = db.get(Setting, key)
    if row is None:
        return defaults().get(key)
    return row.value


def get_all(db: Session) -> dict[str, Any]:
    rows = {r.key: r.value for r in db.query(Setting).all()}
    out = defaults()
    out.update(rows)
    return {k: out[k] for k in PUBLIC_KEYS}


def set_value(db: Session, key: str, value: Any, user: User | None = None) -> None:
    row = db.get(Setting, key)
    if row is None:
        row = Setting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    if user is not None:
        row.updated_by = user.id


_RULES = {
    "inflation_pct_global": (0, 50),
    "default_min_stock": (0, 1000),
    "dead_stock_days": (15, 730),
    "reorder_cover_months": (0.5, 6),
    "monthly_purchase_budget": (0, 1e12),
    "max_stock_multiple": (1, 5),
}


def update(db: Session, user: User, patch: dict[str, Any]) -> dict[str, Any]:
    for key, value in patch.items():
        if value is None:
            continue
        if key not in PUBLIC_KEYS:
            raise AppError("UNKNOWN_SETTING", f"Unknown setting {key}", 422)
        if key in _RULES:
            lo, hi = _RULES[key]
            if not (lo <= float(value) <= hi):
                raise AppError("VALIDATION_ERROR", f"{key} must be between {lo} and {hi}", 422, {"fields": {key: f"Between {lo} and {hi}"}})
        if key == "quarter_system" and value not in ("FINANCIAL", "CALENDAR"):
            raise AppError("VALIDATION_ERROR", "quarter_system must be FINANCIAL or CALENDAR", 422)
        if key in ("shop_name", "owner_name"):
            value = str(value).strip()[:80] or defaults()[key]
        set_value(db, key, value, user)
    return patch

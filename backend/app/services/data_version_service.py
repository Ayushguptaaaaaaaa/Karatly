"""Monotonic data version used for staleness and live updates."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.clock import now_utc
from app.core.events import bus
from app.models import Setting


def current(db: Session) -> int:
    row = db.get(Setting, "data_version")
    return int(row.value) if row else 0


def bump(db: Session, entity: str, action: str, entity_id: int | str | None = None) -> dict:
    """Increment inside the caller's transaction. Returns the event payload to publish after commit."""
    row = db.get(Setting, "data_version")
    if row is None:
        row = Setting(key="data_version", value=0)
        db.add(row)
    row.value = int(row.value or 0) + 1
    return {
        "data_version": row.value,
        "entity": entity,
        "action": action,
        "entity_id": entity_id,
        "at": now_utc().isoformat(),
    }


def notify(db: Session, entity: str, action: str, entity_id: int | str | None = None) -> dict:
    """Event payload for changes that don't affect stock/sales data (e.g. purchase plan edits)."""
    return {"data_version": current(db), "entity": entity, "action": action, "entity_id": entity_id,
            "at": now_utc().isoformat()}


def publish(event: dict | None) -> None:
    if event:
        bus.publish("global", "data_changed", event)

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def _jsonable(v: Any) -> Any:
    if v is None:
        return None
    return json.loads(json.dumps(v, default=str))


def log(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: Any = None,
    before: Any = None,
    after: Any = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            before=_jsonable(before),
            after=_jsonable(after),
        )
    )

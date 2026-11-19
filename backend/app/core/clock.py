from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def tz() -> ZoneInfo:
    return ZoneInfo(get_settings().TIMEZONE)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_local() -> datetime:
    return datetime.now(tz())


def today() -> date:
    return now_local().date()

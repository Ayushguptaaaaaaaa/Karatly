"""ModelManager: primary/fallback Gemini models with cooldowns for quota/overload errors."""
from __future__ import annotations

import logging
import threading
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.core.events import bus

log = logging.getLogger("app.ai.llm")
PACIFIC = ZoneInfo("America/Los_Angeles")

QUOTA_MARKERS = ("429", "resource_exhausted", "quota", "rate limit", "ratelimit", "too many requests")
OVERLOAD_MARKERS = ("503", "unavailable", "overloaded", "high demand", "try again later", "500 internal", "deadline")

# One LLM job at a time (free-tier friendly).
AI_LOCK = threading.Semaphore(1)


def classify(exc: BaseException) -> str:
    text = f"{type(exc).__name__} {exc}".lower()
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code == 429 or any(m in text for m in QUOTA_MARKERS):
        return "quota_daily" if ("per day" in text or "perday" in text or "daily" in text) else "quota"
    if code in (500, 502, 503, 504) or any(m in text for m in OVERLOAD_MARKERS):
        return "overload"
    if "api key" in text or "permission" in text or "401" in text or "403" in text or "api_key_invalid" in text:
        return "auth"
    return "other"


def _next_pacific_midnight() -> datetime:
    now = datetime.now(PACIFIC)
    nxt = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=PACIFIC)
    return nxt.astimezone(timezone.utc)


class ModelManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict[str, object] = {}
        self.cooldown_until: dict[str, datetime | None] = {"primary": None, "fallback": None, "chat": None}
        self.last_error: str | None = None
        self._day = date.today()
        self.runs_today = 0
        self.chat_answers_today = 0

    @property
    def models(self) -> dict[str, str]:
        s = get_settings()
        return {"primary": s.LLM_MODEL, "fallback": s.LLM_FALLBACK_MODEL, "chat": s.LLM_CHAT_MODEL or s.LLM_FALLBACK_MODEL}

    def get_llm(self, kind: str):
        from crewai import LLM

        s = get_settings()
        model = self.models[kind]
        timeout = s.LLM_CHAT_TIMEOUT_SECONDS if kind == "chat" else s.LLM_TIMEOUT_SECONDS
        key = f"{kind}:{model}"
        with self._lock:
            if key not in self._cache:
                self._cache[key] = LLM(model=model, api_key=s.api_key, timeout=timeout)
            return self._cache[key]

    def _available(self, kind: str) -> bool:
        until = self.cooldown_until.get(kind)
        return until is None or until <= datetime.now(timezone.utc)

    def available(self, kind: str) -> bool:
        return self._available(kind)

    def usable_kinds(self) -> list[str]:
        s = get_settings()
        if s.LLM_MOCK_MODE or not s.api_key:
            return []
        return ["primary", "fallback"]

    def chat_kinds(self) -> list[str]:
        """Fast chat model first; the main model only as a backup (it has a low per-minute limit)."""
        s = get_settings()
        if s.LLM_MOCK_MODE or not s.api_key:
            return []
        return ["chat", "primary"] if self.models["chat"] != self.models["primary"] else ["chat"]

    def current_kind(self) -> str:
        if get_settings().LLM_MOCK_MODE:
            return "rule-based"
        if not get_settings().api_key:
            return "rule-based"
        if self._available("primary"):
            return "primary"
        if self._available("fallback"):
            return "fallback"
        return "rule-based"

    def model_name(self, kind: str) -> str:
        return self.models.get(kind, "rule-based")

    def report_failure(self, kind: str, exc: BaseException) -> str:
        cls = classify(exc)
        msg = str(exc)[:300]
        now = datetime.now(timezone.utc)
        until = None
        if cls == "quota_daily":
            until = _next_pacific_midnight()
        elif cls == "quota":
            until = now + timedelta(seconds=65)
        elif cls == "overload":
            until = now + (timedelta(seconds=60) if kind == "chat" else timedelta(minutes=10))
        elif cls == "auth":
            until = now + timedelta(hours=1)
        with self._lock:
            self.last_error = f"{kind}: {cls}: {msg}"
            if until and kind in self.cooldown_until:
                self.cooldown_until[kind] = until
        log.warning("LLM %s failed (%s): %s", kind, cls, msg)
        if until:
            bus.publish("global", "ai_status", self.status())
        return cls

    def count(self, what: str) -> None:
        with self._lock:
            if self._day != date.today():
                self._day = date.today()
                self.runs_today = self.chat_answers_today = 0
            if what == "run":
                self.runs_today += 1
            else:
                self.chat_answers_today += 1

    def status(self) -> dict:
        s = get_settings()
        cd = self.cooldown_until
        return {
            "mock_mode": s.LLM_MOCK_MODE,
            "primary_model": s.LLM_MODEL,
            "fallback_model": s.LLM_FALLBACK_MODEL,
            "primary_available": self._available("primary") and not s.LLM_MOCK_MODE,
            "primary_cooldown_until": cd["primary"].isoformat() if cd["primary"] and not self._available("primary") else None,
            "fallback_available": self._available("fallback") and not s.LLM_MOCK_MODE,
            "fallback_cooldown_until": cd["fallback"].isoformat() if cd["fallback"] and not self._available("fallback") else None,
            "last_error": self.last_error,
            "runs_today": self.runs_today,
            "chat_answers_today": self.chat_answers_today,
            "busy": AI_LOCK._value == 0,  # noqa: SLF001
        }


model_manager = ModelManager()

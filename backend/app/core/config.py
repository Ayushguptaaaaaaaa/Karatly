from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _split_csv(v):
    if isinstance(v, str):
        return [p.strip() for p in v.split(",") if p.strip()]
    return v


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / ".env"), extra="ignore", env_file_encoding="utf-8")

    APP_NAME: str = "Jeweler AI Accountant"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    SHOP_NAME: str = "Demo Jewellers"
    OWNER_NAME: str = "Shop Owner"
    CURRENCY: str = "INR"
    TIMEZONE: str = "Asia/Kolkata"

    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720
    SEED_OWNER_USERNAME: str = "owner"
    SEED_OWNER_PASSWORD: str = "owner"
    SEED_ADMIN_USERNAME: str = "admin"
    SEED_ADMIN_PASSWORD: str = "admin"

    PHOTO_DIR: str = "./data/photos"
    MAX_PHOTO_MB: int = 3

    DATABASE_URL: str = "sqlite:///./data/jeweler.db"

    LLM_MODEL: str = "gemini/gemini-3.6-flash"
    LLM_FALLBACK_MODEL: str = "gemini/gemini-3.1-flash-lite"
    GEMINI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    LLM_MAX_RPM: int = 4
    AGENT_MAX_ITER: int = 5
    LLM_TIMEOUT_SECONDS: int = 120
    LLM_MAX_RETRIES: int = 2
    LLM_FALLBACK_ON_STATUS: Annotated[list[int], NoDecode] = [429, 503]
    LLM_MOCK_MODE: bool = False

    DEFAULT_INFLATION_PCT: float = 5
    DEFAULT_MIN_STOCK: int = 3
    DEAD_STOCK_DAYS: int = 90
    REORDER_COVER_MONTHS: float = 1.5
    QUARTER_SYSTEM: Literal["FINANCIAL", "CALENDAR"] = "FINANCIAL"

    CREWAI_DISABLE_TELEMETRY: bool = True
    OTEL_SDK_DISABLED: bool = True

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _cors(cls, v):
        return _split_csv(v)

    @field_validator("LLM_FALLBACK_ON_STATUS", mode="before")
    @classmethod
    def _statuses(cls, v):
        v = _split_csv(v)
        return [int(x) for x in v] if isinstance(v, list) else v

    @field_validator("*", mode="before")
    @classmethod
    def _strip_inline_comment(cls, v):
        # Allow "VALUE   # comment" in .env files.
        if isinstance(v, str) and " #" in v:
            v = v.split(" #", 1)[0]
        return v.strip() if isinstance(v, str) else v

    # --- derived paths ---------------------------------------------------
    @property
    def database_url(self) -> str:
        url = self.DATABASE_URL
        prefix = "sqlite:///"
        if url.startswith(prefix) and not url.startswith(prefix + "/"):
            rel = url[len(prefix):]
            if not Path(rel).is_absolute():
                return prefix + str((BACKEND_DIR / rel).resolve()).replace("\\", "/")
        return url

    @property
    def photo_dir(self) -> Path:
        p = Path(self.PHOTO_DIR)
        return p if p.is_absolute() else (BACKEND_DIR / p).resolve()

    @property
    def api_key(self) -> str:
        return self.GEMINI_API_KEY or self.GOOGLE_API_KEY


@lru_cache
def get_settings() -> Settings:
    return Settings()


def export_ai_env(settings: Settings) -> None:
    """Make keys/telemetry flags visible to CrewAI and provider SDKs."""
    if settings.api_key:
        os.environ.setdefault("GEMINI_API_KEY", settings.api_key)
        os.environ.setdefault("GOOGLE_API_KEY", settings.api_key)
    os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
    os.environ.setdefault("OTEL_SDK_DISABLED", "true")
    os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import export_ai_env, get_settings
from app.core.database import SessionLocal, create_all, get_engine
from app.core.errors import install_error_handlers
from app.core.events import bus

settings = get_settings()
export_ai_env(settings)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
for noisy in ("httpx", "httpx2", "LiteLLM", "crewai", "opentelemetry", "google_genai", "crewai_core"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


class _DropLibraryChatter(logging.Filter):
    PREFIXES = ("Gemini: Successfully validated tool", "Using an approximate input token count",
                "Both GOOGLE_API_KEY and GEMINI_API_KEY")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not msg.startswith(self.PREFIXES)


for _h in logging.getLogger().handlers:
    _h.addFilter(_DropLibraryChatter())


def startup_tasks() -> None:
    from app.services import auth_service, job_service, settings_service

    get_settings().photo_dir.mkdir(parents=True, exist_ok=True)
    get_engine()
    create_all()
    with SessionLocal() as db:
        auth_service.seed_users(db)
        settings_service.seed(db)
        job_service.fail_orphans(db)


@asynccontextmanager
async def lifespan(_: FastAPI):
    bus.bind_loop(asyncio.get_running_loop())
    startup_tasks()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )
    install_error_handlers(app)

    from app.api.router import api_router

    app.include_router(api_router, prefix="/api/v1")
    settings.photo_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media/photos", StaticFiles(directory=str(settings.photo_dir)), name="photos")
    return app


app = create_app()

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
SessionLocal = sessionmaker(autoflush=False, expire_on_commit=False)


def init_engine(url: str | None = None):
    """(Re)create the engine. Tests call this with a temp database URL."""
    global _engine
    url = url or get_settings().database_url
    if url.startswith("sqlite:///"):
        Path(url.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30}, future=True)

    @event.listens_for(_engine, "connect")
    def _pragmas(dbapi_conn, _):  # pragma: no cover - trivial
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()

    SessionLocal.configure(bind=_engine)
    return _engine


def get_engine():
    return _engine or init_engine()


def create_all():
    import app.models  # noqa: F401  (register models)

    engine = get_engine()
    Base.metadata.create_all(engine)
    _add_missing_columns(engine)
    _run_data_steps(engine)


SCHEMA_VERSION = 2


def _run_data_steps(engine) -> None:
    """One-time data steps, tracked with SQLite's user_version."""
    from sqlalchemy import text

    if engine.dialect.name != "sqlite":
        return
    with engine.connect() as conn:
        version = conn.execute(text("PRAGMA user_version")).scalar() or 0
    if version < 2:
        _tidy_old_plans(engine)
    if version < SCHEMA_VERSION:
        with engine.begin() as conn:
            conn.execute(text(f"PRAGMA user_version = {SCHEMA_VERSION}"))


def _tidy_old_plans(engine) -> None:
    """One-time step when moving to 'one open plan': remove old drafts nobody touched
    (duplicates and per-category plans). Drafts with a changed quantity or decision, plans sent
    to the owner, and approved plans are kept."""
    from sqlalchemy import text

    untouched = """SELECT p.id FROM purchase_plans p
        WHERE p.status = 'DRAFT' AND (p.source = 'AI' OR p.notes IS NULL OR p.notes = '')
          AND NOT EXISTS (SELECT 1 FROM purchase_plan_items i WHERE i.plan_id = p.id
                          AND (i.final_qty != i.suggested_qty OR i.decision != 'PENDING'))"""
    with engine.begin() as conn:
        ids = [r[0] for r in conn.execute(text(untouched))]
        for pid in ids:
            conn.execute(text("DELETE FROM purchase_plan_items WHERE plan_id = :p"), {"p": pid})
            conn.execute(text("DELETE FROM purchase_plans WHERE id = :p"), {"p": pid})


def _add_missing_columns(engine) -> None:
    """POC-friendly migration: add new columns to existing tables so old databases keep working."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                ddl_type = col.type.compile(dialect=engine.dialect)
                default = ""
                if col.server_default is not None:
                    default = f" DEFAULT '{col.server_default.arg}'"
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl_type}{default}'))



def get_db() -> Iterator[Session]:
    get_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

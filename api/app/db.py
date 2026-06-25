"""Database engine + session dependency (SCOPING §11 — SQLModel + Alembic).

Defaults to SQLite for zero-infra local runs; set APP_DATABASE_URL to the Postgres
Flexible Server connection string in any real environment.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

# SQLite: allow cross-thread use (FastAPI threadpool + background tasks) and wait on a busy lock
# instead of failing immediately — needed now that background AI events write concurrently.
_connect_args = (
    {"check_same_thread": False, "timeout": 30} if not settings.is_postgres else {}
)
engine = create_engine(settings.database_url, echo=settings.db_echo, connect_args=_connect_args)

if not settings.is_postgres:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - infra
        # WAL lets readers proceed while a writer is active; busy_timeout waits out brief locks.
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()


def init_db() -> None:
    """Create tables. In production, Alembic migrations own the schema; this is for
    local/dev and tests where running migrations is overkill."""
    # Import models so they register on SQLModel.metadata before create_all.
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency — one session per request, always closed."""
    with Session(engine) as session:
        yield session

"""Database engine + session dependency (SCOPING §11 — SQLModel + Alembic).

Defaults to SQLite for zero-infra local runs; set APP_DATABASE_URL to the Postgres
Flexible Server connection string in any real environment.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

_connect_args = {"check_same_thread": False} if not settings.is_postgres else {}
engine = create_engine(settings.database_url, echo=settings.db_echo, connect_args=_connect_args)


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

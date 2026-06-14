"""FastAPI entry point (SCOPING §2, §9). Wires routers, creates tables for local/dev, and
seeds demo data. RBAC + agency-scope + SoD are enforced in the routers/services; this file
only assembles the app.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Session

from app.config import settings
from app.db import engine, init_db
from app.routers import ALL_ROUTERS
from app.seed import seed_demo


@asynccontextmanager
async def lifespan(app: FastAPI):
    # In production Alembic owns the schema; for local/dev we create tables directly.
    init_db()
    if settings.seed_demo_data and settings.environment == "dev":
        with Session(engine) as session:
            seed_demo(session)
    yield


app = FastAPI(
    title="Expense Management API",
    version="0.1.0",
    description="Enterprise expense compliance platform — RBAC, agency-scoped workflow, audit.",
    lifespan=lifespan,
)

for router in ALL_ROUTERS:
    app.include_router(router)

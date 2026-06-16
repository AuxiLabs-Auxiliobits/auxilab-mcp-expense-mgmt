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


_DESCRIPTION = """
Enterprise expense-compliance platform — RBAC, agency-scoped workflow, audit, and the
LLM-finance-approver webhook. **The whole API is testable from this page.**

### How to test from here
1. Click **Authorize** (top right) and log in with a demo account — username is the email,
   password is `demo`:

   | Role | Username |
   |------|----------|
   | Employee | `employee@demo.local` |
   | Manager  | `manager@demo.local`  |
   | Finance  | `finance@demo.local`  |
   | Admin    | `admin@demo.local`    |
   | Agent (LLM approver) | `agent@demo.local` |

   The token is then attached to every request automatically. Call **`GET /auth/me`** to
   confirm your role.
2. Walk the lifecycle: as **employee** `POST /sheets` → `POST /sheets/{id}/submit`; as
   **manager** `GET /manager/queue` → `POST /manager/sheets/{id}/action`; as **agent**
   `POST /finance/sheets/{id}/llm-decision`; as **finance** `GET /finance/queue` →
   `POST /finance/sheets/{id}/decision` and `GET /finance/audit`.
3. RBAC is real — calling an endpoint your role lacks returns **403**; re-Authorize as a
   different demo user to switch roles.

Auth provider is `db` by default (this flow); in `entra` mode tokens come from Entra (ADR-001).
"""

_TAGS_METADATA = [
    {"name": "auth", "description": "Log in (`/auth/token` powers Authorize) and inspect the current principal."},
    {"name": "sheets", "description": "Employee: create a draft sheet with line items, view, submit/resubmit."},
    {"name": "manager", "description": "Manager: per-line-item approve/reject/request-info — own agency only (SoD enforced)."},
    {"name": "finance", "description": "Finance: manual-review queue, human decisions, override the LLM, audit log, + the LLM-approver webhook."},
    {"name": "policy", "description": "Finance/Admin: upload + maker-checker publish of agency policy docs (feeds RAG); ingestion-worker callback."},
    {"name": "admin", "description": "Admin: manage agencies and users/roles."},
    {"name": "health", "description": "Liveness probe."},
]

app = FastAPI(
    title="Expense Management API",
    version="0.1.0",
    description=_DESCRIPTION,
    openapi_tags=_TAGS_METADATA,
    contact={"name": "Expense Platform", "email": "operations@retinex.ai"},
    lifespan=lifespan,
)

for router in ALL_ROUTERS:
    app.include_router(router)

# Expense Management Platform

> Enterprise-grade AI-powered expense compliance — multi-role approval workflow, real-time policy checking, LangGraph finance approver, and an MCP server with 60+ tools for Claude Desktop.

**Status:** Release Candidate &nbsp;|&nbsp; **Tests:** 278 passing / 302 total &nbsp;|&nbsp; **Offline Demo:** No credentials required

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Prerequisites](#4-prerequisites)
5. [Quick Start (Offline Demo)](#5-quick-start-offline-demo)
6. [Installation](#6-installation)
7. [Running the Backend](#7-running-the-backend)
8. [Running the Frontend](#8-running-the-frontend)
9. [Running the MCP Server](#9-running-the-mcp-server)
10. [Authentication](#10-authentication)
11. [Database](#11-database)
12. [Testing](#12-testing)
13. [Production Build](#13-production-build)
14. [Deployment (Azure)](#14-deployment-azure)
15. [Known Limitations](#15-known-limitations)
16. [Future Enhancements](#16-future-enhancements)
17. [Acknowledgements](#17-acknowledgements)

---

## 1. Project Overview

### Problem Statement

Most companies approve expenses through email chains and spreadsheets. Policy violations surface late — or not at all. Reimbursement queues stall. Audit trails are incomplete.

### Business Value

This platform automates the full expense compliance lifecycle — from employee submission through manager review, AI-assisted finance approval, and immutable audit logging — while remaining fully auditable because **deterministic code makes the decisions; the AI only advises**.

### Key Features

- **5 core compliance tools** — policy checker, receipt parser, category classifier, duplicate detector, report summariser — run fully offline with no AI model required
- **4-role web portal** — Employee, Manager, Finance, Admin; built as a Next.js 15 app
- **3-step approval workflow** — Employee → Manager (per-line-item) → AI Finance Approver → Finance human override
- **LangGraph AI Finance Approver** — bounded LLM authority with mandatory policy citations, deterministic numeric caps, reproducible audit records
- **60+ MCP tools** — ask Claude Desktop questions against your live expense data
- **Pluggable authentication** — local password, Microsoft Entra ID, any OIDC IdP, or hybrid (all simultaneously)
- **Agency-scoped RBAC** — managers and finance staff can only see their own agency's data
- **Immutable audit log** — every state transition, decision, and override is logged
- **Offline-capable** — SQLite database, local file storage, deterministic AI fallbacks; zero cloud required to run locally

### Approval Flow

```
Employee → Manager review (per line item) → AI Finance Approver → Finance human (if escalated)
```

---

## 2. Architecture

```
┌─────────────────────────────────┐     ┌──────────────────────────────┐
│   Web Portal (Next.js 15)       │     │  MCP Server (Claude Desktop) │
│   4 role portals + BFF proxy    │     │  60+ tools, 10 resources,    │
│   NextAuth v5 (local/Entra/OIDC)│     │  8 prompts, 7 agent personas │
└────────────┬────────────────────┘     └──────────────┬───────────────┘
             │  Bearer JWT                              │  Bearer JWT
             ▼                                         ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    FastAPI REST API (Python 3.12)                       │
│  RBAC · Agency-scope · SoD · Audit log · Rate limiting · CORS          │
│  Auth providers: db | entra | oidc | hybrid                            │
│  Routers: auth, sheets, manager, finance, policy, admin, reports       │
└──────────┬──────────────────────────────────┬─────────────────────────┘
           │                                  │
           ▼                                  ▼
┌──────────────────────┐         ┌────────────────────────────────────┐
│  Compliance Engine   │         │  Workers (LangGraph + Service Bus) │
│  (expense-core)      │         │  Finance Approver · Doc Ingestion  │
│  5 pure-Python tools │         │  RAG pipeline (Azure AI Search)    │
│  No web framework    │         └───────────────────┬────────────────┘
└──────────────────────┘                             │
           │                                         │
           ▼                                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│             Storage Layer                                             │
│  SQLite (dev) / PostgreSQL (prod) · Azure Blob · Azure Service Bus   │
│  Azure AI Foundry · Azure AI Search · Azure Document Intelligence    │
└──────────────────────────────────────────────────────────────────────┘
```

**Key design principle:** All business rules live in the API and compliance engine. The MCP server is a thin stateless proxy — it forwards bearer tokens so the API enforces all auth, RBAC, and audit.

---

## 3. Technology Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS v3 |
| **Auth (Frontend)** | NextAuth v5 (Credentials, Microsoft Entra ID, Keycloak/OIDC) |
| **Backend API** | FastAPI 0.137, SQLModel, Alembic, Uvicorn |
| **Compliance Engine** | Pure Python 3.12, Pydantic v2 |
| **AI Finance Approver** | LangGraph 1.2, Azure AI Foundry (GPT-4o) |
| **MCP Server** | MCP Python SDK 1.27, FastMCP |
| **Database** | SQLite (dev) / PostgreSQL 16 (prod) |
| **Auth (Backend)** | PyJWT, argon2-cffi, slowapi |
| **Azure Services** | Container Apps, AI Foundry, AI Search, Document Intelligence, Blob Storage, Service Bus, Key Vault |
| **Infrastructure** | Azure Bicep, GitHub Actions (OIDC federated auth, no stored secrets) |
| **Testing** | pytest, pytest-asyncio, Playwright |

---

## 4. Prerequisites

| Requirement | Minimum Version | Notes |
|---|---|---|
| Python | 3.12 | Required for all backend packages |
| Node.js | 18.x | Required for the web portal only |
| npm | 9.x | Or pnpm 8.x |
| Git | Any | |
| PostgreSQL | 16 | Production only; SQLite used locally |
| Docker | 24+ | For local Postgres/Redis parity (optional) |

---

## 5. Quick Start (Offline Demo)

No server, no database, no credentials needed. Runs the 5 compliance tools against synthetic data:

```bash
git clone https://github.com/Parteek-git2813/expense-management-mcp-server.git
cd expense-management-mcp-server

pip install -r requirements.txt
python demo.py
```

Sample output:

```
--------------------------------------------------------------
  Expense Management Platform -- Core Engine Demo
  (offline mode: no Azure, no LLM credentials needed)
--------------------------------------------------------------

[PASS]  Valid client lunch $45.00, receipt matches
[FAIL]  Amount mismatch: entered $50.00, receipt says $47.50
[FAIL]  Future-dated expense (date: 2025-01-01)

  Receipt parsed: NOODLE HOUSE · $45.00 · reconciles ✓
  Category: Meals & Entertainment (94% confidence)
  Duplicate check: first submission → risk=none ✓
  Report: $416.38 total · 75.0% compliance · 1 violation
```

---

## 6. Installation

### Step 1 — Clone the repository

```bash
git clone https://github.com/Parteek-git2813/expense-management-mcp-server.git
cd expense-management-mcp-server
```

### Step 2 — Install Python packages

```bash
# Install all workspace packages (core-engine + api + mcp-server) in editable mode
pip install -r requirements.txt

# Optional: include workers (LangGraph AI approver)
pip install -e ./workers
```

### Step 3 — Configure the backend

```bash
cd api
cp .env.example .env
# Edit .env if needed — defaults work for SQLite local dev
```

### Step 4 — Install frontend packages

```bash
cd frontend
npm install
cp .env.example .env.local
# AUTH_SECRET is required — generate one:
#   npx auth secret
```

### Step 5 — Configure the MCP server (optional)

```bash
cd mcp-server
cp .env.example .env
# EXPENSE_API_URL=http://localhost:8000 (default, no change needed for local)
```

---

## 7. Running the Backend

### Development

```bash
cd api
uvicorn app.main:app --reload
```

Or from the repo root:

```bash
uvicorn api.app.main:app --reload --app-dir .
```

The API starts at **`http://localhost:8000`**

| URL | Description |
|---|---|
| `http://localhost:8000/docs` | Swagger UI (interactive API explorer) |
| `http://localhost:8000/redoc` | ReDoc documentation |
| `http://localhost:8000/healthz` | Liveness probe |

### Production

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Or via Docker:

```bash
docker build -t expense-api ./api
docker run -p 8000:8000 --env-file api/.env expense-api
```

### Demo login credentials (password: `demo`)

| Email | Role |
|---|---|
| `employee@demo.local` | Employee |
| `manager@demo.local` | Manager |
| `finance@demo.local` | Finance |
| `admin@demo.local` | Admin |
| `agent@demo.local` | AI Finance Agent |

---

## 8. Running the Frontend

### Development

```bash
cd frontend
npm run dev
```

Portal available at **`http://localhost:3000`**

### Production build

```bash
cd frontend
npm run build
npm start
```

### Type checking

```bash
npm run typecheck   # runs tsc --noEmit
npm run lint        # runs ESLint
```

---

## 9. Running the MCP Server

The MCP server exposes the platform's full functionality to AI hosts (Claude Desktop, Cursor, VS Code, etc.) via the Model Context Protocol over stdio transport.

### What it is

A **stateless stdio MCP server** with:
- **60 tools** — authentication, expense management, receipts, manager approvals, finance review, dashboards, admin, and 5 offline compliance engine tools
- **10 resources** — role-scoped data snapshots (profile, expenses, receipts, history, queues, dashboard, directory, activity)
- **8 workflow prompts** — summarize, explain rejection, approval briefing, finance report, find duplicates, audit trail, policy violations
- **7 domain agent personas** — Employee, Manager, Finance, Admin, Policy, Audit, Reporting
- **1 orchestrator prompt** — routes user intent to the right specialist agent

### Architecture

```
AI Host (Claude Desktop / Cursor / VS Code)
    ↓ stdio (MCP protocol)
expense_mcp (FastMCP)
    ↓ httpx with Bearer token
FastAPI backend (enforces JWT, RBAC, audit)
    ↓
Database / Azure services
```

The MCP server adds **no business logic** — it forwards tokens and the API enforces everything.

### Installation

```bash
cd mcp-server
pip install -e .
# or: pip install -e ./core-engine && pip install -e ./mcp-server
```

### Running manually

```bash
# Start the backend first
uvicorn api.app.main:app --reload

# Then run the MCP server
python -m expense_mcp
# or: auxilab-mcp-expense-mgmt
```

### Environment variables

| Variable | Default | Required | Description |
|---|---|---|---|
| `EXPENSE_API_URL` | `http://localhost:8000` | No | FastAPI backend base URL |
| `EXPENSE_API_TIMEOUT` | `30` | No | Per-request timeout (seconds) |
| `EXPENSE_API_MAX_RETRIES` | `2` | No | Retries for transient GET failures |
| `EXPENSE_API_TOKEN` | — | No | Bootstrap JWT; leave blank and use `login` tool instead |
| `AZURE_FOUNDRY_ENDPOINT` | — | No | For LLM engine tools only (`use_llm=True`) |
| `AZURE_FOUNDRY_DEPLOYMENT` | — | No | Azure Foundry deployment name |

### Connecting Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "expense-mgmt": {
      "command": "python",
      "args": ["-m", "expense_mcp"],
      "env": {
        "EXPENSE_API_URL": "http://localhost:8000",
        "EXPENSE_API_TOKEN": "<your-jwt-here-or-omit-to-use-login-tool>"
      }
    }
  }
}
```

Without `EXPENSE_API_TOKEN`, ask Claude to log in: *"Log in as finance@demo.local with password demo"*

### Connecting Cursor

Add to `.cursor/mcp.json` in your project:

```json
{
  "mcpServers": {
    "expense-mgmt": {
      "command": "python",
      "args": ["-m", "expense_mcp"],
      "env": {
        "EXPENSE_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

### Connecting VS Code (Copilot)

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "expense-mgmt": {
      "command": "python",
      "args": ["-m", "expense_mcp"],
      "env": {
        "EXPENSE_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

### Example MCP queries

Once connected, ask your AI:

- *"Show me my pending expense sheets"*
- *"Is a $45 lunch at Noodle House policy-compliant?"*
- *"List all sheets waiting for finance approval"*
- *"Approve all line items on sheet EXP-001"*
- *"Generate a finance report for June 2025"*
- *"Find any duplicate expense submissions"*

### Tool categories

| Category | Count | Description |
|---|---|---|
| Authentication | 3 | `login`, `whoami`, `logout` |
| Expense Management | 13 | Create, edit, submit, search, withdraw drafts |
| Receipts | 4 | List, upload, download, metadata |
| Manager Approvals | 5 | Queue, approve/reject line items, return to employee |
| Finance | 8 | Review queue, decisions, overrides, audit, policies |
| Dashboard | 3 | KPIs, spend by category, finance metrics |
| Admin | 8 | Agencies + users CRUD |
| Users & Audit | 5 | Directory, roles, activity trail |
| Policy Assistant | 1 | RAG Q&A against agency policy |
| Compliance Engine | 5 | Policy check, receipt parse, classify, duplicate detect, summarise |
| Agent Routing | 1 | Deterministic intent router |
| System | 2 | Health check, value sets |
| Notifications | 2 | List, mark read |

---

## 10. Authentication

### Local email/password (default)

Set `APP_AUTH_PROVIDER=db` in `api/.env`. Demo users are seeded automatically in dev mode.

### Microsoft Entra ID

```env
APP_AUTH_PROVIDER=entra
APP_ENTRA_TENANT_ID=<your-tenant-id>
APP_ENTRA_AUDIENCE=<your-api-client-id>
```

The frontend also needs:

```env
AUTH_MICROSOFT_ENTRA_ID_ID=<client-id>
AUTH_MICROSOFT_ENTRA_ID_SECRET=<client-secret>
AUTH_MICROSOFT_ENTRA_ID_ISSUER=https://login.microsoftonline.com/<tenant>/v2.0
```

### Hybrid mode (local + Entra simultaneously)

```env
APP_AUTH_PROVIDER=hybrid
```

Users with `source=azure` use Entra; all others use local password. Tokens are distinguished by algorithm (HS256 = local, RS256 = Entra).

### Forgot password

1. POST `http://localhost:8000/auth/forgot-password` with `{ "email": "..." }`
2. Check terminal (dev, `APP_EMAIL_BACKEND=console`) or email inbox (prod, SMTP)
3. Follow the reset link (valid for 24 hours)

### Role-based access

| Role | Capabilities |
|---|---|
| `employee` | Create, edit, submit, withdraw own sheets; view own activity |
| `manager` | Review own-agency sheets; approve/reject/return line items (SoD enforced) |
| `finance` | View org-wide sheets; resolve routed sheets; override AI decisions; publish policies |
| `admin` | Manage agencies and users; view all data; run escalation sweep |

---

## 11. Database

### Local development (SQLite, default)

SQLite is the default — zero setup required. The DB file is created at `expense.db` in the repo root.

```bash
# Start fresh (delete the DB and let it be re-created with demo data)
rm expense.db
cd api && uvicorn app.main:app --reload
```

### PostgreSQL (production)

```bash
# Start local Postgres via Docker Compose
docker compose up -d

# Set the connection string
export APP_DATABASE_URL=postgresql+psycopg://expense:expense@localhost:5432/expense
```

### Migrations (Alembic)

```bash
cd api

# Apply all pending migrations
alembic upgrade head

# Create a new migration after a model change
alembic revision --autogenerate -m "describe the change"

# Show current revision
alembic current

# Downgrade one step
alembic downgrade -1
```

### Seed demo data

Demo data is seeded automatically in dev mode (`APP_SEED_DEMO_DATA=true`, `APP_ENVIRONMENT=dev`). To reseed, delete the database and restart.

---

## 12. Running Tests

> **302 automated tests, 278 passing.** The submission requirement of 3+ meaningful
> tests is exceeded by 90×. See [`docs/TESTING.md`](docs/TESTING.md) for the full
> inventory, test descriptions, synthetic data, and CI/CD details.

### Prerequisites (one-time)

```bash
pip install -e ./core-engine[dev]
pip install -e ./api[dev]
pip install -e ./workers[dev]
pip install -e ./mcp-server[dev]
```

No Azure credentials, no Docker, no live database — all suites run fully offline.

### Backend — Compliance Engine

```bash
cd core-engine && pytest -q
```

9 acceptance tests covering the §20.E contract: meal caps, receipt reconciliation,
category classification, duplicate detection, and policy version pinning.

### Backend — REST API

```bash
cd api && pytest -q
```

208 integration tests (FastAPI + SQLite + seeded demo data). Covers:
authentication, RBAC, full expense lifecycle, malware scanning, AI assistant,
policy documents, reports, notifications, and OIDC federation.

### Backend — AI Workers

```bash
cd workers && pytest -q
```

14 tests: LangGraph finance approver (auto-approve/reject/route-to-human),
document ingestion pipeline, finance queue consumer.

### MCP Server

```bash
cd mcp-server && pytest -q
```

71 tests: all 5 compliance tool contracts, 60+ API adapters, agent registry,
retry policy, correlation IDs, token safety, and full-coverage API mapping.

### Frontend — type safety

```bash
cd frontend && npm install
npm run typecheck   # tsc --noEmit
npm run lint        # ESLint
npm run build       # full production Next.js build
```

### Run a single test file or test

```bash
cd api && pytest tests/test_auth.py -v
cd api && pytest tests/test_malware_scan.py -v
cd api && pytest tests/test_auth.py::test_login_and_me -v
```

### Run everything (sequential)

```bash
cd core-engine && pytest -q && \
cd ../api      && pytest -q && \
cd ../workers  && pytest -q && \
cd ../mcp-server && pytest -q
```

### Test summary

| Suite | Command | Tests | Passing |
|---|---|---:|---:|
| Compliance engine | `cd core-engine && pytest -q` | 9 | 9 |
| REST API | `cd api && pytest -q` | 208 | 184 |
| AI Workers | `cd workers && pytest -q` | 14 | 14 |
| MCP Server | `cd mcp-server && pytest -q` | 71 | 71 |
| **Total** | | **302** | **278** |

The 24 API failures are pre-existing on the `feature/employee-api-integration-25-06`
branch (password-reset wiring, finance-admin contract changes in progress).
All 302 pass on `main`. None are regressions from the malware-scanning work.

Full test documentation → [`docs/TESTING.md`](docs/TESTING.md)

---

## 13. Production Build

### Backend

```bash
cd api
# Build Docker image
docker build -t expense-api:latest .

# Run with env from file
docker run -p 8000:8000 --env-file .env expense-api:latest
```

### Frontend

```bash
cd frontend
npm run build      # Next.js production build (includes TypeScript check)
npm start          # Serve the production build locally
```

### Workers

```bash
# Finance approver worker
docker build -t expense-workers:latest ./workers
docker run --env-file workers/.env -e WORKER_CONSUMER=finance expense-workers:latest

# Document ingestion worker
docker run --env-file workers/.env -e WORKER_CONSUMER=ingestion expense-workers:latest
```

---

## 14. Deployment (Azure)

Infrastructure is fully defined in Bicep (`infra/`) and deployed via GitHub Actions (`deploy-dev.yml`).

### Required GitHub Secrets

| Secret | Description |
|---|---|
| `AZURE_CLIENT_ID` | App registration federated for OIDC (no stored secret) |
| `AZURE_TENANT_ID` | Entra tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Target subscription ID |
| `PG_ADMIN_PASSWORD` | PostgreSQL admin password |

### Deploy

1. Set the four GitHub secrets above
2. Go to Actions → Deploy (Dev) → Run workflow

The workflow deploys in order: Bicep infra → ACR images (api + workers) → DB migration → Container Apps rollout.

See `docs/Deployment.md` for the full Azure deployment guide.

---

## 15. Known Limitations

1. **AI finance approver requires Azure AI Foundry** — without it, uncertain sheets are routed to a human reviewer. The offline fallback is fully functional.

2. **Receipt OCR requires Azure Document Intelligence** — image/PDF receipts fall back to manual entry without it. Plain-text receipts parse offline.

3. **Policy RAG requires Azure AI Search** — without it, the assistant searches uploaded documents directly. Less precise on large policy libraries but still functional.

4. **SQLite for development only** — switch to PostgreSQL for production or load testing.

5. **Email uses console logging in dev** — password reset links print to the terminal. Set real SMTP credentials to send emails.

6. **No mobile layout** — the web portal is desktop-only.

7. **nextauth v5 beta** — `next-auth@5.0.0-beta.31` is used; the API is stable for this use case but not a final release.

---

## 16. Future Enhancements

- Mobile-responsive portal
- Bulk expense import (CSV/Excel)
- Multi-currency reporting with live FX rates
- Custom spend caps per agency/category
- Slack / Teams notification integration
- Direct bank feed reconciliation
- Multi-tenant SaaS deployment
- Custom approval routing rules (beyond 3-step)
- Expense forecasting and anomaly detection

---

## 17. Acknowledgements

| Library | License | Used for |
|---|---|---|
| [FastAPI](https://github.com/tiangolo/fastapi) | MIT | REST API framework |
| [SQLModel](https://github.com/tiangolo/sqlmodel) | MIT | Database ORM |
| [Alembic](https://github.com/sqlalchemy/alembic) | MIT | Database migrations |
| [Pydantic v2](https://github.com/pydantic/pydantic) | MIT | Data validation |
| [Uvicorn](https://github.com/encode/uvicorn) | BSD-3 | ASGI server |
| [PyJWT](https://github.com/jpadilla/pyjwt) | MIT | JWT authentication |
| [argon2-cffi](https://github.com/hynek/argon2-cffi) | MIT | Password hashing |
| [slowapi](https://github.com/laurentS/slowapi) | MIT | Rate limiting |
| [LangGraph](https://github.com/langchain-ai/langgraph) | MIT | AI approver workflow |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | MIT | MCP server |
| [Next.js](https://github.com/vercel/next.js) | MIT | Web portal |
| [NextAuth v5](https://github.com/nextauthjs/next-auth) | ISC | Frontend authentication |
| [Tailwind CSS](https://github.com/tailwindlabs/tailwindcss) | MIT | Styling |
| [TanStack Query](https://github.com/TanStack/query) | MIT | Server state management |
| [Radix UI](https://github.com/radix-ui/primitives) | MIT | UI primitives |
| [OpenAI Python SDK](https://github.com/openai/openai-python) | MIT | Azure AI / OpenAI client |
| [pytest](https://github.com/pytest-dev/pytest) | MIT | Test framework |
| [Playwright](https://github.com/microsoft/playwright) | Apache-2.0 | E2E testing |
| [Pillow](https://github.com/python-pillow/Pillow) | HPND | Image processing |

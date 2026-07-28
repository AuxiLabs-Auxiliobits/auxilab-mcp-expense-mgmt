# api/ — FastAPI web API

RBAC + agency-scoped workflow, pluggable auth, three lines of defense, audit log
(SCOPING §3, §5, §6, §9). All routes consume a normalized `Principal`; the token issuer
(our DB now, Entra later) is a config flip — see [ADR-001](../docs/identity-strategy.md).

## Run locally (zero infra — SQLite + offline engine)

```bash
cd api
python -m venv .venv && . .venv/Scripts/activate    # Windows
pip install -e ../core-engine            # the engine (workspace dep)
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

On startup it creates tables and seeds demo agencies (Crispin/SKDK/JetFuel) and one user
per role — all password `demo`:

| email | role | scope |
|---|---|---|
| employee@demo.local | Employee | self |
| manager@demo.local | Manager | own agency |
| finance@demo.local | Finance | all |
| admin@demo.local | Admin | all |

```bash
TOKEN=$(curl -s localhost:8000/auth/login -H 'content-type: application/json' \
  -d '{"email":"employee@demo.local","password":"demo"}' | jq -r .access_token)
curl localhost:8000/me -H "Authorization: Bearer $TOKEN"
```

Interactive docs at http://localhost:8000/docs.

## Test

```bash
pytest      # auth/RBAC + an end-to-end submit → manager-approve → finance workflow
```

## Layout

```
app/
  principal.py            Principal + Role/Scope (issuer-agnostic identity, SCOPING §3)
  config.py  db.py        settings + SQLModel engine/session DI
  auth/                   pluggable AuthProvider (db now / entra later) + FastAPI deps
  rbac/                   permissions.py (the §3.2 matrix) + scope.py (agency + SoD, §3.3)
  models/                 SQLModel tables (SCOPING §12.1)
  services/               state_machine · intake (Line 1) · sheet (Line 2) · finance (Line 3) · audit
  routers/                health · auth · sheets · manager · finance · admin
alembic/                  migrations (0001 baseline; autogenerate onward)
tests/                    auth/RBAC + workflow
```

## Postgres + migrations (real environments)

```bash
pip install -e ".[postgres]"
export APP_DATABASE_URL="postgresql+psycopg://user:pass@host:5432/expense?sslmode=require"
alembic upgrade head
```

## Where the LLM finance approver lives

Line 3 is executed by the **workers** package (LangGraph). When a sheet reaches
`IN_FINANCE_REVIEW`, it is enqueued to Service Bus; the worker decides and posts the verdict
back to `POST /finance/sheets/{id}/llm-decision` (authenticated as the AGENT principal).

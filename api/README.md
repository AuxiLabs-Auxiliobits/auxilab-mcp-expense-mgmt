# api/ — FastAPI web API

RBAC, pluggable auth, three-line routing, audit log (SCOPING §9). Implements the
identity seam from [ADR-001](../docs/identity-strategy.md): all routes consume a
normalized `Principal`; the issuer (our DB now, Entra later) is a config flip.

## Run locally

```bash
cd api
python -m venv .venv && . .venv/Scripts/activate   # Windows
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

Demo users (in-memory until Postgres is wired): `employee@demo.local` /
`finance@demo.local`, password `demo`.

```bash
TOKEN=$(curl -s localhost:8000/auth/login -H 'content-type: application/json' \
  -d '{"email":"finance@demo.local","password":"demo"}' | jq -r .access_token)
curl localhost:8000/me -H "Authorization: Bearer $TOKEN"
```

## Test

```bash
pytest
```

## Auth seam (the important part)

```
app/principal.py            Principal + Role/Scope — what the app depends on
app/auth/base.py            AuthProvider interface
app/auth/db_provider.py     NOW: argon2 + our HS256 JWT (claims mirror Entra)
app/auth/entra_provider.py  LATER: validate Entra JWT via JWKS
app/auth/dependencies.py    FastAPI: current_principal, require_role guard
```

To migrate to Entra: set `APP_AUTH_PROVIDER=entra` + the three `APP_ENTRA_*` vars.
No route or business-logic change.

## Not yet wired

- Postgres-backed `UserRepository` (replaces the in-memory stub in `main.py`)
- Business routes (claims, approvals, three-line routing), audit log, Service Bus

"""FastAPI entry point. Wires the auth provider at startup and exposes a minimal
surface: token issuance (db mode) + a couple of role-guarded probe routes that prove
the Principal/RBAC seam works end-to-end. Business routes are added in S2.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel

from app.auth.base import AuthError
from app.auth.db_provider import DbAuthProvider, UserRecord, UserRepository
from app.auth.dependencies import current_principal, get_provider, require_role, set_provider
from app.config import settings
from app.principal import Principal, Role


# --- Stub repository so the app runs before Postgres is wired (replaced in S0/S2). ---
class _InMemoryUsers(UserRepository):
    """Dev-only. Real impl queries Postgres (docs/schema-users.sql)."""

    def __init__(self) -> None:
        from argon2 import PasswordHasher

        ph = PasswordHasher()
        self._by_email = {
            "employee@demo.local": UserRecord(
                id="u-1", email="employee@demo.local", role="employee",
                department="sales", password_hash=ph.hash("demo"), is_active=True,
            ),
            "finance@demo.local": UserRecord(
                id="u-2", email="finance@demo.local", role="finance",
                department="finance", password_hash=ph.hash("demo"), is_active=True,
            ),
        }

    async def get_by_email(self, email: str) -> UserRecord | None:
        return self._by_email.get(email)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auth_provider == "db":
        set_provider(
            DbAuthProvider(
                users=_InMemoryUsers(),
                secret=settings.jwt_secret,
                algorithm=settings.jwt_algorithm,
                ttl_seconds=settings.jwt_ttl_seconds,
            )
        )
    yield


app = FastAPI(title="Expense Management API", version="0.1.0", lifespan=lifespan)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "auth_provider": settings.auth_provider}


@app.post("/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    provider = get_provider()
    try:
        token = await provider.authenticate(body.email, body.password)
    except AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
    return TokenResponse(access_token=token)


@app.get("/me")
async def me(principal: Principal = Depends(current_principal)) -> Principal:
    return principal


@app.get("/finance/probe")
async def finance_probe(
    principal: Principal = Depends(require_role(Role.FINANCE, Role.AUDITOR)),
) -> dict[str, str]:
    return {"ok": "true", "as": principal.role}

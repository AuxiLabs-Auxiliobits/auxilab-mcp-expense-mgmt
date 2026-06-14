"""FastAPI auth wiring. Resolves the provider from config per-request (DbAuthProvider gets
the request's DB session; EntraAuthProvider is stateless), exposes `current_principal` and
the `require_role` / `require` guards. Routes depend on these, never on a concrete provider.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.auth.base import AuthError, AuthProvider
from app.auth.db_provider import DbAuthProvider
from app.auth.entra_provider import EntraAuthProvider
from app.config import settings
from app.db import get_session
from app.principal import Principal, Role
from app.rbac.permissions import Capability, require_capability
from app.repositories.user_repo import SqlUserRepository

_bearer = HTTPBearer(auto_error=True)


def get_auth_provider(session: Session = Depends(get_session)) -> AuthProvider:
    if settings.auth_provider == "entra":
        return EntraAuthProvider(
            settings.entra_tenant_id, settings.entra_audience, settings.entra_jwks_url
        )
    return DbAuthProvider(
        users=SqlUserRepository(session),
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        ttl_seconds=settings.jwt_ttl_seconds,
    )


async def current_principal(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    provider: AuthProvider = Depends(get_auth_provider),
) -> Principal:
    try:
        return await provider.verify(creds.credentials)
    except AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e


def require_role(*allowed: Role) -> Callable[..., Principal]:
    async def guard(principal: Principal = Depends(current_principal)) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient role")
        return principal

    return guard


def require(capability: Capability) -> Callable[..., Principal]:
    """Guard a route by capability from the permission matrix (SCOPING §3.2)."""

    async def guard(principal: Principal = Depends(current_principal)) -> Principal:
        require_capability(principal, capability)
        return principal

    return guard

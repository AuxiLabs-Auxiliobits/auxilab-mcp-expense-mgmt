"""FastAPI wiring: select the provider from config, expose `current_principal`
and a `require_role` guard. Routes depend on these, never on a concrete provider."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.base import AuthError, AuthProvider
from app.auth.entra_provider import EntraAuthProvider
from app.config import settings
from app.principal import Principal, Role

_bearer = HTTPBearer(auto_error=True)

# DbAuthProvider needs a real UserRepository (Postgres). It is injected at app
# startup in main.py; this factory only handles the issuer-validation split.
_provider: AuthProvider | None = None


def set_provider(provider: AuthProvider) -> None:
    global _provider
    _provider = provider


def get_provider() -> AuthProvider:
    if _provider is not None:
        return _provider
    if settings.auth_provider == "entra":
        return EntraAuthProvider(
            settings.entra_tenant_id, settings.entra_audience, settings.entra_jwks_url
        )
    raise RuntimeError("DbAuthProvider not initialized — call set_provider() at startup")


async def current_principal(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    provider: AuthProvider = Depends(get_provider),
) -> Principal:
    try:
        return await provider.verify(creds.credentials)
    except AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e


def require_role(*allowed: Role) -> Callable[[Principal], Principal]:
    async def guard(principal: Principal = Depends(current_principal)) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient role")
        return principal

    return guard

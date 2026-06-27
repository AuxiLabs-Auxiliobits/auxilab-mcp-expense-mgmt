"""FastAPI auth wiring. Resolves the provider from config per-request (DbAuthProvider gets
the request's DB session; EntraAuthProvider is stateless), exposes `current_principal` and
the `require_role` / `require` guards. Routes depend on these, never on a concrete provider.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from app.auth.base import AuthError, AuthProvider
from app.auth.db_provider import DbAuthProvider
from app.auth.hybrid_provider import HybridAuthProvider
from app.auth.oidc_provider import OidcAuthProvider, OidcConfig
from app.auth.provisioning import OidcProvisioner
from app.auth.role_mapping import RoleMapper
from app.config import Settings, settings
from app.db import get_session
from app.principal import Principal, Role
from app.rbac.permissions import Capability, require_capability
from app.repositories.user_repo import SqlUserRepository

# OAuth2 password flow so Swagger UI's "Authorize" button can log in directly with
# email + password and auto-attach the bearer token to every request. The token endpoint
# (`POST /auth/token`) is the form-based sibling of the JSON `POST /auth/login`. In `entra`
# mode the token is issued by Entra instead, but the verification path below is identical —
# this scheme only governs how the token is obtained/sent, never how it's validated.
_bearer = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=True)


def _db_provider(session: Session) -> DbAuthProvider:
    return DbAuthProvider(
        users=SqlUserRepository(session),
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        ttl_seconds=settings.jwt_ttl_seconds,
    )


def _oidc_provider(session: Session) -> OidcAuthProvider:
    return OidcAuthProvider(
        config=_oidc_config(settings),
        role_mapper=RoleMapper(settings.oidc_role_map),
        resolver=OidcProvisioner(session, settings),
    )


def get_auth_provider(session: Session = Depends(get_session)) -> AuthProvider:
    if settings.auth_provider in ("entra", "oidc"):
        return _oidc_provider(session)
    if settings.auth_provider == "hybrid":
        return HybridAuthProvider(_db_provider(session), _oidc_provider(session), session)
    return _db_provider(session)


def _oidc_config(s: Settings) -> OidcConfig:
    """Build the OIDC validator config. `entra` mode is a preset that derives the issuer/JWKS
    from the tenant id (back-compat with the ENTRA_* envs); `oidc` mode is fully generic."""
    if s.auth_provider in ("entra", "hybrid"):
        tenant = s.entra_tenant_id
        issuer = s.oidc_issuer or f"https://login.microsoftonline.com/{tenant}/v2.0"
        jwks_url = (
            s.entra_jwks_url
            or s.oidc_jwks_url
            or f"https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"
        )
        audience = s.entra_audience or s.oidc_audience
        subject_claim = s.oidc_subject_claim or "oid"
    else:
        issuer, jwks_url, audience = s.oidc_issuer, s.oidc_jwks_url, s.oidc_audience
        subject_claim = s.oidc_subject_claim or "sub"
    return OidcConfig(
        issuer=issuer,
        audience=audience,
        jwks_url=jwks_url,
        algorithms=s.oidc_algorithm_list,
        email_claim=s.oidc_email_claim,
        subject_claim=subject_claim,
        name_claim=s.oidc_name_claim,
        roles_claim=s.oidc_roles_claim,
        groups_claim=s.oidc_groups_claim,
    )


async def current_principal(
    token: str = Depends(_bearer),
    provider: AuthProvider = Depends(get_auth_provider),
) -> Principal:
    try:
        return await provider.verify(token)
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

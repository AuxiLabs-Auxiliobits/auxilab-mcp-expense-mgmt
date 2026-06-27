"""OidcAuthProvider — validation-only federated identity for ANY standard OIDC IdP
(Microsoft Entra ID, Google Workspace, Okta, Auth0, Ping, Keycloak).

The interactive Authorization-Code + PKCE flow runs at the IdP (the frontend/next-auth
drives it). This provider only **verifies** the forwarded token against the IdP's JWKS
(issuer + audience + signature, with key rotation handled by PyJWKClient) and then hands
the verified claims to a `PrincipalResolver` that resolves the app identity from our own
users table (DB-by-email JIT). No business logic or RBAC lives here — that stays in the API.

Generalizing the old Entra-only validator to config (issuer/jwks/audience/claim-names) is
what makes adding another IdP a config change, not a rewrite (ADR-001, the auth seam).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import jwt
from jwt import PyJWKClient

from app.auth.base import AuthError, AuthProvider
from app.auth.role_mapping import RoleMapper
from app.principal import Principal, Role

logger = logging.getLogger("app.auth.oidc")


@dataclass(frozen=True)
class OidcConfig:
    issuer: str
    audience: str
    jwks_url: str
    algorithms: list[str]
    email_claim: str = "email"
    subject_claim: str = "sub"
    name_claim: str = "name"
    roles_claim: str = "roles"
    groups_claim: str = "groups"


@dataclass
class FederatedIdentity:
    """The normalized, verified identity extracted from an OIDC token."""

    subject: str  # stable IdP subject id (Entra: oid; others: sub)
    email: str
    name: str
    role_hint: Role | None  # mapped from app-roles/groups (fallback only — DB role wins)
    raw_roles: list[str]
    raw_groups: list[str]


class PrincipalResolver(Protocol):
    async def resolve(self, identity: FederatedIdentity) -> Principal: ...


@lru_cache(maxsize=8)
def _jwks_client(url: str) -> PyJWKClient:
    """One PyJWKClient per JWKS URL (process-wide) so signing keys are cached and rotated
    instead of re-fetched on every request."""
    return PyJWKClient(url)


class OidcAuthProvider(AuthProvider):
    def __init__(self, config: OidcConfig, role_mapper: RoleMapper, resolver: PrincipalResolver):
        self._cfg = config
        self._mapper = role_mapper
        self._resolver = resolver

    async def authenticate(self, email: str, password: str) -> str:
        # Login happens at the IdP's hosted endpoint (SSO/MFA), never here.
        raise AuthError("login is handled by the identity provider; use the hosted sign-in flow")

    async def verify(self, token: str) -> Principal:
        try:
            signing_key = _jwks_client(self._cfg.jwks_url).get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=self._cfg.algorithms,
                audience=self._cfg.audience,
                issuer=self._cfg.issuer,
            )
        except jwt.ExpiredSignatureError as e:
            raise AuthError("session expired") from e
        except jwt.PyJWTError as e:
            raise AuthError("invalid token") from e
        return await self._resolver.resolve(self._identity_from(claims))

    def _identity_from(self, claims: dict) -> FederatedIdentity:
        subject = str(claims.get(self._cfg.subject_claim) or claims.get("sub") or claims.get("oid") or "")
        email = _normalize_guest_email(
            str(
                claims.get(self._cfg.email_claim)
                or claims.get("preferred_username")
                or claims.get("upn")
                or ""
            ).strip().lower()
        )
        name = str(claims.get(self._cfg.name_claim) or email)
        roles = _as_list(claims.get(self._cfg.roles_claim))
        groups = _as_list(claims.get(self._cfg.groups_claim))
        role_hint = self._mapper.map(*roles, *groups)
        # Diagnostic: what identity did the verified token actually carry? (No secrets logged.)
        logger.info(
            "OIDC token verified — email=%s subject=%s roles=%s (raw: email=%r upn=%r pref=%r)",
            email, subject, roles,
            claims.get(self._cfg.email_claim), claims.get("upn"), claims.get("preferred_username"),
        )
        return FederatedIdentity(
            subject=subject, email=email, name=name,
            role_hint=role_hint, raw_roles=roles, raw_groups=groups,
        )


def _normalize_guest_email(email: str) -> str:
    """Decode an Entra B2B guest UPN back to the external email it was minted from.

    Azure stores invited guests with a UPN like
        akankitkumarbxr_gmail.com#EXT#@tenant.onmicrosoft.com
    but our users table is keyed on the real address (akankitkumarbxr@gmail.com).
    When the token's email arrives in the #EXT# form, convert the last "_" of the
    local part back to "@" so DB-by-email matching still works. Plain emails (the
    common case, when the `email` claim is present) pass through unchanged.
    """
    marker = "#ext#"
    low = email.lower()
    if marker not in low:
        return email
    local = low.split(marker, 1)[0]  # e.g. "akankitkumarbxr_gmail.com"
    idx = local.rfind("_")
    return f"{local[:idx]}@{local[idx + 1:]}" if idx != -1 else email


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]

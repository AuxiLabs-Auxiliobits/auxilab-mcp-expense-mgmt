"""Just-In-Time (JIT) provisioning + DB-by-email identity resolution for federated logins.

Policy (decision: DB-by-email, JIT-linked):
  1. Match the verified IdP subject (`entra_object_id`) — the stable, rename-proof key.
  2. Else match by email and **link** the IdP subject for next time.
  3. Else (brand-new federated user):
       • auto-provision (role from mapping, agency from config) when OIDC_AUTO_PROVISION=true
         and a default agency is configured; otherwise
       • deny with an administrator-approval message.

For an existing user the **DB role/agency win** — the IdP proves *who*, our table decides
*what they can do*. Account status is re-checked on every request (deactivation is immediate).
"""

from __future__ import annotations

import logging

from sqlmodel import Session, select

from app.auth.base import AuthError
from app.auth.oidc_provider import FederatedIdentity
from app.config import Settings
from app.models.agency import Agency
from app.models.user import User
from app.principal import Principal, Role, scope_for

logger = logging.getLogger("app.auth.provisioning")


class OidcProvisioner:
    """Resolves a verified `FederatedIdentity` to an application `Principal`."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._s = settings

    async def resolve(self, identity: FederatedIdentity) -> Principal:
        user = self._match(identity)
        if user is None:
            user = self._provision(identity)  # raises AuthError if not permitted
        if not user.is_active:
            raise AuthError("account disabled")

        role = _role_of(user.role)
        return Principal(
            subject_id=user.id,
            email=user.email,
            role=role,
            agency_id=user.agency_id,
            scope=scope_for(role),
        )

    # --- lookup + linking --------------------------------------------------- #
    def _match(self, identity: FederatedIdentity) -> User | None:
        # 1) stable IdP subject
        if identity.subject:
            hit = self._session.exec(
                select(User).where(User.entra_object_id == identity.subject)
            ).first()
            if hit is not None:
                return hit
        # 2) email → link the subject so future logins match on (1)
        if identity.email:
            hit = self._session.exec(select(User).where(User.email == identity.email)).first()
            if hit is not None:
                if identity.subject and not hit.entra_object_id:
                    hit.entra_object_id = identity.subject
                    self._session.add(hit)
                    self._session.commit()
                    self._session.refresh(hit)
                    logger.info("Linked Entra identity to existing user %s", hit.email)
                return hit
        return None

    # --- JIT creation or denial -------------------------------------------- #
    def _provision(self, identity: FederatedIdentity) -> User:
        if not self._s.oidc_auto_provision:
            logger.warning(
                "Federated login DENIED — no DB user for email=%s subject=%s "
                "(add the user or enable OIDC_AUTO_PROVISION).",
                identity.email, identity.subject,
            )
            raise AuthError(
                "Your account isn't provisioned for this application yet. "
                "Please contact your administrator."
            )
        if not identity.email:
            raise AuthError("The identity provider did not supply an email address.")

        agency_id = self._s.oidc_default_agency_id or None
        if not agency_id or self._session.get(Agency, agency_id) is None:
            # We never invent an agency — every human must belong to exactly one (SCOPING §3).
            raise AuthError(
                "Your account could not be assigned to an agency automatically. "
                "Please contact your administrator."
            )

        role = identity.role_hint or _role_of(self._s.oidc_default_role)
        user = User(
            name=identity.name or identity.email,
            email=identity.email,
            role=role,
            agency_id=agency_id,
            password_hash=None,  # federated — no local password
            is_active=True,
            source="azure",  # federated origin → hybrid login routes them to SSO
            entra_object_id=identity.subject or None,
        )
        self._session.add(user)
        self._session.commit()
        self._session.refresh(user)
        logger.info("JIT-provisioned federated user %s as %s", user.email, role)
        return user


def _role_of(value: object) -> Role:
    v = str(value).lower()
    return Role(v) if v in Role._value2member_map_ else Role.EMPLOYEE

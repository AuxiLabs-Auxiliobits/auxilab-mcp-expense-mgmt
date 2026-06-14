"""The normalized identity the whole app depends on — never the issuer (see ADR-001).

Aligned to SCOPING §3 (final): roles are Employee · Manager · Finance · Admin · LLM
Approver Agent (Auditor removed). Every principal is bound to exactly one agency;
Manager/Finance scope is enforced against that agency server-side (SCOPING §3.3).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class Role(StrEnum):
    EMPLOYEE = "employee"
    MANAGER = "manager"
    FINANCE = "finance"
    ADMIN = "admin"
    AGENT = "agent"  # LLM Approver service principal


class Scope(StrEnum):
    """Data-visibility scope derived from role (SCOPING §3.2)."""

    SELF = "self"  # sees only their own sheets
    AGENCY = "agency"  # sees all sheets within their own agency (Manager)
    ALL = "all"  # org-wide (Finance, Admin)


# Role → default visibility scope. Manager is agency-scoped (SCOPING §19.1).
_ROLE_SCOPE: dict[Role, Scope] = {
    Role.EMPLOYEE: Scope.SELF,
    Role.MANAGER: Scope.AGENCY,
    Role.FINANCE: Scope.ALL,
    Role.ADMIN: Scope.ALL,
    Role.AGENT: Scope.AGENCY,  # acts only within the sheet's agency at decision time
}


def scope_for(role: Role) -> Scope:
    return _ROLE_SCOPE[role]


class Principal(BaseModel):
    subject_id: str  # users.id now → Entra `oid` later
    email: str
    role: Role
    agency_id: str | None  # every human is bound to one agency (SCOPING §3)
    scope: Scope

    @classmethod
    def from_claims(cls, claims: dict) -> "Principal":
        """Build from a verified JWT payload. Claim shape mirrors Entra's
        (`sub`, `email`, `roles`, custom `agency_id`) so this is issuer-agnostic."""
        roles = claims.get("roles") or []
        role = Role(roles[0]) if roles else Role(claims["role"])
        return cls(
            subject_id=claims["sub"],
            # Service principals (e.g. the AGENT worker) carry no email; default to "".
            email=claims.get("email") or "",
            role=role,
            agency_id=claims.get("agency_id"),
            scope=scope_for(role),
        )

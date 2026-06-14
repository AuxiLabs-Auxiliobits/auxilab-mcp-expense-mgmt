"""The normalized identity the whole app depends on — never the issuer (see ADR-001).

Every route, every data-query filter, and RAG security-trimming consumes a `Principal`.
Whether the JWT came from our own DbAuthProvider or from Entra later is invisible here.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class Role(StrEnum):
    EMPLOYEE = "employee"
    MANAGER = "manager"
    FINANCE = "finance"
    AUDITOR = "auditor"
    AGENT = "agent"  # AI-Agent service principal


class Scope(StrEnum):
    SELF = "self"  # sees only their own claims
    ALL = "all"  # sees across the org


# SCOPING §3: role-based, no team/department hierarchy. Scope is derived from role,
# NOT from department. (Department stays profile metadata unless requirements says
# otherwise — see the open question in ADR-001.)
_ROLE_SCOPE: dict[Role, Scope] = {
    Role.EMPLOYEE: Scope.SELF,
    Role.MANAGER: Scope.ALL,
    Role.FINANCE: Scope.ALL,
    Role.AUDITOR: Scope.ALL,
    Role.AGENT: Scope.ALL,
}


def scope_for(role: Role) -> Scope:
    return _ROLE_SCOPE[role]


class Principal(BaseModel):
    subject_id: str  # users.id now → Entra `oid` later
    email: str
    role: Role
    department: str | None = None
    scope: Scope

    @classmethod
    def from_claims(cls, claims: dict) -> "Principal":
        """Build from a verified JWT payload. Claim shape mirrors Entra's
        (`sub`, `email`, `roles`, custom `department`) so this is issuer-agnostic."""
        roles = claims.get("roles") or []
        role = Role(roles[0]) if roles else Role(claims["role"])
        return cls(
            subject_id=claims["sub"],
            email=claims["email"],
            role=role,
            department=claims.get("department"),
            scope=scope_for(role),
        )

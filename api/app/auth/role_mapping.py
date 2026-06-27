"""Configurable IdP-claim → application-role mapping (SCOPING §3, ADR-001).

Entra (and other OIDC IdPs) express authorization as **app-roles** or **group object-ids**
in the token. This module turns those issuer-specific values into our `Role` enum using a
config-driven map — never hardcoded — so onboarding a new IdP or renaming a group is a config
change, not a code change.

Design notes:
  • `Super Admin` (and common variants) map to `Role.ADMIN` by default — we don't yet have a
    distinct super-admin tier, so it collapses to admin (revisit if that changes).
  • Matching is case-insensitive and accepts either the human app-role name or a group GUID.
  • This is a *fallback* for role resolution: for an existing DB user the DB role wins
    (DB-by-email is the source of truth). It's authoritative only for brand-new JIT users.
"""

from __future__ import annotations

import json
import logging

from app.principal import Role

logger = logging.getLogger("app.auth.role_mapping")

# Built-in aliases so a sensibly-named IdP role/group "just works" without config.
_DEFAULT_ALIASES: dict[str, Role] = {
    "employee": Role.EMPLOYEE,
    "manager": Role.MANAGER,
    "finance": Role.FINANCE,
    "admin": Role.ADMIN,
    "administrator": Role.ADMIN,
    # No distinct super-admin tier today → collapse to admin (decision: Super Admin → Admin).
    "super admin": Role.ADMIN,
    "super_admin": Role.ADMIN,
    "superadmin": Role.ADMIN,
}


class RoleMapper:
    """Resolve a single application `Role` from a token's app-roles / group claims."""

    def __init__(self, role_map_json: str = "{}") -> None:
        self._map: dict[str, Role] = dict(_DEFAULT_ALIASES)
        for key, value in _parse_map(role_map_json).items():
            role = _coerce_role(value)
            if role is not None:
                self._map[key.strip().lower()] = role

    def map(self, *claim_values: str) -> Role | None:
        """Return the highest-privilege role any of the claim values maps to, or None.

        `claim_values` are the flattened app-role names and group ids from the token.
        When a user carries several mapped roles we pick the most privileged so access
        is never silently downgraded by claim ordering.
        """
        hits = [self._map[v.strip().lower()] for v in claim_values if v and v.strip().lower() in self._map]
        if not hits:
            return None
        return max(hits, key=_privilege)


# Privilege ordering (higher = more powerful) so multi-role users resolve deterministically.
_PRIVILEGE: dict[Role, int] = {
    Role.EMPLOYEE: 0,
    Role.MANAGER: 1,
    Role.FINANCE: 2,
    Role.ADMIN: 3,
    Role.AGENT: 0,
}


def _privilege(role: Role) -> int:
    return _PRIVILEGE.get(role, 0)


def _parse_map(raw: str) -> dict:
    try:
        parsed = json.loads(raw or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        logger.warning("OIDC_ROLE_MAP is not valid JSON; ignoring it.")
        return {}


def _coerce_role(value: object) -> Role | None:
    if isinstance(value, str):
        v = value.strip().lower()
        if v in Role._value2member_map_:
            return Role(v)
        if v in _DEFAULT_ALIASES:
            return _DEFAULT_ALIASES[v]
    return None

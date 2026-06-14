"""The permission matrix (SCOPING §3.2) as code, plus enforcement helpers (§3.3).

This is the single source of truth for "who may do what". Routes call `require_capability`;
data-query scoping and segregation-of-duties are separate, sharper checks layered on top
(see `scope.py` and the services) because a capability alone never implies cross-agency or
self-approval rights.
"""

from __future__ import annotations

from enum import StrEnum

from fastapi import HTTPException, status

from app.principal import Principal, Role


class Capability(StrEnum):
    SUBMIT_OWN_SHEET = "submit_own_sheet"
    VIEW_OWN_SHEETS = "view_own_sheets"
    VIEW_SHEETS = "view_sheets"  # others' sheets (scope decides which)
    MANAGER_ACTION_LINE_ITEM = "manager_action_line_item"
    FINANCE_DECISION = "finance_decision"
    OVERRIDE_LLM_DECISION = "override_llm_decision"
    UPDATE_AGENCY_POLICY_DOC = "update_agency_policy_doc"
    MANAGE_AGENCY = "manage_agency"  # create / onboard / delete agency
    MANAGE_USERS = "manage_users"
    VIEW_AUDIT_LOG = "view_audit_log"
    RAG_QUERY = "rag_query"


# Direct transcription of SCOPING §3.2. Agency-scoping/SoD are enforced separately.
_MATRIX: dict[Capability, set[Role]] = {
    Capability.SUBMIT_OWN_SHEET: {Role.EMPLOYEE, Role.MANAGER, Role.FINANCE, Role.ADMIN},
    Capability.VIEW_OWN_SHEETS: {Role.EMPLOYEE, Role.MANAGER, Role.FINANCE, Role.ADMIN},
    Capability.VIEW_SHEETS: {Role.MANAGER, Role.FINANCE, Role.ADMIN},
    Capability.MANAGER_ACTION_LINE_ITEM: {Role.MANAGER},
    Capability.FINANCE_DECISION: {Role.FINANCE, Role.ADMIN, Role.AGENT},
    Capability.OVERRIDE_LLM_DECISION: {Role.FINANCE, Role.ADMIN},
    Capability.UPDATE_AGENCY_POLICY_DOC: {Role.FINANCE, Role.ADMIN},
    Capability.MANAGE_AGENCY: {Role.ADMIN},
    Capability.MANAGE_USERS: {Role.ADMIN},
    Capability.VIEW_AUDIT_LOG: {Role.FINANCE, Role.ADMIN},
    Capability.RAG_QUERY: {Role.EMPLOYEE, Role.MANAGER, Role.FINANCE, Role.ADMIN, Role.AGENT},
}


def can(principal: Principal, capability: Capability) -> bool:
    return principal.role in _MATRIX.get(capability, set())


def require_capability(principal: Principal, capability: Capability) -> None:
    """Raise 403 if the principal's role lacks the capability. Agency-scope and SoD are
    checked closer to the data (they need the target resource, not just the role)."""
    if not can(principal, capability):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=f"Role '{principal.role}' lacks capability '{capability}'",
        )

"""Expense-sheet state machine (SCOPING §5.1, §6). Centralizes legal transitions so no
router can move a sheet into an illegal state. Raises on invalid transitions.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from expense_core.schemas.enums import SheetStatus as S

# Allowed transitions. Source → set of legal destinations (SCOPING §5.1 diagram).
_ALLOWED: dict[S, set[S]] = {
    S.DRAFT: {S.SUBMITTED, S.WITHDRAWN},  # withdraw a draft before submission (soft)
    S.SUBMITTED: {S.IN_MANAGER_REVIEW},
    S.IN_MANAGER_REVIEW: {S.RETURNED_TO_EMPLOYEE, S.IN_FINANCE_REVIEW},
    S.RETURNED_TO_EMPLOYEE: {S.SUBMITTED},  # resubmit (new version)
    S.IN_FINANCE_REVIEW: {S.FINANCE_APPROVED, S.FINANCE_REJECTED, S.FINANCE_MANUAL_REVIEW},
    S.FINANCE_REJECTED: {S.SUBMITTED},  # resubmit
    S.FINANCE_MANUAL_REVIEW: {S.APPROVED, S.REJECTED},
    S.FINANCE_APPROVED: {S.PAID},
    S.APPROVED: {S.PAID},
    S.REJECTED: {S.SUBMITTED},  # resubmit after human reject
    S.PAID: set(),
    S.WITHDRAWN: set(),  # terminal
}


def can_transition(src: S, dst: S) -> bool:
    return dst in _ALLOWED.get(src, set())


def assert_transition(src: S, dst: S) -> None:
    if not can_transition(src, dst):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Illegal sheet transition {src} → {dst}",
        )


# Terminal-ish states an employee may resubmit from (restarts fresh; SCOPING §5.1).
RESUBMITTABLE = {S.RETURNED_TO_EMPLOYEE, S.FINANCE_REJECTED, S.REJECTED}

"""Agency-scope + segregation-of-duties enforcement (SCOPING §3.3, §6.2, §6.3).

These need the *target* resource (a sheet, a line item), not just the caller's role —
so they live apart from the capability matrix. Server-side only; never trust client scope.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from app.models.expense_sheet import ExpenseSheet
from app.models.line_item import LineItem
from app.principal import Principal, Role, Scope


def assert_can_view_sheet(principal: Principal, sheet: ExpenseSheet) -> None:
    """Employee → own only; Manager → own agency; Finance/Admin → all (SCOPING §3.2)."""
    if principal.scope is Scope.ALL:
        return
    if principal.scope is Scope.SELF:
        if sheet.employee_id != principal.subject_id:
            raise _forbidden("not your sheet")
        return
    if principal.scope is Scope.AGENCY:
        if sheet.agency_id != principal.agency_id:
            raise _forbidden("sheet is outside your agency")
        return
    raise _forbidden("no visibility scope")


def assert_manager_in_agency(principal: Principal, sheet: ExpenseSheet) -> None:
    """A manager may only action sheets in their own agency (SCOPING §19.1)."""
    if principal.role is not Role.MANAGER:
        raise _forbidden("manager role required")
    if sheet.agency_id != principal.agency_id:
        raise _forbidden("cross-agency manager action denied")


def assert_no_self_approval(principal: Principal, line_item: LineItem) -> None:
    """A manager cannot approve their own line items (SoD, SCOPING §3.3, §6.2)."""
    if line_item.employee_id == principal.subject_id:
        raise _forbidden("segregation of duties: cannot action your own line item")


def assert_finance_not_own_sheet(principal: Principal, sheet: ExpenseSheet) -> None:
    """Finance cannot override a decision on their own sheet (SoD, SCOPING §3.3)."""
    if sheet.employee_id == principal.subject_id:
        raise _forbidden("segregation of duties: cannot decide on your own sheet")


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, detail=detail)

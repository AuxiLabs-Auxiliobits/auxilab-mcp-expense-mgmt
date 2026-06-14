"""Expense-sheet workflow orchestration (SCOPING §5, §6). The three lines of defense:
intake (Line 1), manager per-line-item approval (Line 2), and hand-off to the LLM finance
queue (Line 3, executed by the workers package). All transitions go through the state
machine and are audited.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.base import utcnow
from app.models.expense_sheet import ExpenseSheet
from app.models.line_item import LineItem
from app.principal import Principal
from app.rbac import scope as rbac_scope
from app.services import audit_service, intake_service
from app.services.state_machine import RESUBMITTABLE, assert_transition
from expense_core.policy import BaselinePolicy
from expense_core.schemas.enums import LineItemStatus, SheetStatus
from fastapi import HTTPException, status


def get_sheet_or_404(session: Session, sheet_id: str) -> ExpenseSheet:
    sheet = session.get(ExpenseSheet, sheet_id)
    if sheet is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="sheet not found")
    return sheet


def _line_items(session: Session, sheet_id: str) -> list[LineItem]:
    return list(session.exec(select(LineItem).where(LineItem.sheet_id == sheet_id)).all())


# --------------------------------------------------------------------------- #
# Submit / resubmit
# --------------------------------------------------------------------------- #
def submit_sheet(
    session: Session, sheet: ExpenseSheet, actor: Principal, policy: BaselinePolicy
) -> ExpenseSheet:
    """DRAFT/resubmittable → SUBMITTED → IN_MANAGER_REVIEW, running intake on every item.
    A hard intake failure returns the sheet to the employee immediately (SCOPING §6.1)."""
    items = _line_items(session, sheet.id)
    if not items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="cannot submit an empty sheet")

    is_resubmit = sheet.status in RESUBMITTABLE
    if is_resubmit:
        _reset_for_resubmission(sheet, items)

    before = sheet.status
    assert_transition(sheet.status, SheetStatus.SUBMITTED)
    sheet.status = SheetStatus.SUBMITTED
    sheet.submitted_at = utcnow()
    sheet.policy_version_used = "baseline-v1"  # pinned at submission (SCOPING §7)

    # Line 1 — intake on each item.
    intake_failed = False
    for item in items:
        check = intake_service.run_intake(session, item, policy)
        if not intake_service.intake_passes(check):
            intake_failed = True

    if intake_failed:
        sheet.status = SheetStatus.RETURNED_TO_EMPLOYEE
        audit_service.record(
            session, actor=actor, action="INTAKE_RETURNED", entity=f"expense_sheet:{sheet.id}",
            before={"status": before}, after={"status": sheet.status},
        )
    else:
        assert_transition(SheetStatus.SUBMITTED, SheetStatus.IN_MANAGER_REVIEW)
        sheet.status = SheetStatus.IN_MANAGER_REVIEW
        audit_service.record(
            session, actor=actor, action="SUBMITTED", entity=f"expense_sheet:{sheet.id}",
            before={"status": before}, after={"status": sheet.status, "version": sheet.version},
        )

    sheet.updated_at = utcnow()
    session.add(sheet)
    session.commit()
    session.refresh(sheet)
    return sheet


def _reset_for_resubmission(sheet: ExpenseSheet, items: list[LineItem]) -> None:
    """Resubmission keeps the sheet ID, bumps version, and restarts fresh — all prior
    manager/finance verdicts are reset (SCOPING §5.1)."""
    sheet.version += 1
    sheet.finance_decision = None
    sheet.finance_decided_by = None
    for item in items:
        item.manager_status = LineItemStatus.PENDING_MANAGER
        item.manager_actor_id = None
        item.manager_reason = None
        item.policy_status = None
        item.policy_clause_ref = None


# --------------------------------------------------------------------------- #
# Line 2 — Manager per-line-item action
# --------------------------------------------------------------------------- #
def manager_action(
    session: Session,
    sheet: ExpenseSheet,
    item: LineItem,
    actor: Principal,
    new_status: LineItemStatus,
    reason: str | None,
) -> ExpenseSheet:
    """Approve / reject / request-info one line item. Enforces agency scope + SoD, then
    advances the sheet if all items are approved (SCOPING §6.2)."""
    rbac_scope.assert_manager_in_agency(actor, sheet)
    rbac_scope.assert_no_self_approval(actor, item)

    if item.sheet_id != sheet.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="line item not on this sheet")
    if sheet.status is not SheetStatus.IN_MANAGER_REVIEW:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="sheet not in manager review")

    item.manager_status = new_status
    item.manager_actor_id = actor.subject_id
    item.manager_reason = reason
    session.add(item)
    audit_service.record(
        session, actor=actor, action=f"MANAGER_{new_status}",
        entity=f"line_item:{item.id}", after={"reason": reason},
    )

    _maybe_advance_after_manager(session, sheet, actor)
    session.commit()
    session.refresh(sheet)
    return sheet


def _maybe_advance_after_manager(
    session: Session, sheet: ExpenseSheet, actor: Principal
) -> None:
    items = _line_items(session, sheet.id)
    statuses = {i.manager_status for i in items}

    if {LineItemStatus.MANAGER_REJECTED, LineItemStatus.INFO_REQUESTED} & statuses:
        # Any rejection / info-request returns the whole sheet (SCOPING §6.2).
        assert_transition(sheet.status, SheetStatus.RETURNED_TO_EMPLOYEE)
        sheet.status = SheetStatus.RETURNED_TO_EMPLOYEE
        audit_service.record(
            session, actor=actor, action="RETURNED_TO_EMPLOYEE",
            entity=f"expense_sheet:{sheet.id}",
        )
    elif statuses == {LineItemStatus.MANAGER_APPROVED}:
        # All approved → advance to the finance (LLM) queue.
        assert_transition(sheet.status, SheetStatus.IN_FINANCE_REVIEW)
        sheet.status = SheetStatus.IN_FINANCE_REVIEW
        audit_service.record(
            session, actor=actor, action="ADVANCED_TO_FINANCE",
            entity=f"expense_sheet:{sheet.id}",
        )
        # NOTE: enqueue to Service Bus finance queue here (workers package consumes it).
    sheet.updated_at = utcnow()
    session.add(sheet)

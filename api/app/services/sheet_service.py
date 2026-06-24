"""Expense-sheet workflow orchestration (SCOPING §5, §6). The three lines of defense:
intake (Line 1), manager per-line-item approval (Line 2), and hand-off to the LLM finance
queue (Line 3, executed by the workers package). All transitions go through the state
machine and are audited.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models.attachment import Attachment
from app.models.base import utcnow
from app.models.expense_sheet import ExpenseSheet
from app.models.line_item import LineItem
from app.principal import Principal, Role
from app.rbac import scope as rbac_scope
from app.schemas.dto import LineItemCreate, LineItemUpdate, SheetCreate, SheetUpdate
from app.services import audit_service, intake_service, notification_service
from app.services.state_machine import RESUBMITTABLE, assert_transition
from app.storage import upload_receipt_blob
from app.value_sets import MAX_RECEIPT_BYTES, receipt_extension
from expense_core.schemas.enums import LineItemStatus, SheetStatus

from expense_core.policy import BaselinePolicy  # isort: skip

# A sheet is editable by its owner while drafting or after being sent back.
_EDITABLE = {SheetStatus.DRAFT} | RESUBMITTABLE


def get_sheet_or_404(session: Session, sheet_id: str) -> ExpenseSheet:
    sheet = session.get(ExpenseSheet, sheet_id)
    if sheet is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="sheet not found")
    return sheet


def _line_items(session: Session, sheet_id: str) -> list[LineItem]:
    return list(session.exec(select(LineItem).where(LineItem.sheet_id == sheet_id)).all())


def _attachment_count(session: Session, line_item_id: str) -> int:
    return len(
        session.exec(select(Attachment).where(Attachment.line_item_id == line_item_id)).all()
    )


# --------------------------------------------------------------------------- #
# Draft editing (owner-only, DRAFT/returned states)
# --------------------------------------------------------------------------- #
def _assert_owner(actor: Principal, sheet: ExpenseSheet) -> None:
    if sheet.employee_id != actor.subject_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="not your sheet")


def _assert_editable(sheet: ExpenseSheet) -> None:
    if sheet.status not in _EDITABLE:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"sheet is not editable in status {sheet.status} (edit while DRAFT)",
        )


def _build_line_item(sheet: ExpenseSheet, data: LineItemCreate) -> LineItem:
    return LineItem(
        sheet_id=sheet.id, employee_id=sheet.employee_id,
        category=data.category, expense_type_other=data.expense_type_other,
        amount=data.amount, currency=data.currency, merchant=data.merchant,
        description=data.description, expense_date=data.expense_date,
        receipt_datetime=data.receipt_datetime, receipt_total=data.receipt_total,
        tax=data.tax, has_receipt=False,
    )


def create_draft(session: Session, actor: Principal, data: SheetCreate) -> ExpenseSheet:
    """Create a DRAFT sheet (title + period), optionally seeded with line items. A receipt
    is still required on each item before submission (change req)."""
    if actor.agency_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="user has no agency assigned")

    sheet = ExpenseSheet(
        employee_id=actor.subject_id, agency_id=actor.agency_id,
        title=data.title, period=data.period,
    )
    session.add(sheet)
    session.flush()  # assign sheet.id
    for li in data.line_items:
        session.add(_build_line_item(sheet, li))
    audit_service.record(
        session, actor=actor, action="SHEET_DRAFTED", entity=f"expense_sheet:{sheet.id}",
        after={"title": data.title, "period": data.period},
    )
    session.commit()
    session.refresh(sheet)
    return sheet


def update_sheet(
    session: Session, sheet: ExpenseSheet, actor: Principal, data: SheetUpdate
) -> ExpenseSheet:
    _assert_owner(actor, sheet)
    _assert_editable(sheet)
    if data.title is not None:
        sheet.title = data.title
    if data.period is not None:
        sheet.period = data.period
    sheet.updated_at = utcnow()
    session.add(sheet)
    session.commit()
    session.refresh(sheet)
    return sheet


def delete_draft(session: Session, sheet: ExpenseSheet, actor: Principal) -> None:
    """Withdraw/discard a draft. Only allowed while DRAFT (never mid-workflow)."""
    _assert_owner(actor, sheet)
    if sheet.status is not SheetStatus.DRAFT:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="only DRAFT sheets can be withdrawn"
        )
    for item in _line_items(session, sheet.id):
        for att in session.exec(
            select(Attachment).where(Attachment.line_item_id == item.id)
        ).all():
            session.delete(att)
        session.delete(item)
    audit_service.record(
        session, actor=actor, action="SHEET_DISCARDED", entity=f"expense_sheet:{sheet.id}",
    )
    session.delete(sheet)
    session.commit()


def withdraw_sheet(session: Session, sheet: ExpenseSheet, actor: Principal) -> ExpenseSheet:
    """Soft-withdraw a DRAFT (SCOPING §5.1). Unlike delete_draft this preserves the sheet and
    its line items for the audit trail, moving it to the terminal WITHDRAWN state. Owner-only,
    DRAFT-only."""
    _assert_owner(actor, sheet)
    if sheet.status is not SheetStatus.DRAFT:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="only DRAFT sheets can be withdrawn"
        )
    before = sheet.status
    assert_transition(sheet.status, SheetStatus.WITHDRAWN)
    sheet.status = SheetStatus.WITHDRAWN
    sheet.updated_at = utcnow()
    session.add(sheet)
    audit_service.record(
        session, actor=actor, action="SHEET_WITHDRAWN", entity=f"expense_sheet:{sheet.id}",
        before={"status": before}, after={"status": sheet.status},
    )
    session.commit()
    session.refresh(sheet)
    return sheet


def add_line_item(
    session: Session, sheet: ExpenseSheet, actor: Principal, data: LineItemCreate
) -> LineItem:
    _assert_owner(actor, sheet)
    _assert_editable(sheet)
    item = _build_line_item(sheet, data)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def get_line_item_or_404(session: Session, sheet: ExpenseSheet, line_item_id: str) -> LineItem:
    item = session.get(LineItem, line_item_id)
    if item is None or item.sheet_id != sheet.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="line item not found on this sheet")
    return item


def update_line_item(
    session: Session, sheet: ExpenseSheet, item: LineItem, actor: Principal, data: LineItemUpdate
) -> LineItem:
    _assert_owner(actor, sheet)
    _assert_editable(sheet)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def delete_line_item(
    session: Session, sheet: ExpenseSheet, item: LineItem, actor: Principal
) -> None:
    _assert_owner(actor, sheet)
    _assert_editable(sheet)
    for att in session.exec(select(Attachment).where(Attachment.line_item_id == item.id)).all():
        session.delete(att)
    session.delete(item)
    session.commit()


def attach_receipt(
    session: Session, sheet: ExpenseSheet, item: LineItem, actor: Principal,
    *, filename: str, data: bytes, file_type: str,
) -> Attachment:
    """Upload a receipt to Blob under receipts/{employee_id}/ and attach it to the line item.
    Sets has_receipt=True (a receipt is mandatory per line item)."""
    _assert_owner(actor, sheet)
    _assert_editable(sheet)
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="empty file")
    if len(data) > MAX_RECEIPT_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file exceeds 25 MB")
    try:
        receipt_extension(filename)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e

    att = Attachment(
        line_item_id=item.id, blob_uri="", filename=filename, file_type=file_type, size=len(data)
    )
    session.add(att)
    session.flush()  # assign att.id for a collision-safe blob name
    att.blob_uri = upload_receipt_blob(sheet.employee_id, f"{att.id}-{filename}", data)
    item.has_receipt = True
    session.add_all([att, item])
    audit_service.record(
        session, actor=actor, action="RECEIPT_ATTACHED", entity=f"line_item:{item.id}",
        after={"attachment": att.id, "file_type": file_type, "size": len(data)},
    )
    session.commit()
    session.refresh(att)
    return att


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

    # Receipt is mandatory on every line item (change req) — flag before submission.
    missing = [i.id for i in items if _attachment_count(session, i.id) == 0]
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "every line item must have a receipt attached before submission",
                "line_items_without_receipt": missing,
            },
        )

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

    title = sheet.title or "Expense sheet"
    if intake_failed:
        sheet.status = SheetStatus.RETURNED_TO_EMPLOYEE
        audit_service.record(
            session, actor=actor, action="INTAKE_RETURNED", entity=f"expense_sheet:{sheet.id}",
            before={"status": before}, after={"status": sheet.status},
        )
        notification_service.notify(
            session, recipient_id=sheet.employee_id, kind="warning", icon="error",
            title="Sheet returned at intake",
            body=f'"{title}" was returned automatically — fix the flagged items and resubmit.',
            href=f"/employee/sheets/{sheet.id}", entity=f"expense_sheet:{sheet.id}",
            agency_id=sheet.agency_id,
        )
    else:
        assert_transition(SheetStatus.SUBMITTED, SheetStatus.IN_MANAGER_REVIEW)
        sheet.status = SheetStatus.IN_MANAGER_REVIEW
        audit_service.record(
            session, actor=actor, action="SUBMITTED", entity=f"expense_sheet:{sheet.id}",
            before={"status": before}, after={"status": sheet.status, "version": sheet.version},
        )
        # Alert every manager in the sheet's agency that there's work in their queue.
        notification_service.notify_role_in_agency(
            session, role=Role.MANAGER, agency_id=sheet.agency_id, kind="info", icon="assignment",
            title="New sheet to review",
            body=f'"{title}" is awaiting your review.',
            href="/manager", entity=f"expense_sheet:{sheet.id}",
            exclude_user_id=actor.subject_id,
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


def manager_approve_sheet(
    session: Session, sheet: ExpenseSheet, actor: Principal
) -> ExpenseSheet:
    """Approve a whole sheet in one action (SCOPING §6.2, §8 bulk-approve): mark every
    not-yet-rejected line item MANAGER_APPROVED, then advance to finance review. Enforces
    agency scope + segregation-of-duties (a manager cannot approve their own line items)."""
    rbac_scope.assert_manager_in_agency(actor, sheet)
    if sheet.status is not SheetStatus.IN_MANAGER_REVIEW:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="sheet not in manager review")

    items = _line_items(session, sheet.id)
    if not items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="sheet has no line items")
    for item in items:
        rbac_scope.assert_no_self_approval(actor, item)  # SoD across the whole sheet

    approved = 0
    for item in items:
        # Preserve any explicit rejection/info-request the manager already made; approve the rest.
        if item.manager_status in (
            LineItemStatus.MANAGER_REJECTED,
            LineItemStatus.INFO_REQUESTED,
        ):
            continue
        item.manager_status = LineItemStatus.MANAGER_APPROVED
        item.manager_actor_id = actor.subject_id
        session.add(item)
        approved += 1

    audit_service.record(
        session, actor=actor, action="MANAGER_SHEET_APPROVED",
        entity=f"expense_sheet:{sheet.id}", after={"items_approved": approved},
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

    title = sheet.title or "Expense sheet"
    if {LineItemStatus.MANAGER_REJECTED, LineItemStatus.INFO_REQUESTED} & statuses:
        # Any rejection / info-request returns the whole sheet (SCOPING §6.2).
        assert_transition(sheet.status, SheetStatus.RETURNED_TO_EMPLOYEE)
        sheet.status = SheetStatus.RETURNED_TO_EMPLOYEE
        audit_service.record(
            session, actor=actor, action="RETURNED_TO_EMPLOYEE",
            entity=f"expense_sheet:{sheet.id}",
        )
        notification_service.notify(
            session, recipient_id=sheet.employee_id, kind="warning", icon="undo",
            title="Sheet returned by your manager",
            body=f'"{title}" needs changes — review the manager\'s notes and resubmit.',
            href=f"/employee/sheets/{sheet.id}", entity=f"expense_sheet:{sheet.id}",
            agency_id=sheet.agency_id,
        )
    elif statuses == {LineItemStatus.MANAGER_APPROVED}:
        # All approved → advance to the finance (LLM) queue.
        assert_transition(sheet.status, SheetStatus.IN_FINANCE_REVIEW)
        sheet.status = SheetStatus.IN_FINANCE_REVIEW
        audit_service.record(
            session, actor=actor, action="ADVANCED_TO_FINANCE",
            entity=f"expense_sheet:{sheet.id}",
        )
        notification_service.notify(
            session, recipient_id=sheet.employee_id, kind="success", icon="forward",
            title="Sheet approved by your manager",
            body=f'"{title}" passed manager review and is now in finance review.',
            href=f"/employee/sheets/{sheet.id}", entity=f"expense_sheet:{sheet.id}",
            agency_id=sheet.agency_id,
        )
        # NOTE: enqueue to Service Bus finance queue here (workers package consumes it).
    sheet.updated_at = utcnow()
    session.add(sheet)

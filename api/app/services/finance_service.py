"""Line 3 — Finance decisions (SCOPING §6.3, §9.2). Two entry points:

  • apply_llm_decision  — the LLM approver worker reports a sheet-level verdict; we record
    it with model+policy version + cited clauses and move the sheet accordingly.
  • finance_human_decision / override — a Finance user decides a routed sheet or overrides
    an LLM verdict (with a logged reason). SoD: not on their own sheet.
"""

from __future__ import annotations

import json

from fastapi import HTTPException, status
from sqlmodel import Session

from app.models.base import utcnow
from app.models.decision import Decision
from app.models.expense_sheet import ExpenseSheet
from app.principal import Principal, Role
from app.rbac import scope as rbac_scope
from app.services import audit_service, notification_service
from app.services.state_machine import assert_transition
from expense_core.schemas.enums import FinanceDecision, SheetStatus


def _notify_employee_outcome(session: Session, sheet: ExpenseSheet, approved: bool | None) -> None:
    """Tell the submitter the finance outcome. `approved=None` → routed for manual review."""
    title = sheet.title or "Expense sheet"
    if approved is None:
        kind, head, body = (
            "info",
            "Sent for finance review",
            f"“{title}” was routed to a Finance reviewer for a closer look.",
        )
    elif approved:
        kind, head, body = ("success", "Reimbursement approved", f"“{title}” was approved by Finance.")
    else:
        kind, head, body = ("error", "Sheet rejected", f"“{title}” was rejected by Finance.")
    notification_service.notify(
        session, recipient_id=sheet.employee_id, kind=kind, title=head, body=body,
        href=f"/employee/sheets/{sheet.id}",
    )


def apply_llm_decision(
    session: Session,
    sheet: ExpenseSheet,
    *,
    decision: FinanceDecision,
    model_version: str,
    policy_version: str,
    cited_clauses: list[str],
    confidence: float,
) -> ExpenseSheet:
    """Record the LLM finance approver's sheet-level decision (SCOPING §6.3)."""
    if sheet.status is not SheetStatus.IN_FINANCE_REVIEW:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="sheet not awaiting finance review")

    target = {
        FinanceDecision.APPROVED: SheetStatus.FINANCE_APPROVED,
        FinanceDecision.REJECTED_WITH_COMMENTS: SheetStatus.FINANCE_REJECTED,
        FinanceDecision.ROUTED_TO_HUMAN: SheetStatus.FINANCE_MANUAL_REVIEW,
    }[decision]

    assert_transition(sheet.status, target)
    sheet.status = target
    sheet.finance_decision = decision
    sheet.updated_at = utcnow()
    session.add(sheet)

    session.add(
        Decision(
            sheet_id=sheet.id,
            actor_id="llm-approver",
            actor_role=Role.AGENT,
            action=str(decision),
            llm_model_version=model_version,
            policy_version=policy_version,
            cited_clauses=json.dumps(cited_clauses),
            reason=f"confidence={confidence}",
        )
    )
    audit_service.record(
        session, action=f"LLM_{decision}", entity=f"expense_sheet:{sheet.id}",
        agency_id=sheet.agency_id,
        after={"model_version": model_version, "policy_version": policy_version,
               "cited_clauses": cited_clauses, "confidence": confidence},
    )
    _notify_employee_outcome(
        session, sheet,
        approved=True if decision is FinanceDecision.APPROVED
        else False if decision is FinanceDecision.REJECTED_WITH_COMMENTS
        else None,
    )
    session.commit()
    session.refresh(sheet)
    return sheet


def finance_human_decision(
    session: Session, sheet: ExpenseSheet, actor: Principal, *, approve: bool, reason: str
) -> ExpenseSheet:
    """Finance resolves a routed (manual-review) sheet (SCOPING §6.3)."""
    rbac_scope.assert_finance_not_own_sheet(actor, sheet)
    if sheet.status is not SheetStatus.FINANCE_MANUAL_REVIEW:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="sheet not in manual review")

    target = SheetStatus.APPROVED if approve else SheetStatus.REJECTED
    assert_transition(sheet.status, target)
    sheet.status = target
    sheet.finance_decided_by = actor.subject_id
    sheet.updated_at = utcnow()
    session.add(sheet)
    session.add(
        Decision(sheet_id=sheet.id, actor_id=actor.subject_id, actor_role=actor.role,
                 action=str(target), reason=reason)
    )
    audit_service.record(
        session, actor=actor, action=f"FINANCE_HUMAN_{target}",
        entity=f"expense_sheet:{sheet.id}", after={"reason": reason},
    )
    _notify_employee_outcome(session, sheet, approved=approve)
    session.commit()
    session.refresh(sheet)
    return sheet


def override_decision(
    session: Session, sheet: ExpenseSheet, actor: Principal, *, approve: bool, reason: str
) -> ExpenseSheet:
    """Finance/Admin overrides an LLM finance decision with a logged reason (SCOPING §3.2)."""
    rbac_scope.assert_finance_not_own_sheet(actor, sheet)
    if sheet.status not in (SheetStatus.FINANCE_APPROVED, SheetStatus.FINANCE_REJECTED):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="no LLM decision to override")

    before = sheet.status
    sheet.status = SheetStatus.APPROVED if approve else SheetStatus.REJECTED
    sheet.finance_decided_by = actor.subject_id
    sheet.updated_at = utcnow()
    session.add(sheet)
    session.add(
        Decision(sheet_id=sheet.id, actor_id=actor.subject_id, actor_role=actor.role,
                 action="OVERRIDE", reason=reason)
    )
    audit_service.record(
        session, actor=actor, action="OVERRIDE_LLM_DECISION",
        entity=f"expense_sheet:{sheet.id}",
        before={"status": before}, after={"status": sheet.status, "reason": reason},
    )
    _notify_employee_outcome(session, sheet, approved=approve)
    session.commit()
    session.refresh(sheet)
    return sheet

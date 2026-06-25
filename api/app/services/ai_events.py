"""Event-driven agent framework.

Business events (sheet submitted / returned / manager-approved / finance-decided / receipt
uploaded) trigger AI workflows: (re)generate the advisory recommendation and fan out **smart,
actionable notifications** to the right audience. Handlers run **after** the business transaction
commits, in their own session, and are fully defensive — an AI failure can never break or roll
back a business operation. The AI only advises and notifies; it never changes sheet state.
"""

from __future__ import annotations

import logging
from enum import Enum

from sqlmodel import Session

from app.db import engine
from app.models.expense_sheet import ExpenseSheet
from app.principal import Role
from app.services import ai_recommendations as ai
from app.services import notification_service

logger = logging.getLogger("app.ai_events")


class EventType(str, Enum):
    SHEET_SUBMITTED = "sheet.submitted"
    SHEET_RETURNED = "sheet.returned"
    MANAGER_APPROVED = "manager.approved"
    FINANCE_DECIDED = "finance.decided"
    RECEIPT_UPLOADED = "receipt.uploaded"


def emit(event: EventType, sheet_id: str) -> None:
    """Schedule-friendly entry point (call via BackgroundTasks). Never raises."""
    try:
        with Session(engine) as session:
            sheet = session.get(ExpenseSheet, sheet_id)
            if sheet is None:
                return
            rec = ai.generate(session, sheet)  # refresh the advisory analysis on every event
            _dispatch(session, event, sheet, rec)
            session.commit()
    except Exception:  # AI must never break a business flow
        logger.exception("AI event handler failed for %s on sheet %s", event, sheet_id)


def _dispatch(session: Session, event: EventType, sheet: ExpenseSheet, rec) -> None:
    title = sheet.title or "Expense sheet"
    entity = f"expense_sheet:{sheet.id}"

    if event is EventType.SHEET_SUBMITTED and sheet.agency_id:
        if rec.risk_band == "high":
            kind, icon, head = "warning", "priority_high", f"High-priority approval: {title}"
        elif rec.duplicate_band in ("medium", "high"):
            kind, icon, head = "warning", "content_copy", f"Possible duplicate to review: {title}"
        elif not rec.policy_compliant:
            kind, icon, head = "warning", "gavel", f"Policy issue to review: {title}"
        else:
            kind, icon, head = "info", "auto_awesome", f"New sheet to review: {title}"
        notification_service.notify_role_in_agency(
            session, role=Role.MANAGER, agency_id=sheet.agency_id, kind=kind, icon=icon,
            title=head, body=rec.summary, href="/manager", entity=entity,
        )

    elif event is EventType.MANAGER_APPROVED and sheet.agency_id:
        if rec.risk_band == "high" or rec.duplicate_band in ("medium", "high") or not rec.policy_compliant:
            notification_service.notify_role_in_agency(
                session, role=Role.FINANCE, agency_id=sheet.agency_id, kind="warning",
                icon="account_balance", title=f"High-risk reimbursement — review: {title}",
                body=rec.summary, href="/finance", entity=entity,
            )

    elif event is EventType.RECEIPT_UPLOADED:
        receipt_gaps = [m for m in (rec.missing_info or []) if "receipt" in m.lower()]
        if receipt_gaps and sheet.employee_id:
            notification_service.notify(
                session, recipient_id=sheet.employee_id, kind="info", icon="receipt_long",
                title="Receipts still needed", body=receipt_gaps[0],
                href="/employee", entity=entity, agency_id=sheet.agency_id,
            )

    elif event is EventType.SHEET_RETURNED and sheet.employee_id and rec.missing_info:
        notification_service.notify(
            session, recipient_id=sheet.employee_id, kind="info", icon="auto_awesome",
            title="AI tips to fix your returned sheet", body="; ".join(rec.missing_info[:3]),
            href="/employee", entity=entity, agency_id=sheet.agency_id,
        )
    # FINANCE_DECIDED: just refreshes the recommendation (the app already notifies the employee).

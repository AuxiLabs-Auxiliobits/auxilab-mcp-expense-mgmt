"""Line 1 — Intake gate (SCOPING §6.1). Runs the deterministic engine tools over each
line item at submission, persists a ClaimCheck, and reports whether the sheet may proceed.

The LLM-using tools (classifier) default to the engine's offline provider here; wiring a
real Foundry gateway is a one-line injection when the worker/API needs it.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.claim_check import ClaimCheck
from app.models.line_item import LineItem
from expense_core.policy import BaselinePolicy
from expense_core.schemas.enums import PolicyCheckStatus
from expense_core.schemas.tools import LineItemInput
from expense_core.tools import check_policy, classify_category, detect_duplicates
from expense_core.tools.duplicate_detector import CandidateLineItem, HistoricalLineItem


def run_intake(session: Session, item: LineItem, policy: BaselinePolicy) -> ClaimCheck:
    """Run policy + classifier + duplicate checks for one line item; persist + return the
    ClaimCheck. Does not commit — caller owns the transaction."""
    tool_input = LineItemInput(
        employee_id=item.employee_id,
        category=item.category,
        amount=item.amount,
        currency=item.currency,
        merchant=item.merchant,
        description=item.description,
        expense_date=item.expense_date,
        receipt_datetime=item.receipt_datetime,
        receipt_total=item.receipt_total,
        has_receipt=item.has_receipt,
    )

    policy_result = check_policy(tool_input, policy)
    category_result = classify_category(item.description, item.merchant)
    duplicate_result = detect_duplicates(
        CandidateLineItem(
            employee_id=item.employee_id,
            receipt_datetime=item.receipt_datetime,
            total=item.receipt_total or item.amount,
        ),
        _duplicate_history(session, item),
        near_match_days=policy.duplicate_near_match_days,
    )

    check = ClaimCheck(
        line_item_id=item.id,
        policy_result=policy_result.model_dump(mode="json"),
        category_result=category_result.model_dump(mode="json"),
        duplicate_result=duplicate_result.model_dump(mode="json"),
    )
    session.add(check)
    return check


def intake_passes(check: ClaimCheck) -> bool:
    """A line item clears intake when policy passes and there's no high duplicate risk."""
    policy_ok = (check.policy_result or {}).get("status") == PolicyCheckStatus.PASS.value
    dup_risk = (check.duplicate_result or {}).get("risk")
    return policy_ok and dup_risk in (None, "none", "low")


def _duplicate_history(session: Session, item: LineItem) -> list[HistoricalLineItem]:
    """Prior line items for the same employee — intra-sheet items are flagged via same_sheet."""
    rows = session.exec(
        select(LineItem).where(
            LineItem.employee_id == item.employee_id, LineItem.id != item.id
        )
    ).all()
    return [
        HistoricalLineItem(
            line_item_id=r.id,
            employee_id=r.employee_id,
            receipt_datetime=r.receipt_datetime,
            total=r.receipt_total or r.amount,
            same_sheet=(r.sheet_id == item.sheet_id),
        )
        for r in rows
    ]

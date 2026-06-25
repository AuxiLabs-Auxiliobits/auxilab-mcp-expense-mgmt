"""Model → DTO serialization shared across routers."""

from __future__ import annotations

import json
from decimal import Decimal
from urllib.parse import unquote, urlparse

from sqlmodel import Session, select

from app.models.agency import Agency
from app.models.attachment import Attachment
from app.models.decision import Decision
from app.models.expense_sheet import ExpenseSheet
from app.models.line_item import LineItem
from app.models.user import User
from app.schemas.dto import AttachmentOut, DecisionOut, LineItemOut, PolicyFlags, SheetOut
from app.services.state_machine import RESUBMITTABLE
from expense_core.policy import BaselinePolicy
from expense_core.schemas.enums import PolicyCheckStatus, SheetStatus
from expense_core.schemas.tools import LineItemInput
from expense_core.tools import check_policy

# A sheet's "Submit for Review" is only offered while drafting or after being sent back.
_SUBMITTABLE_STATES = {SheetStatus.DRAFT} | RESUBMITTABLE


def _attachment_out(sheet_id: str, line_item_id: str, a: Attachment) -> AttachmentOut:
    """Build the read DTO for a stored receipt: real size/type + the original filename
    (the blob name is `{attachment_id}-{original}`) + an auth'd download path."""
    name = unquote(urlparse(a.blob_uri).path).rsplit("/", 1)[-1]
    prefix = f"{a.id}-"
    if name.startswith(prefix):
        name = name[len(prefix):]
    return AttachmentOut(
        id=a.id,
        line_item_id=a.line_item_id,
        file_name=name or "receipt",
        file_type=a.file_type,
        size=a.size,
        blob_uri=a.blob_uri,
        scan_status=str(a.scan_status),
        download_url=f"/sheets/{sheet_id}/line-items/{line_item_id}/receipts/{a.id}/file",
    )


def sheet_to_out(
    session: Session, sheet: ExpenseSheet, *, policy: BaselinePolicy | None = None
) -> SheetOut:
    """Serialize a sheet to its read DTO, enriched for the sheet-detail UI.

    Pass `policy` to populate the draft-time `policy_flags` preview; without it the flags stay
    at zero (everything else is still computed). Names, totals, receipt and submit-gating
    fields are resolved here so the client doesn't re-implement them."""
    items = list(session.exec(select(LineItem).where(LineItem.sheet_id == sheet.id)).all())
    # Fetch the attachment rows once and group by line item (real size/name, not synthetic).
    att_rows = list(
        session.exec(
            select(Attachment).where(
                Attachment.line_item_id.in_([i.id for i in items] or [""])  # type: ignore[attr-defined]
            )
        ).all()
    )
    by_item: dict[str, list[Attachment]] = {}
    for a in att_rows:
        by_item.setdefault(a.line_item_id, []).append(a)
    counts = {iid: len(atts) for iid, atts in by_item.items()}

    out = SheetOut.model_validate(sheet)  # pulls id/status/version/period/timestamps directly
    line_outs: list[LineItemOut] = []
    for i in items:
        li = LineItemOut.model_validate(i)
        atts = by_item.get(i.id, [])
        li.receipt_count = len(atts)
        li.attachments = [_attachment_out(sheet.id, i.id, a) for a in atts]
        line_outs.append(li)
    out.line_items = line_outs

    # Display names for the FK columns the UI shows (owner + agency).
    employee = session.get(User, sheet.employee_id)
    agency = session.get(Agency, sheet.agency_id)
    out.employee_name = employee.name if employee else None
    out.agency_name = agency.name if agency else None

    # Resolve the finance decider's id → display name so the UI never shows a raw user id.
    if sheet.finance_decided_by:
        decider = session.get(User, sheet.finance_decided_by)
        out.finance_decided_by = decider.name if decider else "Finance"

    # Totals. Keep a per-currency breakdown (always correct) plus a flat total/currency for
    # the single-currency common case the summary panel renders.
    totals: dict[str, Decimal] = {}
    for i in items:
        totals[i.currency] = totals.get(i.currency, Decimal("0")) + i.amount
    out.totals_by_currency = totals
    out.total = sum(totals.values(), Decimal("0"))
    if not totals:
        out.currency = "USD"
    elif len(totals) == 1:
        out.currency = next(iter(totals))
    else:
        out.currency = None  # mixed currencies — client should read totals_by_currency

    # Receipt + submit gating (mirrors sheet_service.submit_sheet's pre-checks).
    out.missing_receipts = sum(1 for i in items if counts.get(i.id, 0) == 0)
    blockers: list[str] = []
    if sheet.status not in _SUBMITTABLE_STATES:
        blockers.append(f"Sheet cannot be submitted from status {sheet.status}.")
    else:
        if not items:
            blockers.append("Add a line item to submit.")
        if out.missing_receipts:
            n = out.missing_receipts
            blockers.append(f"{n} line item{'s' if n != 1 else ''} missing a receipt.")
    out.submit_blockers = blockers
    out.can_submit = not blockers

    # Policy preview (non-mutating dry run; authoritative intake runs at submission).
    if policy is not None and items:
        out.policy_flags = _policy_flags(items, policy)

    return out


def _policy_flags(items: list[LineItem], policy: BaselinePolicy) -> PolicyFlags:
    errors = warnings = 0
    for i in items:
        result = check_policy(_to_tool_input(i), policy)
        count = len(result.violations) or 1  # a FAIL/WARN with no detail still counts as one
        if result.status == PolicyCheckStatus.FAIL:
            errors += count
        elif result.status == PolicyCheckStatus.WARN:
            warnings += count
    return PolicyFlags(errors=errors, warnings=warnings)


def _to_tool_input(item: LineItem) -> LineItemInput:
    return LineItemInput(
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


def agency_to_out(session: Session, agency: Agency) -> AgencyOut:
    """Serialize an agency with its live active-user count (the admin table column)."""
    count = session.exec(
        select(func.count(User.id)).where(
            User.agency_id == agency.id,
            User.is_active == True,  # noqa: E712 — SQL boolean comparison
        )
    ).one()
    return AgencyOut(
        id=agency.id, name=agency.name, status=str(agency.status),
        created_by=agency.created_by, created_at=agency.created_at,
        user_count=int(count or 0),
    )


def agencies_to_out(session: Session, agencies: list[Agency]) -> list[AgencyOut]:
    """Batch serialize agencies with one grouped count query (avoids N per-agency queries)."""
    counts = dict(
        session.exec(
            select(User.agency_id, func.count(User.id))
            .where(User.is_active == True)  # noqa: E712
            .group_by(User.agency_id)
        ).all()
    )
    return [
        AgencyOut(
            id=a.id, name=a.name, status=str(a.status),
            created_by=a.created_by, created_at=a.created_at,
            user_count=int(counts.get(a.id, 0)),
        )
        for a in agencies
    ]


def decision_to_out(decision: Decision) -> DecisionOut:
    """Serialize a decision-trail row, decoding the stored cited-clauses JSON to a list."""
    clauses: list[str] = []
    if decision.cited_clauses:
        try:
            clauses = json.loads(decision.cited_clauses)
        except (ValueError, TypeError):
            clauses = []
    return DecisionOut(
        id=decision.id,
        actor_id=decision.actor_id,
        actor_role=decision.actor_role,
        action=decision.action,
        reason=decision.reason,
        llm_model_version=decision.llm_model_version,
        policy_version=decision.policy_version,
        cited_clauses=clauses,
        timestamp=decision.timestamp,
    )

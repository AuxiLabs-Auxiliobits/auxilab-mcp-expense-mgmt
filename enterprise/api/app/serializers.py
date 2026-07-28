"""Model → DTO serialization shared across routers."""

from __future__ import annotations

import json
from decimal import Decimal
from urllib.parse import unquote, urlparse

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.agency import Agency
from app.models.attachment import Attachment
from app.models.decision import Decision
from app.models.expense_sheet import ExpenseSheet
from app.models.line_item import LineItem
from app.models.user import User
from app.schemas.dto import (
    AgencyOut,
    AttachmentOut,
    DecisionOut,
    LineItemOut,
    PolicyFlags,
    SheetOut,
)
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
        filename=name or "receipt",
        file_type=a.file_type,
        size=a.size,
        blob_uri=a.blob_uri,
        scan_status=str(a.scan_status),
        download_url=f"/sheets/{sheet_id}/line-items/{line_item_id}/receipts/{a.id}/file",
    )


def _assemble_sheet(
    sheet: ExpenseSheet,
    items: list[LineItem],
    atts_by_item: dict[str, list[Attachment]],
    name_of: dict[str, str],
    agency_of: dict[str, str],
    policy: BaselinePolicy | None,
) -> SheetOut:
    """Build a SheetOut from already-resolved data (no DB access). Shared by the single-sheet
    and batched-list serializers so they can't diverge."""
    out = SheetOut.model_validate(sheet)  # id/status/version/period/timestamps
    line_outs: list[LineItemOut] = []
    for i in items:
        li = LineItemOut.model_validate(i)
        atts = atts_by_item.get(i.id, [])
        li.receipt_count = len(atts)
        li.attachments = [_attachment_out(sheet.id, i.id, a) for a in atts]
        line_outs.append(li)
    out.line_items = line_outs

    out.employee_name = name_of.get(sheet.employee_id)
    out.agency_name = agency_of.get(sheet.agency_id) if sheet.agency_id else None
    if sheet.finance_decided_by:
        out.finance_decided_by = name_of.get(sheet.finance_decided_by, "Finance")

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
        out.currency = None  # mixed currencies — client reads totals_by_currency

    out.missing_receipts = sum(1 for i in items if not atts_by_item.get(i.id))
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

    if policy is not None and items:
        out.policy_flags = _policy_flags(items, policy)
    return out


def sheet_to_out(
    session: Session, sheet: ExpenseSheet, *, policy: BaselinePolicy | None = None
) -> SheetOut:
    """Serialize ONE sheet (the detail endpoint). For lists use `sheets_to_out` to avoid N+1."""
    items = list(session.exec(select(LineItem).where(LineItem.sheet_id == sheet.id)).all())
    att_rows = session.exec(
        select(Attachment).where(
            Attachment.line_item_id.in_([i.id for i in items] or [""])  # type: ignore[attr-defined]
        )
    ).all()
    by_item: dict[str, list[Attachment]] = {}
    for a in att_rows:
        by_item.setdefault(a.line_item_id, []).append(a)

    name_of: dict[str, str] = {}
    employee = session.get(User, sheet.employee_id)
    if employee:
        name_of[sheet.employee_id] = employee.name
    if sheet.finance_decided_by:
        decider = session.get(User, sheet.finance_decided_by)
        if decider:
            name_of[sheet.finance_decided_by] = decider.name
    agency_of: dict[str, str] = {}
    if sheet.agency_id:
        agency = session.get(Agency, sheet.agency_id)
        if agency:
            agency_of[sheet.agency_id] = agency.name
    return _assemble_sheet(sheet, items, by_item, name_of, agency_of, policy)


def sheets_to_out(
    session: Session, sheets: list[ExpenseSheet], *, policy: BaselinePolicy | None = None
) -> list[SheetOut]:
    """Batched list serializer — resolves line items, attachments, and FK display names for
    the WHOLE result set in a fixed handful of queries instead of ~2N (perf: P-H1)."""
    if not sheets:
        return []
    sheet_ids = [s.id for s in sheets]
    all_items = list(
        session.exec(select(LineItem).where(LineItem.sheet_id.in_(sheet_ids))).all()  # type: ignore[attr-defined]
    )
    items_by_sheet: dict[str, list[LineItem]] = {}
    for i in all_items:
        items_by_sheet.setdefault(i.sheet_id, []).append(i)

    item_ids = [i.id for i in all_items] or [""]
    att_rows = list(
        session.exec(select(Attachment).where(Attachment.line_item_id.in_(item_ids))).all()  # type: ignore[attr-defined]
    )
    atts_by_item: dict[str, list[Attachment]] = {}
    for a in att_rows:
        atts_by_item.setdefault(a.line_item_id, []).append(a)

    user_ids = {s.employee_id for s in sheets} | {
        s.finance_decided_by for s in sheets if s.finance_decided_by
    }
    agency_ids = {s.agency_id for s in sheets if s.agency_id}
    name_of = {
        u.id: u.name
        for u in session.exec(select(User).where(User.id.in_(user_ids or [""]))).all()  # type: ignore[attr-defined]
    }
    agency_of = {
        a.id: a.name
        for a in session.exec(select(Agency).where(Agency.id.in_(agency_ids or [""]))).all()  # type: ignore[attr-defined]
    }
    return [
        _assemble_sheet(s, items_by_sheet.get(s.id, []), atts_by_item, name_of, agency_of, policy)
        for s in sheets
    ]


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

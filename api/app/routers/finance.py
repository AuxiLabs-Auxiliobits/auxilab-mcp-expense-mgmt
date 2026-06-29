"""Finance routes (SCOPING §3.1, §6.3). Manual-review queue + human decisions, overrides
of LLM decisions, the audit log, and the webhook the LLM approver worker posts decisions to."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth.dependencies import require, require_role
from app.db import get_session
from app.models.audit import AuditLog
from app.models.expense_sheet import ExpenseSheet
from app.models.line_item import LineItem
from app.pagination import PageParams
from app.principal import Principal, Role, Scope
from app.rbac.permissions import Capability
from app.schemas.dto import (
    FinanceHumanDecisionRequest,
    FinanceKpisOut,
    LlmDecisionRequest,
    PolicyCheckOut,
    PolicyMatchEvidence,
    SheetOut,
)
from app.serializers import sheet_to_out, sheets_to_out
from app.services import (
    finance_service,
    policy_compliance_service,
    reports_service,
    sheet_service,
)
from app.config import settings as app_settings
from expense_core.schemas.enums import SheetStatus

router = APIRouter(
    prefix="/finance",
    tags=["finance"],
    responses={
        401: {"description": "Missing or invalid bearer token"},
        403: {"description": "Insufficient role (Finance/Admin, or Agent for the webhook)"},
    },
)


@router.get("/queue", response_model=list[SheetOut], summary="Manual-review queue (LLM-routed sheets)")
async def manual_review_queue(
    page: PageParams = Depends(),
    principal: Principal = Depends(require(Capability.FINANCE_DECISION)),
    session: Session = Depends(get_session),
) -> list[SheetOut]:
    """Sheets the LLM routed for manual intervention (SCOPING §6.3). Paginated + bounded."""
    rows = session.exec(
        select(ExpenseSheet)
        .where(ExpenseSheet.status == SheetStatus.FINANCE_MANUAL_REVIEW)
        .order_by(ExpenseSheet.updated_at.desc())  # type: ignore[attr-defined]
        .limit(page.limit)
        .offset(page.offset)
    ).all()
    return sheets_to_out(session, list(rows))


@router.get(
    "/sheets",
    response_model=list[SheetOut],
    summary="All expense sheets (org-wide for Finance/Admin; own agency for Manager)",
)
async def all_sheets(
    page: PageParams = Depends(),
    principal: Principal = Depends(require(Capability.VIEW_SHEETS)),
    session: Session = Depends(get_session),
) -> list[SheetOut]:
    """Backs the Finance/Admin 'Expense Sheets' screen. Finance/Admin see every sheet; a
    Manager is scoped to their own agency (SCOPING §3.2). Paginated + bounded."""
    stmt = select(ExpenseSheet)
    if principal.scope is Scope.AGENCY:
        stmt = stmt.where(ExpenseSheet.agency_id == principal.agency_id)
    rows = session.exec(
        stmt.order_by(ExpenseSheet.updated_at.desc()).limit(page.limit).offset(page.offset)
    ).all()
    return sheets_to_out(session, list(rows))


@router.get("/kpis", response_model=FinanceKpisOut, summary="Finance dashboard KPIs")
async def finance_kpis(
    principal: Principal = Depends(require(Capability.VIEW_REPORTS)),
    session: Session = Depends(get_session),
) -> FinanceKpisOut:
    """Deterministically-computed finance KPIs (auto-approval rate, manual interventions,
    policy citations, compliance) for the analytics strip (SCOPING §4)."""
    return reports_service.build_finance_kpis(session, principal)


@router.post(
    "/process-pending",
    summary="Run the AI approver on sheets stuck in finance review",
)
async def process_pending(
    principal: Principal = Depends(require(Capability.FINANCE_DECISION)),
    session: Session = Depends(get_session),
) -> dict[str, int]:
    """Nudge: run the (offline) AI finance approver on every sheet still in IN_FINANCE_REVIEW
    in the caller's scope — for sheets handed off before the worker ran. Auto-approves clean
    sheets and routes flagged ones to the manual-review queue. Returns {processed, approved,
    routed}."""
    return finance_service.process_pending_finance(session, principal)


@router.post(
    "/sheets/{sheet_id}/policy-check",
    response_model=PolicyCheckOut,
    summary="Evaluate a sheet against the agency's RAG policy (read-only, shows matched points)",
    responses={404: {"description": "Sheet not found"}},
)
async def policy_check(
    sheet_id: str,
    principal: Principal = Depends(require(Capability.VIEW_SHEETS)),
    session: Session = Depends(get_session),
) -> PolicyCheckOut:
    """Run the AI Finance Approver's RAG + LLM policy evaluation against a sheet on demand and
    return the verdict, cited clauses, AND the exact policy chunks retrieved (which policy
    points the sheet was checked against). Read-only — it never changes the sheet's status, so
    Finance can audit any sheet (manual-review or already auto-approved) and see how its
    content/receipts line up with the indexed policy (SCOPING §6.3)."""
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    items = list(session.exec(select(LineItem).where(LineItem.sheet_id == sheet.id)).all())
    ev = policy_compliance_service.evaluate_sheet(sheet, items, app_settings)
    return PolicyCheckOut(
        decision=ev.decision,
        confidence=ev.confidence,
        cited_clauses=ev.cited_clauses,
        reason_detail=ev.reason_detail,
        evidence=[
            PolicyMatchEvidence(policy_version=e.policy_version, text=e.text) for e in ev.evidence
        ],
        policy_found=ev.policy_found,
        llm_used=ev.llm_used,
    )


@router.post(
    "/sheets/{sheet_id}/decision",
    response_model=SheetOut,
    summary="Finance human decision (approve/reject)",
    responses={404: {"description": "Sheet not found"}},
)
async def human_decision(
    sheet_id: str,
    body: FinanceHumanDecisionRequest,
    principal: Principal = Depends(require(Capability.FINANCE_DECISION)),
    session: Session = Depends(get_session),
) -> SheetOut:
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    sheet = finance_service.finance_human_decision(
        session, sheet, principal, approve=body.approve, reason=body.reason
    )
    return sheet_to_out(session, sheet)


@router.post(
    "/sheets/{sheet_id}/override",
    response_model=SheetOut,
    summary="Override the LLM decision (reason required)",
    responses={404: {"description": "Sheet not found"}},
)
async def override(
    sheet_id: str,
    body: FinanceHumanDecisionRequest,
    principal: Principal = Depends(require(Capability.OVERRIDE_LLM_DECISION)),
    session: Session = Depends(get_session),
) -> SheetOut:
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    sheet = finance_service.override_decision(
        session, sheet, principal, approve=body.approve, reason=body.reason
    )
    return sheet_to_out(session, sheet)


@router.post(
    "/sheets/{sheet_id}/llm-decision",
    response_model=SheetOut,
    summary="LLM-approver webhook (Agent role) — post a decision",
    responses={404: {"description": "Sheet not found"}},
)
async def llm_decision(
    sheet_id: str,
    body: LlmDecisionRequest,
    principal: Principal = Depends(require_role(Role.AGENT)),
    session: Session = Depends(get_session),
) -> SheetOut:
    """Posted by the LLM approver worker (authenticated as the AGENT service principal)."""
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    sheet = finance_service.apply_llm_decision(
        session, sheet,
        decision=body.decision, model_version=body.model_version,
        policy_version=body.policy_version, cited_clauses=body.cited_clauses,
        confidence=body.confidence,
    )
    return sheet_to_out(session, sheet)


@router.get("/audit", summary="Immutable audit log (most recent first)")
async def audit_log(
    principal: Principal = Depends(require(Capability.VIEW_AUDIT_LOG)),
    session: Session = Depends(get_session),
    limit: int = 200,
) -> list[AuditLog]:
    return list(
        session.exec(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)).all()
    )

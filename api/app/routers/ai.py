"""Agentic layer API — advisory AI recommendations, the AI Workspace, feedback, and analytics.

Everything here is **advisory**: it reads sheets the caller is already allowed to see (RBAC
scoped) and returns/records recommendations. It exposes NO endpoint that approves, rejects, or
modifies a sheet — humans act through the normal manager/finance endpoints. Every generation is
audit-logged.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.auth.dependencies import current_principal
from app.db import get_session
from app.models.ai import AiFeedback, AiRecommendation
from app.models.decision import Decision
from app.models.expense_sheet import ExpenseSheet
from app.principal import Principal, Role
from app.rbac.scope import assert_can_view_sheet
from app.services import ai_recommendations as ai
from app.services import audit_service
from app.services import sheet_service

router = APIRouter(
    prefix="/ai",
    tags=["ai"],
    responses={401: {"description": "Missing or invalid bearer token"}},
)


def _rec_dict(r: AiRecommendation) -> dict[str, Any]:
    return {
        "id": r.id, "sheet_id": r.sheet_id, "summary": r.summary,
        "risk_score": r.risk_score, "risk_band": r.risk_band,
        "policy_compliant": r.policy_compliant, "duplicate_likelihood": r.duplicate_likelihood,
        "duplicate_band": r.duplicate_band, "missing_info": r.missing_info,
        "recommended_action": r.recommended_action, "confidence": r.confidence,
        "rationale": r.rationale, "sheet_status": r.sheet_status,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _scope_sheets(session: Session, principal: Principal) -> list[ExpenseSheet]:
    """Sheets the caller may act on — same scoping as the rest of the app."""
    q = select(ExpenseSheet)
    if principal.role == Role.EMPLOYEE:
        q = q.where(ExpenseSheet.employee_id == principal.subject_id)
    elif principal.role == Role.MANAGER:
        q = q.where(ExpenseSheet.agency_id == principal.agency_id)
    # finance / admin: org-wide
    return list(session.exec(q).all())


# --- per-sheet recommendation (Phase 3 + 6) ----------------------------------------------- #
@router.get("/sheets/{sheet_id}/recommendation", summary="Advisory AI recommendation for a sheet")
async def sheet_recommendation(
    sheet_id: str,
    refresh: bool = False,
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> dict:
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    assert_can_view_sheet(principal, sheet)  # RBAC: same visibility as viewing the sheet
    rec = ai.generate(session, sheet, principal) if refresh else ai.get_or_generate(session, sheet, principal)
    return _rec_dict(rec)


# --- AI Workspace (Phase 5) --------------------------------------------------------------- #
@router.get("/workspace", summary="AI Workspace — recommendations, risks, duplicates, gaps")
async def workspace(
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> dict:
    sheets = _scope_sheets(session, principal)
    recs = [ai.get_or_generate(session, s, principal) for s in sheets]
    title_by_id = {s.id: (s.title or "Untitled") for s in sheets}

    def card(r: AiRecommendation) -> dict:
        d = _rec_dict(r)
        d["title"] = title_by_id.get(r.sheet_id, "Untitled")
        return d

    actionable = [r for r in recs if r.risk_band in ("medium", "high") or not r.policy_compliant
                  or r.duplicate_band in ("medium", "high") or r.missing_info]
    return {
        "role": str(principal.role),
        "counts": {
            "sheets_analyzed": len(recs),
            "high_risk": sum(r.risk_band == "high" for r in recs),
            "policy_violations": sum(not r.policy_compliant for r in recs),
            "duplicate_candidates": sum(r.duplicate_band in ("medium", "high") for r in recs),
            "missing_receipts": sum(bool(r.missing_info) for r in recs),
        },
        "pending_recommendations": [card(r) for r in sorted(actionable, key=lambda r: -r.risk_score)],
        "high_risk": [card(r) for r in recs if r.risk_band == "high"],
        "duplicate_candidates": [card(r) for r in recs if r.duplicate_band in ("medium", "high")],
        "policy_violations": [card(r) for r in recs if not r.policy_compliant],
        "missing_receipts": [card(r) for r in recs if r.missing_info],
        "recent_ai_actions": _recent_ai_actions(session, principal),
    }


def _recent_ai_actions(session: Session, principal: Principal) -> list[dict]:
    q = select(AiRecommendation).order_by(AiRecommendation.created_at.desc())
    if principal.role == Role.EMPLOYEE:
        q = q.where(AiRecommendation.employee_id == principal.subject_id)
    elif principal.role == Role.MANAGER:
        q = q.where(AiRecommendation.agency_id == principal.agency_id)
    rows = list(session.exec(q).all())[:10]
    return [
        {"sheet_id": r.sheet_id, "action": "Analyzed sheet", "risk_band": r.risk_band,
         "recommended_action": r.recommended_action,
         "at": r.created_at.isoformat() if r.created_at else None}
        for r in rows
    ]


# --- feedback (Phase 8) ------------------------------------------------------------------- #
class FeedbackIn(BaseModel):
    helpful: bool | None = None
    decision: str | None = Field(default=None, description="accepted | ignored | dismissed")
    reason: str | None = None


@router.post("/recommendations/{rec_id}/feedback", summary="Record feedback on a recommendation")
async def feedback(
    rec_id: str,
    body: FeedbackIn,
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> dict:
    rec = session.get(AiRecommendation, rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
    sheet = sheet_service.get_sheet_or_404(session, rec.sheet_id)
    assert_can_view_sheet(principal, sheet)  # only people who can see the sheet may rate it
    fb = AiFeedback(
        recommendation_id=rec_id, sheet_id=rec.sheet_id, user_id=principal.subject_id,
        helpful=body.helpful, decision=body.decision, reason=body.reason,
    )
    session.add(fb)
    audit_service.record(
        session, actor=principal, action="AI_FEEDBACK_RECORDED",
        entity=f"ai_recommendation:{rec_id}", agency_id=sheet.agency_id,
        after={"helpful": body.helpful, "decision": body.decision},
    )
    session.commit()
    return {"ok": True}


# --- analytics (Phase 9) ------------------------------------------------------------------ #
@router.get("/analytics", summary="AI analytics — generation, acceptance, impact")
async def analytics(
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> dict:
    rq = select(AiRecommendation)
    fq = select(AiFeedback)
    if principal.role == Role.EMPLOYEE:
        rq = rq.where(AiRecommendation.employee_id == principal.subject_id)
    elif principal.role == Role.MANAGER:
        rq = rq.where(AiRecommendation.agency_id == principal.agency_id)
    recs = list(session.exec(rq).all())
    fbs = list(session.exec(fq).all())
    rec_ids = {r.id for r in recs}
    fbs = [f for f in fbs if f.recommendation_id in rec_ids]

    decided = [f for f in fbs if f.decision in ("accepted", "ignored", "dismissed")]
    accepted = sum(f.decision == "accepted" for f in decided)
    rated = [f for f in fbs if f.helpful is not None]
    helpful = sum(bool(f.helpful) for f in rated)
    current = [r for r in recs if not r.superseded]

    return {
        "recommendations_generated": len(recs),
        "current_recommendations": len(current),
        "by_risk_band": {b: sum(r.risk_band == b for r in current) for b in ("low", "medium", "high")},
        "policy_violations_detected": sum(not r.policy_compliant for r in current),
        "duplicate_candidates_flagged": sum(r.duplicate_band in ("medium", "high") for r in current),
        "feedback_count": len(fbs),
        "acceptance_rate_pct": round(100 * accepted / len(decided), 1) if decided else None,
        "helpful_rate_pct": round(100 * helpful / len(rated), 1) if rated else None,
        "avg_approval_hours": _avg_approval_hours(session, principal),
        "engagement_pct": round(100 * len(fbs) / len(recs), 1) if recs else None,
    }


def _avg_approval_hours(session: Session, principal: Principal) -> float | None:
    q = select(ExpenseSheet).where(ExpenseSheet.submitted_at.is_not(None))
    if principal.role == Role.MANAGER:
        q = q.where(ExpenseSheet.agency_id == principal.agency_id)
    elif principal.role == Role.EMPLOYEE:
        q = q.where(ExpenseSheet.employee_id == principal.subject_id)
    deltas: list[float] = []
    for s in session.exec(q).all():
        if s.submitted_at and s.updated_at and str(s.status) in (
            "SheetStatus.APPROVED", "APPROVED", "SheetStatus.FINANCE_APPROVED", "FINANCE_APPROVED"
        ):
            deltas.append((s.updated_at - s.submitted_at).total_seconds() / 3600.0)
    return round(sum(deltas) / len(deltas), 1) if deltas else None

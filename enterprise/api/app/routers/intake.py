"""Live intake routes (SCOPING §6.1). Stateless, as-you-type checks for the line-item form:
the **authoritative deterministic** policy check (engine `check_policy`). This replaces the
client-side mock so the UI shows the real backend/agency policy. LLM/RAG stays advisory.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends

from app.auth.dependencies import current_principal
from app.config import settings
from app.deps import get_policy
from app.principal import Principal
from app.schemas.dto import (
    PolicyAdvisoryOut,
    PolicyAdvisoryRequest,
    PolicyPreviewOut,
    PolicyPreviewRequest,
    PolicyViolationOut,
)
from app.services import policy_advisory_service
from expense_core.policy import BaselinePolicy
from expense_core.schemas.tools import LineItemInput
from expense_core.tools import check_policy

router = APIRouter(
    prefix="/intake",
    tags=["intake"],
    responses={401: {"description": "Missing or invalid bearer token"}},
)


@router.post("/policy-check", response_model=PolicyPreviewOut, summary="Deterministic policy check (live)")
async def policy_check(
    body: PolicyPreviewRequest,
    principal: Principal = Depends(current_principal),
    policy: BaselinePolicy = Depends(get_policy),
) -> PolicyPreviewOut:
    """Dry-run a draft line item against the effective policy and return violations/warnings.
    Authoritative and deterministic — the same engine rules that run at submission."""
    tool_input = LineItemInput(
        employee_id=principal.subject_id,
        category=body.category,
        amount=body.amount,
        currency=body.currency,
        merchant=body.merchant,
        description=body.description,
        expense_date=body.expense_date or date.today(),
        receipt_datetime=body.receipt_datetime,
        receipt_total=body.receipt_total,
        has_receipt=body.has_receipt,
    )
    result = check_policy(tool_input, policy)
    return PolicyPreviewOut(
        status=result.status.value,
        recommended_action=result.recommended_action.value,
        violations=[
            PolicyViolationOut(code=v.code, message=v.message, field=v.field)
            for v in result.violations
        ],
    )


@router.post(
    "/policy-advisory",
    response_model=PolicyAdvisoryOut,
    summary="Cited agency policy clause (RAG advisory — never blocks)",
)
async def policy_advisory(
    body: PolicyAdvisoryRequest,
    principal: Principal = Depends(current_principal),
) -> PolicyAdvisoryOut:
    """Retrieve the most relevant clause from the caller's agency policy (Azure AI Search),
    advisory only. Returns no clause offline / when Search isn't configured."""
    query = " ".join(
        part
        for part in [
            body.category.value if body.category else "",
            body.merchant,
            body.description,
        ]
        if part
    ).strip()
    return policy_advisory_service.advisory(query, principal.agency_id, settings)

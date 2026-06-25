"""AI recommendation engine — advisory analysis of an expense sheet.

Deterministic and offline: it composes the existing `expense_core` tools (policy_checker,
duplicate_detector) with transparent risk heuristics. It produces a structured, explainable
recommendation (summary, risk, policy compliance, missing info, duplicate likelihood, a
*suggested* next action, and confidence) and persists it — but it NEVER changes sheet state.
Humans act through the normal endpoints; this only advises. Swap in an LLM later for the narrative
without changing the contract.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlmodel import Session, select

from expense_core.policy import load_baseline_policy
from expense_core.schemas.tools import LineItemInput, PolicyCheckStatus
from expense_core.tools.duplicate_detector import CandidateLineItem, HistoricalLineItem
from expense_core.tools import check_policy, detect_duplicates

from app.models.ai import AiRecommendation
from app.models.expense_sheet import ExpenseSheet
from app.models.line_item import LineItem
from app.principal import Principal
from app.services import audit_service

_LARGE_AMOUNT = 500.0  # elevated-attention threshold (advisory)
_POLICY = load_baseline_policy()


def _f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def analyze(items: list[LineItem], history: list[LineItem], sheet_status: str | None) -> dict[str, Any]:
    """Pure analysis (no DB writes) — easy to unit test."""
    if not items:
        return {
            "summary": "This sheet has no line items yet.",
            "risk_score": 0.0, "risk_band": "low", "policy_compliant": True,
            "duplicate_likelihood": 0.0, "duplicate_band": "none",
            "missing_info": ["No line items added yet."], "recommended_action": "add_items",
            "confidence": "low",
            "rationale": {
                "why": "There is nothing to analyze until line items are added.",
                "data_analyzed": ["0 line items"], "policies_considered": [],
            },
        }

    # Build duplicate-detection history once (other items by the same employee).
    hist_models = [
        HistoricalLineItem(
            line_item_id=h.id, employee_id=h.employee_id,
            receipt_datetime=h.receipt_datetime,
            total=h.receipt_total if h.receipt_total is not None else h.amount,
            same_sheet=(h.sheet_id == items[0].sheet_id),
        )
        for h in history
    ]

    policy_fail = policy_warn = missing_receipts = uncategorized = large_count = 0
    total = Decimal("0")
    at_risk = Decimal("0")
    max_dup = 0.0
    clauses: list[str] = []
    missing_info: list[str] = []

    for it in items:
        total += it.amount or Decimal("0")
        li = LineItemInput(
            employee_id=it.employee_id, category=it.category, amount=it.amount or Decimal("0"),
            currency=it.currency or "USD", merchant=it.merchant or "", description=it.description or "",
            expense_date=it.expense_date, receipt_datetime=it.receipt_datetime,
            receipt_total=it.receipt_total, has_receipt=bool(it.has_receipt),
        )
        pr = check_policy(li, _POLICY)
        if pr.status == PolicyCheckStatus.FAIL:
            policy_fail += 1
            at_risk += it.amount or Decimal("0")
        elif pr.status == PolicyCheckStatus.WARN:
            policy_warn += 1
        for v in pr.violations:
            label = getattr(v, "clause", None) or getattr(v, "code", None) or getattr(v, "message", "")
            if label:
                clauses.append(str(label))

        if not it.has_receipt:
            missing_receipts += 1
        if it.category is None:
            uncategorized += 1
        if _f(it.amount) >= _LARGE_AMOUNT:
            large_count += 1

        cand = CandidateLineItem(
            employee_id=it.employee_id, receipt_datetime=it.receipt_datetime,
            total=it.receipt_total if it.receipt_total is not None else (it.amount or Decimal("0")),
        )
        dr = detect_duplicates(cand, [h for h in hist_models if h.line_item_id != it.id])
        max_dup = max(max_dup, _f(dr.risk_score))

    # --- aggregate to a 0..100 risk score (transparent weights) ---
    score = min(100.0, 30.0 * policy_fail + 12.0 * missing_receipts + 25.0 * max_dup
                + (10.0 if large_count else 0.0) + 4.0 * policy_warn)
    band = "high" if score >= 60 else "medium" if score >= 25 else "low"
    if (policy_fail or max_dup >= 0.8) and band == "low":
        band = "medium"

    dup_band = "high" if max_dup >= 0.8 else "medium" if max_dup >= 0.5 else "low" if max_dup > 0 else "none"

    if missing_receipts:
        missing_info.append(f"{missing_receipts} line item(s) missing a receipt.")
    if uncategorized:
        missing_info.append(f"{uncategorized} line item(s) have no category.")
    if policy_fail:
        missing_info.append(f"{policy_fail} line item(s) fail policy (e.g. over a cap).")

    if policy_fail or missing_receipts:
        action = "request_changes"
        why = "There are policy failures or missing receipts that should be fixed before approval."
    elif max_dup >= 0.5:
        action = "review_duplicate"
        why = "One or more line items look like possible duplicates and warrant a closer look."
    elif large_count or policy_warn:
        action = "review"
        why = "Amounts are elevated or there are policy warnings worth a quick review."
    else:
        action = "approve"
        why = "All items have receipts and pass policy with no duplicate signal."

    receipts_complete = missing_receipts == 0 and all(i.receipt_total is not None for i in items)
    confidence = "high" if receipts_complete else "medium"

    summary = (
        f"{len(items)} line item(s) totaling ${_f(total):,.2f}. "
        f"{policy_fail} policy failure(s), {policy_warn} warning(s), {missing_receipts} missing "
        f"receipt(s); duplicate risk **{dup_band}**. Suggested: {action.replace('_', ' ')}."
    )

    return {
        "summary": summary,
        "risk_score": round(score, 1), "risk_band": band,
        "policy_compliant": policy_fail == 0,
        "duplicate_likelihood": round(max_dup, 3), "duplicate_band": dup_band,
        "missing_info": missing_info, "recommended_action": action, "confidence": confidence,
        "rationale": {
            "why": why,
            "data_analyzed": [
                f"{len(items)} line item(s) (${_f(total):,.2f} total)",
                f"{missing_receipts} missing receipt(s)",
                f"{len(history)} prior item(s) checked for duplicates",
                "agency baseline policy",
            ],
            "policies_considered": sorted(set(clauses)) or ["baseline expense policy (caps, receipts, dates)"],
            "total_at_risk": f"${_f(at_risk):,.2f}",
        },
    }


def generate(session: Session, sheet: ExpenseSheet, actor: Principal | None = None) -> AiRecommendation:
    """Compute + persist the current recommendation for a sheet (supersedes any prior one).
    Advisory only — writes an AiRecommendation row + an audit entry; never touches sheet state."""
    items = list(session.exec(select(LineItem).where(LineItem.sheet_id == sheet.id)).all())
    history = list(
        session.exec(
            select(LineItem).where(LineItem.employee_id == sheet.employee_id)
        ).all()
    )
    data = analyze(items, history, str(sheet.status))

    # supersede any existing current recommendation for this sheet
    for prior in session.exec(
        select(AiRecommendation).where(
            AiRecommendation.sheet_id == sheet.id, AiRecommendation.superseded == False  # noqa: E712
        )
    ).all():
        prior.superseded = True
        session.add(prior)

    rec = AiRecommendation(
        sheet_id=sheet.id, agency_id=sheet.agency_id, employee_id=sheet.employee_id,
        sheet_status=str(sheet.status), **data,
    )
    session.add(rec)
    audit_service.record(
        session, actor=actor, action="AI_RECOMMENDATION_GENERATED",
        entity=f"expense_sheet:{sheet.id}", agency_id=sheet.agency_id,
        after={"risk_band": rec.risk_band, "risk_score": rec.risk_score,
               "recommended_action": rec.recommended_action, "confidence": rec.confidence},
    )
    session.commit()
    session.refresh(rec)
    return rec


def get_current(session: Session, sheet_id: str) -> AiRecommendation | None:
    return session.exec(
        select(AiRecommendation).where(
            AiRecommendation.sheet_id == sheet_id, AiRecommendation.superseded == False  # noqa: E712
        )
    ).first()


def get_or_generate(session: Session, sheet: ExpenseSheet, actor: Principal | None = None) -> AiRecommendation:
    return get_current(session, sheet.id) or generate(session, sheet, actor)

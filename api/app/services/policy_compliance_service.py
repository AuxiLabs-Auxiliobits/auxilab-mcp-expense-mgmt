"""AI Finance Approver — policy compliance check via RAG + LLM (SCOPING §6.3).

Retrieves the agency's indexed policy from Azure AI Search, enriches it with the
sheet's line items and receipt-scan data, then asks the LLM to evaluate compliance.
Returns a structured verdict with cited policy clauses AND the retrieved policy evidence
(the exact policy chunks considered) so Finance can audit which policy points matched and
override if needed.

Falls back to the receipt-scan `needs_human_review` flag when Azure Search/Foundry are not
configured (offline / local dev without the full Azure stack).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from app.config import Settings
from app.models.expense_sheet import ExpenseSheet
from app.models.line_item import LineItem
from expense_core.schemas.enums import FinanceDecision

logger = logging.getLogger(__name__)

_AUTO_APPROVE_THRESHOLD = 0.75


@dataclass
class PolicyEvidence:
    """One retrieved policy chunk that was considered when evaluating the sheet."""

    policy_version: str
    text: str


@dataclass
class PolicyEvaluation:
    """Full result of evaluating a sheet against the agency's policy."""

    decision: FinanceDecision
    confidence: float
    cited_clauses: list[str]
    reason_detail: str | None
    evidence: list[PolicyEvidence] = field(default_factory=list)
    policy_found: bool = False  # did we retrieve any agency policy from the index?
    llm_used: bool = False  # was the verdict produced by the LLM (vs. the offline fallback)?


def evaluate_sheet(
    sheet: ExpenseSheet,
    items: list[LineItem],
    settings: Settings,
) -> PolicyEvaluation:
    """Evaluate an expense sheet against the agency's policy documents using RAG + LLM.

    Always returns a PolicyEvaluation; on any failure it degrades to the receipt-scan
    fallback but still carries whatever policy evidence was retrieved."""
    if not settings.search_endpoint or not sheet.agency_id:
        return _fallback_evaluation(items, evidence=[], policy_found=False)

    evidence: list[PolicyEvidence] = []
    try:
        evidence = _fetch_policy_chunks(sheet, items, settings)
        if not evidence:
            logger.info(
                "no policy chunks found for agency %s — falling back to receipt-scan flags",
                sheet.agency_id,
            )
            return _fallback_evaluation(items, evidence=[], policy_found=False)

        return _llm_evaluate(sheet, items, evidence, settings)
    except Exception:  # noqa: BLE001 — best-effort; never fail the approval path
        logger.warning(
            "policy compliance check failed (sheet=%s agency=%s)",
            sheet.id, sheet.agency_id, exc_info=True,
        )
        return _fallback_evaluation(items, evidence=evidence, policy_found=bool(evidence))


def check_sheet_against_policy(
    sheet: ExpenseSheet,
    items: list[LineItem],
    settings: Settings,
) -> tuple[FinanceDecision, float, list[str], str | None]:
    """Thin tuple wrapper kept for the finance approver path (run_offline_approver)."""
    ev = evaluate_sheet(sheet, items, settings)
    return ev.decision, ev.confidence, ev.cited_clauses, ev.reason_detail


# --------------------------------------------------------------------------- #
# Azure AI Search — policy chunk retrieval                                     #
# --------------------------------------------------------------------------- #

def _fetch_policy_chunks(
    sheet: ExpenseSheet,
    items: list[LineItem],
    settings: Settings,
) -> list[PolicyEvidence]:
    """Retrieve the most relevant agency policy chunks from Azure AI Search."""
    from azure.search.documents import SearchClient  # noqa: PLC0415

    from app.services.policy_advisory_service import _search_credential  # noqa: PLC0415

    client = SearchClient(
        endpoint=settings.search_endpoint,
        index_name=settings.search_index_name,
        credential=_search_credential(settings),
    )

    # Build a query covering the expense categories and merchants so the search surface
    # covers the per-category limits and rules most likely to be relevant.
    categories = {
        li.category.value.replace("_", " ") if li.category else "general expense"
        for li in items
    }
    merchants = {li.merchant for li in items if li.merchant}
    query_parts = list(categories) + list(merchants)[:3] + ["reimbursement policy limit"]
    query = " ".join(query_parts)

    results = client.search(
        search_text=query,
        filter=f"agency_id eq '{sheet.agency_id}'",
        top=5,
    )

    evidence: list[PolicyEvidence] = []
    for doc in results:
        content = str(doc.get("content") or "").strip()
        if content:
            evidence.append(
                PolicyEvidence(
                    policy_version=str(doc.get("policy_version") or "current"),
                    text=content,
                )
            )
    return evidence


# --------------------------------------------------------------------------- #
# LLM evaluation                                                               #
# --------------------------------------------------------------------------- #

def _llm_evaluate(
    sheet: ExpenseSheet,
    items: list[LineItem],
    evidence: list[PolicyEvidence],
    settings: Settings,
) -> PolicyEvaluation:
    """Run the LLM compliance check against the retrieved policy chunks.

    Falls back to receipt-scan flags (but keeps the evidence) when Foundry isn't configured."""
    if not settings.foundry_endpoint:
        return _fallback_evaluation(items, evidence=evidence, policy_found=True)

    from expense_core.llm.gateway import ChatMessage  # noqa: PLC0415
    from expense_core.llm.providers import AzureFoundryProvider  # noqa: PLC0415

    llm = AzureFoundryProvider(
        endpoint=settings.foundry_endpoint,
        deployment=settings.foundry_chat_deployment,
        api_key=settings.foundry_api_key or None,
        api_version=settings.foundry_api_version,
    )

    policy_text = "\n\n---\n\n".join(e.text for e in evidence)[:3000]
    sheet_summary = _build_sheet_summary(sheet, items)

    system_prompt = (
        "You are an AI Finance Approver for an enterprise expense management system. "
        "Evaluate whether the employee's expense sheet complies with their company's "
        "expense reimbursement policy.\n\n"
        "Instructions:\n"
        "- Check EVERY line item against the policy: limits, allowed categories, and "
        "receipt requirements.\n"
        "- Also check receipt scan data: if a receipt total does not match the entered "
        "amount, flag it.\n"
        "- If ALL items clearly comply: return APPROVED with high confidence and cite the "
        "specific policy clauses that justify approval — Finance needs to audit your "
        "reasoning and may override.\n"
        "- If ANY item violates policy, has a mismatched receipt, or is genuinely "
        "ambiguous: return ROUTED_TO_HUMAN and cite the specific concern.\n"
        "- Be specific in cited_clauses — quote or paraphrase the exact policy text and tie "
        "it to the line item (e.g. \"Meals capped at $50/day — $45 dinner is within limit\").\n\n"
        "Respond ONLY with valid JSON (no markdown, no preamble):\n"
        '{"decision":"APPROVED"|"ROUTED_TO_HUMAN","confidence":0.0-1.0,'
        '"cited_clauses":["..."],"reason_detail":"..."}'
    )

    user_prompt = (
        f"AGENCY EXPENSE POLICY:\n{policy_text}\n\n"
        f"EXPENSE SHEET:\n{sheet_summary}\n\n"
        "Evaluate this sheet against the policy. Cite specific policy clauses. "
        "Return only valid JSON."
    )

    raw = llm.complete(
        [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ],
        max_tokens=600,
    )

    verdict = _parse_verdict(raw)
    decision_str = str(verdict.get("decision", "ROUTED_TO_HUMAN")).upper()
    confidence = max(0.0, min(1.0, float(verdict.get("confidence", 0.6))))
    cited = [str(c) for c in (verdict.get("cited_clauses") or [])][:6]
    reason_detail = str(verdict.get("reason_detail") or "").strip() or None

    if decision_str == "APPROVED" and confidence >= _AUTO_APPROVE_THRESHOLD:
        return PolicyEvaluation(
            decision=FinanceDecision.APPROVED,
            confidence=confidence,
            cited_clauses=cited or ["Sheet complies with agency policy."],
            reason_detail=reason_detail,
            evidence=evidence,
            policy_found=True,
            llm_used=True,
        )

    # Route to human: if the LLM said APPROVED but confidence is too low, note why.
    if decision_str == "APPROVED":
        reason_detail = (
            f"Confidence {confidence:.0%} below auto-approval threshold. " + (reason_detail or "")
        ).strip()
    return PolicyEvaluation(
        decision=FinanceDecision.ROUTED_TO_HUMAN,
        confidence=confidence,
        cited_clauses=cited,
        reason_detail=reason_detail,
        evidence=evidence,
        policy_found=True,
        llm_used=True,
    )


def _parse_verdict(raw: str | None) -> dict:
    """Parse the LLM's JSON verdict, tolerating markdown code fences."""
    raw_stripped = (raw or "").strip()
    if raw_stripped.startswith("```"):
        parts = raw_stripped.split("```")
        raw_stripped = parts[1] if len(parts) > 1 else raw_stripped
        if raw_stripped.startswith("json"):
            raw_stripped = raw_stripped[4:]
        raw_stripped = raw_stripped.strip()
    try:
        return json.loads(raw_stripped)
    except (ValueError, TypeError):
        return {}


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _build_sheet_summary(sheet: ExpenseSheet, items: list[LineItem]) -> str:
    """Build a human-readable summary of the sheet + line items + receipt scan data for the LLM."""
    lines = [
        f"Sheet: {sheet.title or 'Untitled'} | Period: {sheet.period or 'N/A'} | Agency: {sheet.agency_id}",
        "",
        "LINE ITEMS:",
    ]
    for i, li in enumerate(items, 1):
        cat = li.category.value.replace("_", " ") if li.category else "Uncategorized"
        lines.append(f"{i}. Category: {cat}")
        lines.append(f"   Merchant: {li.merchant}  |  Amount: {li.currency} {li.amount}")
        if li.description:
            lines.append(f"   Description: {li.description}")
        if li.expense_date:
            lines.append(f"   Expense date: {li.expense_date}")
        # Receipt scan data — the LLM should factor in scan vs entered discrepancies.
        if li.receipt_total is not None:
            match_status = (
                "MATCHES entered amount" if not li.needs_human_review
                else "MISMATCH with entered amount"
            )
            lines.append(f"   Receipt scan total: {li.currency} {li.receipt_total} ({match_status})")
            if li.tax is not None:
                lines.append(f"   Tax on receipt: {li.currency} {li.tax}")
        if li.needs_human_review and li.review_reason:
            lines.append(f"   *** FLAGGED BY SCAN: {li.review_reason} ***")
    return "\n".join(lines)


def _fallback_evaluation(
    items: list[LineItem],
    *,
    evidence: list[PolicyEvidence],
    policy_found: bool,
) -> PolicyEvaluation:
    """Offline / LLM-unavailable fallback: route scan-flagged sheets; auto-approve clean ones.
    Carries any retrieved policy evidence so Finance still sees the matched policy text."""
    flagged = [li for li in items if li.needs_human_review]
    if flagged:
        cited = [li.review_reason for li in flagged if li.review_reason][:3]
        return PolicyEvaluation(
            decision=FinanceDecision.ROUTED_TO_HUMAN,
            confidence=0.58,
            cited_clauses=cited,
            reason_detail=f"{len(flagged)} line item(s) flagged by receipt scan — manual check required.",
            evidence=evidence,
            policy_found=policy_found,
            llm_used=False,
        )
    return PolicyEvaluation(
        decision=FinanceDecision.APPROVED,
        confidence=0.96,
        cited_clauses=["No receipt discrepancies detected."],
        reason_detail=None,
        evidence=evidence,
        policy_found=policy_found,
        llm_used=False,
    )

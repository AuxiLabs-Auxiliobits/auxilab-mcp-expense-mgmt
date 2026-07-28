"""Acceptance tests for the LLM Finance Approver (SCOPING §6.3, §20.E).

Offline only: InMemoryRetriever + LocalEcho + NoopShield. No Azure, no langgraph required.
Covers the §20.E worked examples plus the missing-policy route-to-human guardrail (§8).
"""

from __future__ import annotations

from decimal import Decimal

from expense_core.llm.providers import LocalEchoProvider
from expense_core.schemas.enums import FinanceDecision, LineItemStatus

from workers.finance_approver.runner import approve_sheet
from workers.finance_approver.state import ApproverLineItem, FinanceApproverState
from workers.guardrails.prompt_shield import NoopShield
from workers.rag.retriever import InMemoryRetriever

WIFI_CLAUSE = "Wi-Fi / internet reimbursement is capped at $100; any amount above is rejected."


def _retriever() -> InMemoryRetriever:
    return InMemoryRetriever({"crispin": [WIFI_CLAUSE]}, policy_version="crispin-2026.06")


def _sheet(amount: str) -> FinanceApproverState:
    return FinanceApproverState(
        sheet_id="S1",
        agency_id="crispin",
        line_items=[
            ApproverLineItem(
                id="li-1",
                category="Software / Subscriptions",
                amount=Decimal(amount),
                merchant="Comcast",
                description="Home Wi-Fi internet",
            )
        ],
    )


def _run(state: FinanceApproverState, retriever: InMemoryRetriever):
    return approve_sheet(
        state, retriever=retriever, llm=LocalEchoProvider(), shield=NoopShield()
    )


def test_wifi_at_cap_is_approved():
    """$100 vs $100 cap → APPROVED (inclusive boundary, SCOPING §19.3, §20.E)."""
    result = _run(_sheet("100"), _retriever())
    assert result.decision is FinanceDecision.APPROVED
    assert result.line_item_verdicts[0].status is LineItemStatus.POLICY_PASS
    assert result.line_item_verdicts[0].numeric_cross_checked is True


def test_wifi_above_cap_is_rejected():
    """$100.01 vs $100 cap → REJECTED_WITH_COMMENTS, whole sheet (SCOPING §6.3, §20.E)."""
    result = _run(_sheet("100.01"), _retriever())
    assert result.decision is FinanceDecision.REJECTED_WITH_COMMENTS
    assert result.line_item_verdicts[0].status is LineItemStatus.POLICY_FAIL
    assert result.line_item_verdicts[0].cited_clause == WIFI_CLAUSE
    assert result.comments  # cited reject reason present


def test_missing_policy_routes_to_human():
    """Agency with no policy → ROUTED_TO_HUMAN, never auto-approve (SCOPING §8)."""
    retriever = InMemoryRetriever({})  # no clauses for any agency
    result = _run(_sheet("50"), retriever)
    assert result.decision is FinanceDecision.ROUTED_TO_HUMAN
    assert result.confidence == 0.0


def test_pinned_versions_for_audit():
    """Result pins policy + model version for reproducibility (SCOPING §6.4, §9.2)."""
    result = _run(_sheet("100"), _retriever())
    assert result.policy_version == "crispin-2026.06"
    assert result.model_version == LocalEchoProvider().model_version


def test_agency_trimming_never_leaks_other_agency():
    """A sheet for an agency with no policy must not see another agency's clauses (§7)."""
    retriever = InMemoryRetriever(
        {"skdk": [WIFI_CLAUSE]}, policy_version="skdk-1"
    )
    result = _run(_sheet("100"), retriever)  # sheet is agency 'crispin'
    assert result.decision is FinanceDecision.ROUTED_TO_HUMAN

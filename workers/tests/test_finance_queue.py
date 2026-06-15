"""Finance-approval queue consumer wiring (SCOPING §6.3, §8), offline.

No Azure / no API: `handle_sheet` runs the approver and the decision-persistence callback
is a no-op when `api_base_url` is empty. Also checks the cited-clause projection that feeds
the API `LlmDecisionRequest`.
"""

from __future__ import annotations

import json

from expense_core.llm.providers import LocalEchoProvider
from expense_core.schemas.enums import FinanceDecision, LineItemStatus

from workers.config import Settings
from workers.consumers.finance_queue import _cited_clauses, handle_sheet, post_decision
from workers.finance_approver.state import LineItemVerdict, SheetResult
from workers.guardrails.prompt_shield import NoopShield
from workers.rag.retriever import InMemoryRetriever

WIFI_CLAUSE = "Wi-Fi / internet reimbursement is capped at $100; any amount above is rejected."


def _retriever() -> InMemoryRetriever:
    return InMemoryRetriever({"crispin": [WIFI_CLAUSE]}, policy_version="crispin-2026.06")


def _body(amount: str) -> str:
    return json.dumps(
        {
            "sheet_id": "S1",
            "agency_id": "crispin",
            "line_items": [
                {
                    "id": "li-1",
                    "category": "Software / Subscriptions",
                    "amount": amount,
                    "merchant": "Comcast",
                    "description": "Home Wi-Fi internet",
                }
            ],
        }
    )


def test_handle_sheet_offline_runs_and_persists_noop():
    # Offline (no api_base_url): post_decision is a no-op, so handle_sheet must not raise.
    result = handle_sheet(
        _body("100.01"),
        retriever=_retriever(),
        llm=LocalEchoProvider(),
        shield=NoopShield(),
        settings=Settings(api_base_url=""),
    )
    assert result.decision is FinanceDecision.REJECTED_WITH_COMMENTS


def test_post_decision_offline_noop():
    result = SheetResult(sheet_id="S1", agency_id="crispin", decision=FinanceDecision.APPROVED)
    # No api_base_url → returns without attempting any HTTP call.
    post_decision(result, Settings(api_base_url=""))


def test_cited_clauses_dedupes_in_order():
    result = SheetResult(
        sheet_id="S1",
        agency_id="crispin",
        decision=FinanceDecision.REJECTED_WITH_COMMENTS,
        line_item_verdicts=[
            LineItemVerdict(line_item_id="li-1", status=LineItemStatus.POLICY_FAIL,
                            cited_clause=WIFI_CLAUSE),
            LineItemVerdict(line_item_id="li-2", status=LineItemStatus.POLICY_FAIL,
                            cited_clause=WIFI_CLAUSE),
            LineItemVerdict(line_item_id="li-3", status=LineItemStatus.POLICY_UNCERTAIN,
                            cited_clause=None),
        ],
    )
    assert _cited_clauses(result) == [WIFI_CLAUSE]

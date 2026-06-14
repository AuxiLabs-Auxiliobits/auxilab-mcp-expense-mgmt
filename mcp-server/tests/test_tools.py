"""MCP tool wrappers return well-formed dicts (SCOPING §20.E).

Import-safe without Azure: every tool defaults to expense_core's offline
LocalEchoProvider, so these run with no credentials. `@mcp.tool()` returns the
original function unchanged, so we call the handlers directly and assert each yields a
JSON-safe dict matching the engine contract.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from expense_core.tools.duplicate_detector import CandidateLineItem, HistoricalLineItem
from expense_core.tools.report_summariser import SummaryLineItem

from expense_mcp import server


# §20.E row 1 — meal over per-meal limit → policy fails.
def test_policy_checker_meal_over_limit():
    out = server.policy_checker(
        employee_id="e1",
        amount=Decimal("187"),
        merchant="Steakhouse",
        expense_date=date(2026, 6, 1),
        category="Meals & Entertainment",
        has_receipt=True,
        today=date(2026, 6, 14),
    )
    assert isinstance(out, dict)
    assert out["status"] == "fail"
    assert any(v["code"] == "OVER_MEAL_LIMIT" for v in out["violations"])
    assert out["recommended_action"] == "return_to_employee"


# Clean item passes intake.
def test_policy_checker_pass():
    out = server.policy_checker(
        employee_id="e1",
        amount=Decimal("50"),
        merchant="Cafe",
        expense_date=date(2026, 6, 1),
        has_receipt=True,
        today=date(2026, 6, 14),
    )
    assert out["status"] == "pass"
    assert out["violations"] == []
    assert out["recommended_action"] == "accept"


# §20.E row 2 — Marriott reconciliation passes (2×210 + 42 = 462).
def test_receipt_parser_marriott_reconciles():
    out = server.receipt_parser("Marriott Hotels, 2 nights @ $210, Tax $42, Total $462")
    assert isinstance(out, dict)
    assert out["merchant"].startswith("Marriott")
    assert out["total"] == "462"
    assert out["tax"] == "42"
    assert out["reconciles"] is True
    assert out["delta"] == "0"


# §20.E row 3 — Uber airport transfer → Travel - Ground.
def test_category_classifier_uber_ground():
    out = server.category_classifier("Airport transfer", "Uber")
    assert isinstance(out, dict)
    assert out["category"] == "Travel - Ground"
    assert out["confidence"] >= 0.9


# §6.1 — exact duplicate key → HIGH risk.
def test_duplicate_detector_exact_key_high():
    dt = datetime(2026, 6, 1, 12, 0)
    candidate = CandidateLineItem(employee_id="e1", receipt_datetime=dt, total=Decimal("120"))
    history = [
        HistoricalLineItem(
            line_item_id="li1", employee_id="e1", receipt_datetime=dt, total=Decimal("120")
        )
    ]
    out = server.duplicate_detector(candidate, history, near_match_days=3)
    assert isinstance(out, dict)
    assert out["risk"] == "high"
    assert out["risk_score"] == 1.0
    assert out["matches"][0]["reason"] == "EXACT_KEY"


# No history → no duplicate signal.
def test_duplicate_detector_none():
    candidate = CandidateLineItem(
        employee_id="e1", receipt_datetime=datetime(2026, 6, 1, 12, 0), total=Decimal("120")
    )
    out = server.duplicate_detector(candidate, [])
    assert out["risk"] == "none"
    assert out["matches"] == []


# Summariser aggregation + compliance rate (one of two items non-compliant).
def test_report_summariser_aggregation():
    items = [
        SummaryLineItem(category="Travel - Hotel", amount=Decimal("462"), is_compliant=True),
        SummaryLineItem(
            category="Meals & Entertainment", amount=Decimal("187"), is_compliant=False
        ),
    ]
    out = server.report_summariser(items)
    assert isinstance(out, dict)
    assert out["violation_count"] == 1
    assert out["total_at_risk"] == "187"
    assert out["compliance_rate_pct"] == 50.0
    assert out["total_by_category"]["Travel - Hotel"] == "462"
    assert isinstance(out["narrative"], str) and out["narrative"]


# All five tools are registered on the FastMCP instance.
def test_five_tools_registered():
    assert server.mcp.name == "auxilab-mcp-expense-mgmt"
    for fn in (
        server.policy_checker,
        server.receipt_parser,
        server.category_classifier,
        server.duplicate_detector,
        server.report_summariser,
    ):
        assert callable(fn)

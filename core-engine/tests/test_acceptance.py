"""Acceptance checks straight from SCOPING §20.E — these are the contract."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from expense_core.policy import load_baseline_policy
from expense_core.schemas.enums import Category, DuplicateRisk, PolicyCheckStatus
from expense_core.schemas.tools import LineItemInput
from expense_core.tools import (
    check_policy,
    classify_category,
    detect_duplicates,
    parse_receipt,
    summarise_report,
)
from expense_core.tools.duplicate_detector import CandidateLineItem, HistoricalLineItem
from expense_core.tools.report_summariser import SummaryLineItem

POLICY = load_baseline_policy()
TODAY = date(2026, 6, 14)


def _item(**kw) -> LineItemInput:
    base = dict(
        employee_id="e1",
        amount=Decimal("50"),
        merchant="Test",
        expense_date=date(2026, 6, 1),
        has_receipt=True,
    )
    base.update(kw)
    return LineItemInput(**base)


# §20.E row 1 — meal over per-meal limit
def test_meal_over_limit_rejected():
    res = check_policy(
        _item(category=Category.MEALS_ENTERTAINMENT, amount=Decimal("187")), POLICY, today=TODAY
    )
    assert res.status is PolicyCheckStatus.FAIL
    assert any(v.code == "OVER_MEAL_LIMIT" for v in res.violations)


# §19.3 — inclusive cap boundary ($100 passes, $100.01 fails) via baseline meal cap analogue
def test_cap_boundary_inclusive():
    assert POLICY.exceeds_cap(Decimal("75"), Decimal("75")) is False
    assert POLICY.exceeds_cap(Decimal("75.01"), Decimal("75")) is True


# §20.E row 2 — Marriott reconciliation passes (2×210 + 42 = 462)
def test_receipt_reconciles():
    res = parse_receipt("Marriott Hotels, 2 nights @ $210, Tax $42, Total $462")
    assert res.merchant.startswith("Marriott")
    assert res.total == Decimal("462")
    assert res.tax == Decimal("42")
    assert res.reconciles is True
    assert res.delta == Decimal("0")


# §20.E row 3 — Uber airport transfer → Travel - Ground
def test_classify_uber_ground():
    res = classify_category("Airport transfer", "Uber")
    assert res.category is Category.TRAVEL_GROUND
    assert res.confidence >= 0.9


# §6.1 — exact duplicate key → HIGH risk
def test_exact_duplicate_blocked():
    dt = datetime(2026, 6, 1, 12, 0)
    cand = CandidateLineItem(employee_id="e1", receipt_datetime=dt, total=Decimal("120"))
    hist = [HistoricalLineItem(line_item_id="li1", employee_id="e1", receipt_datetime=dt, total=Decimal("120"))]
    res = detect_duplicates(cand, hist, near_match_days=POLICY.duplicate_near_match_days)
    assert res.risk is DuplicateRisk.HIGH
    assert res.matches[0].reason == "EXACT_KEY"


# §6.1 — near match within window → MEDIUM
def test_near_match_window():
    cand = CandidateLineItem(employee_id="e1", receipt_datetime=datetime(2026, 6, 4, 9, 0), total=Decimal("120"))
    hist = [HistoricalLineItem(line_item_id="li1", employee_id="e1", receipt_datetime=datetime(2026, 6, 1, 9, 0), total=Decimal("120"))]
    res = detect_duplicates(cand, hist, near_match_days=3)
    assert res.risk is DuplicateRisk.MEDIUM


# Receipt required over threshold when missing
def test_receipt_required_over_threshold():
    res = check_policy(_item(amount=Decimal("200"), has_receipt=False), POLICY, today=TODAY)
    assert res.status is PolicyCheckStatus.FAIL
    assert any(v.code == "RECEIPT_REQUIRED" for v in res.violations)


# Submission after month-end of incurred month is rejected (§19.6)
def test_submission_window_missed():
    res = check_policy(_item(expense_date=date(2026, 5, 1)), POLICY, today=date(2026, 6, 14))
    assert any(v.code == "SUBMISSION_WINDOW_MISSED" for v in res.violations)


# Summariser aggregation + compliance rate
def test_summary_aggregation():
    items = [
        SummaryLineItem(category=Category.TRAVEL_HOTEL, amount=Decimal("462"), is_compliant=True),
        SummaryLineItem(category=Category.MEALS_ENTERTAINMENT, amount=Decimal("187"), is_compliant=False),
    ]
    res = summarise_report(items)
    assert res.violation_count == 1
    assert res.total_at_risk == Decimal("187")
    assert res.compliance_rate_pct == 50.0
    assert res.total_by_category[Category.TRAVEL_HOTEL] == Decimal("462")

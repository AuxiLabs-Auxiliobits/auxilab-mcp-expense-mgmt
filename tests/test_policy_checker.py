"""Policy Checker — one test per rule, plus the interactions between them."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from compliance_tools import BaselinePolicy, CapBoundary, check_policy
from compliance_tools.schemas import Category, LineItemInput, PolicyCheckStatus, RecommendedAction

from .conftest import TODAY


def item(**overrides) -> LineItemInput:
    base = {
        "employee_id": "emp-001",
        "category": Category.MEALS_ENTERTAINMENT,
        "amount": Decimal("40.00"),
        "merchant": "Noodle House",
        "expense_date": date(2026, 6, 1),
        "has_receipt": True,
    }
    base.update(overrides)
    return LineItemInput(**base)


def codes(result) -> set[str]:
    return {v.code for v in result.violations}


# --------------------------------------------------------------------------- #
# Clean path
# --------------------------------------------------------------------------- #
def test_compliant_item_passes(strict_policy):
    result = check_policy(item(), strict_policy, today=TODAY)
    assert result.status is PolicyCheckStatus.PASS
    assert result.violations == []
    assert result.recommended_action is RecommendedAction.ACCEPT


# --------------------------------------------------------------------------- #
# Category rules
# --------------------------------------------------------------------------- #
def test_prohibited_category_is_flagged(strict_policy):
    result = check_policy(
        item(category=Category.CLIENT_ENTERTAINMENT, amount=Decimal("200")),
        strict_policy,
        today=TODAY,
    )
    assert "PROHIBITED_CATEGORY" in codes(result)
    assert result.status is PolicyCheckStatus.FAIL


def test_over_category_limit_is_flagged(strict_policy):
    result = check_policy(item(amount=Decimal("187")), strict_policy, today=TODAY)
    assert "OVER_CATEGORY_LIMIT" in codes(result)


def test_uncapped_category_allows_any_amount(strict_policy):
    # Only Meals is capped in strict_policy, so a large Other expense clears.
    result = check_policy(
        item(category=Category.OTHER, amount=Decimal("9999")), strict_policy, today=TODAY
    )
    assert "OVER_CATEGORY_LIMIT" not in codes(result)


def test_missing_category_skips_category_rules(strict_policy):
    result = check_policy(item(category=None, amount=Decimal("9999")), strict_policy, today=TODAY)
    assert "OVER_CATEGORY_LIMIT" not in codes(result)
    assert "PROHIBITED_CATEGORY" not in codes(result)


# --------------------------------------------------------------------------- #
# Cap boundary
# --------------------------------------------------------------------------- #
def test_inclusive_boundary_allows_amount_equal_to_cap(strict_policy):
    result = check_policy(item(amount=Decimal("75")), strict_policy, today=TODAY)
    assert "OVER_CATEGORY_LIMIT" not in codes(result)


def test_inclusive_boundary_rejects_a_cent_over(strict_policy):
    result = check_policy(item(amount=Decimal("75.01")), strict_policy, today=TODAY)
    assert "OVER_CATEGORY_LIMIT" in codes(result)


def test_exclusive_boundary_rejects_amount_equal_to_cap():
    policy = BaselinePolicy(
        category_limits={Category.MEALS_ENTERTAINMENT: Decimal("75")},
        cap_boundary=CapBoundary.EXCLUSIVE,
        receipt_required_over=None,
        max_expense_age_days=None,
    )
    result = check_policy(item(amount=Decimal("75")), policy, today=TODAY)
    assert "OVER_CATEGORY_LIMIT" in codes(result)


@pytest.mark.parametrize(
    ("boundary", "amount", "expected"),
    [
        (CapBoundary.INCLUSIVE, Decimal("74.99"), False),
        (CapBoundary.INCLUSIVE, Decimal("75"), False),
        (CapBoundary.INCLUSIVE, Decimal("75.01"), True),
        (CapBoundary.EXCLUSIVE, Decimal("74.99"), False),
        (CapBoundary.EXCLUSIVE, Decimal("75"), True),
    ],
)
def test_exceeds_cap_helper(boundary, amount, expected):
    policy = BaselinePolicy(cap_boundary=boundary)
    assert policy.exceeds_cap(amount, Decimal("75")) is expected


# --------------------------------------------------------------------------- #
# Date rules
# --------------------------------------------------------------------------- #
def test_future_date_is_flagged(strict_policy):
    result = check_policy(item(expense_date=TODAY + timedelta(days=1)), strict_policy, today=TODAY)
    assert "FUTURE_DATE" in codes(result)


def test_expense_older_than_claim_window_is_flagged(strict_policy):
    result = check_policy(
        item(expense_date=TODAY - timedelta(days=200)), strict_policy, today=TODAY
    )
    assert "EXPENSE_TOO_OLD" in codes(result)


def test_expense_inside_claim_window_passes(strict_policy):
    result = check_policy(item(expense_date=TODAY - timedelta(days=89)), strict_policy, today=TODAY)
    assert "EXPENSE_TOO_OLD" not in codes(result)


def test_claim_window_can_be_disabled():
    policy = BaselinePolicy(max_expense_age_days=None, receipt_required_over=None)
    result = check_policy(item(expense_date=date(2001, 1, 1), category=None), policy, today=TODAY)
    assert result.status is PolicyCheckStatus.PASS


def test_future_date_suppresses_the_too_old_check(strict_policy):
    # A future date is one problem, not two — it should never also report as too old.
    result = check_policy(
        item(expense_date=TODAY + timedelta(days=400)), strict_policy, today=TODAY
    )
    assert codes(result) == {"FUTURE_DATE"}


# --------------------------------------------------------------------------- #
# Receipt rules
# --------------------------------------------------------------------------- #
def test_receipt_required_over_threshold(strict_policy):
    result = check_policy(item(amount=Decimal("60"), has_receipt=False), strict_policy, today=TODAY)
    assert "RECEIPT_REQUIRED" in codes(result)


def test_no_receipt_needed_under_threshold(strict_policy):
    result = check_policy(item(amount=Decimal("20"), has_receipt=False), strict_policy, today=TODAY)
    assert "RECEIPT_REQUIRED" not in codes(result)
    assert result.status is PolicyCheckStatus.PASS


def test_missing_receipt_alone_asks_for_a_receipt(strict_policy):
    """A fixable omission gets the narrower action, not a full return."""
    result = check_policy(item(amount=Decimal("60"), has_receipt=False), strict_policy, today=TODAY)
    assert result.recommended_action is RecommendedAction.REQUEST_RECEIPT


def test_missing_receipt_with_another_violation_returns_to_employee(strict_policy):
    result = check_policy(
        item(amount=Decimal("500"), has_receipt=False), strict_policy, today=TODAY
    )
    assert codes(result) == {"RECEIPT_REQUIRED", "OVER_CATEGORY_LIMIT"}
    assert result.recommended_action is RecommendedAction.RETURN_TO_EMPLOYEE


def test_amount_mismatch_against_receipt(strict_policy):
    result = check_policy(
        item(amount=Decimal("50.00"), receipt_total=Decimal("47.50")),
        strict_policy,
        today=TODAY,
    )
    assert "AMOUNT_MISMATCH" in codes(result)


def test_matching_receipt_total_passes(strict_policy):
    result = check_policy(
        item(amount=Decimal("50.00"), receipt_total=Decimal("50.00")),
        strict_policy,
        today=TODAY,
    )
    assert result.status is PolicyCheckStatus.PASS


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #
def test_same_input_gives_same_verdict(strict_policy):
    """No model, no clock, no randomness — repeated calls must be identical."""
    first = check_policy(item(amount=Decimal("187")), strict_policy, today=TODAY)
    second = check_policy(item(amount=Decimal("187")), strict_policy, today=TODAY)
    assert first == second

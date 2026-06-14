"""Tool 1 — Policy Checker. Pure deterministic rules, NO LLM (SCOPING §4, §6.1).

Intake-level checks: receipt threshold, per-category caps, prohibited categories,
submission window (month-end of incurred month), basic data sanity. Returns a
structured verdict; the API/worker decides what to do with `recommended_action`.
"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from expense_core.policy.baseline import BaselinePolicy
from expense_core.schemas.enums import Category, PolicyCheckStatus, RecommendedAction
from expense_core.schemas.tools import LineItemInput, PolicyResult, PolicyViolation


def _month_end(d: date) -> date:
    last = calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, last)


def check_policy(
    item: LineItemInput,
    policy: BaselinePolicy,
    *,
    today: date | None = None,
) -> PolicyResult:
    """Validate a single line item against the baseline ruleset.

    `today` is injectable so the submission-window check is testable/deterministic.
    """
    today = today or date.today()
    violations: list[PolicyViolation] = []

    # --- Data sanity ---------------------------------------------------------
    if item.amount <= Decimal("0"):
        violations.append(
            PolicyViolation(code="NON_POSITIVE_AMOUNT", message="Amount must be > 0", field="amount")
        )
    if item.expense_date > today:
        violations.append(
            PolicyViolation(
                code="FUTURE_DATE", message="Expense date is in the future", field="expense_date"
            )
        )

    # --- Submission window: before month-end of the incurred month (SCOPING §19.6)
    if today > _month_end(item.expense_date):
        violations.append(
            PolicyViolation(
                code="SUBMISSION_WINDOW_MISSED",
                message="Submitted after the end of the month in which the expense was incurred",
                field="expense_date",
            )
        )

    # --- Receipt required over threshold ------------------------------------
    if item.amount > policy.receipt_required_threshold and not item.has_receipt:
        violations.append(
            PolicyViolation(
                code="RECEIPT_REQUIRED",
                message=f"Receipt required for amounts over {policy.receipt_required_threshold}",
                field="has_receipt",
            )
        )

    # --- Category rules ------------------------------------------------------
    if item.category is not None:
        if item.category in policy.prohibited_categories:
            violations.append(
                PolicyViolation(
                    code="PROHIBITED_CATEGORY",
                    message=f"Category '{item.category}' is prohibited",
                    field="category",
                )
            )
        _check_category_cap(item, policy, violations)

    # --- Entered amount vs parsed receipt total -----------------------------
    if item.receipt_total is not None and item.receipt_total != item.amount:
        violations.append(
            PolicyViolation(
                code="AMOUNT_MISMATCH",
                message="Entered amount does not match parsed receipt total",
                field="amount",
            )
        )

    return _result(violations)


def _check_category_cap(
    item: LineItemInput, policy: BaselinePolicy, violations: list[PolicyViolation]
) -> None:
    if item.category is Category.MEALS_ENTERTAINMENT and policy.exceeds_cap(
        item.amount, policy.per_meal_limit
    ):
        violations.append(
            PolicyViolation(
                code="OVER_MEAL_LIMIT",
                message=f"Meal exceeds per-meal limit of {policy.per_meal_limit}",
                field="amount",
            )
        )
    if item.category is Category.TRAVEL_HOTEL and policy.exceeds_cap(
        item.amount, policy.per_hotel_night_limit
    ):
        violations.append(
            PolicyViolation(
                code="OVER_HOTEL_LIMIT",
                message=f"Hotel exceeds per-night limit of {policy.per_hotel_night_limit}",
                field="amount",
            )
        )


def _result(violations: list[PolicyViolation]) -> PolicyResult:
    if not violations:
        return PolicyResult(
            status=PolicyCheckStatus.PASS,
            violations=[],
            recommended_action=RecommendedAction.ACCEPT,
        )
    only_missing_receipt = all(v.code == "RECEIPT_REQUIRED" for v in violations)
    action = (
        RecommendedAction.REQUEST_RECEIPT
        if only_missing_receipt
        else RecommendedAction.RETURN_TO_EMPLOYEE
    )
    return PolicyResult(
        status=PolicyCheckStatus.FAIL, violations=violations, recommended_action=action
    )

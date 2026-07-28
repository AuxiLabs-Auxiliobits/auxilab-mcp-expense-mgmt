"""Tool 1 — Policy Checker. Pure deterministic rules, NO LLM (SCOPING §4, §6.1).

Intake-level checks: prohibited categories, basic data sanity, and entered-vs-receipt
amount match. Returns a structured verdict; the API/worker decides what to do with
`recommended_action`.

Note: per-category caps, the receipt-over-threshold rule, and the submission-window
(month-end) rule were intentionally removed — a receipt is mandatory on *every* line item
(enforced at submission), caps aren't part of the intake gate, and expense periods are
chosen from a rolling 12-month window (so back-dated months are valid).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from expense_core.policy.baseline import BaselinePolicy
from expense_core.schemas.enums import PolicyCheckStatus, RecommendedAction
from expense_core.schemas.tools import LineItemInput, PolicyResult, PolicyViolation


def check_policy(
    item: LineItemInput,
    policy: BaselinePolicy,
    *,
    today: date | None = None,
) -> PolicyResult:
    """Validate a single line item against the baseline ruleset.

    `today` is injectable so the future-date check is testable/deterministic.
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

    # --- Category rules ------------------------------------------------------
    if item.category is not None and item.category in policy.prohibited_categories:
        violations.append(
            PolicyViolation(
                code="PROHIBITED_CATEGORY",
                message=f"Category '{item.category}' is prohibited",
                field="category",
            )
        )

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


def _result(violations: list[PolicyViolation]) -> PolicyResult:
    if not violations:
        return PolicyResult(
            status=PolicyCheckStatus.PASS,
            violations=[],
            recommended_action=RecommendedAction.ACCEPT,
        )
    return PolicyResult(
        status=PolicyCheckStatus.FAIL,
        violations=violations,
        recommended_action=RecommendedAction.RETURN_TO_EMPLOYEE,
    )

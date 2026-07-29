"""Tool 1 — Policy Checker.

Validates a single expense line item against a :class:`~tools.policy.BaselinePolicy`.
Entirely deterministic: same input, same policy, same verdict, every time. No model is
consulted, which is deliberate — spend rules are the part of a compliance system that
must be auditable and reproducible.

Checks performed:

===========================  ======================================================
Code                         Fires when
===========================  ======================================================
``NON_POSITIVE_AMOUNT``      amount <= 0
``FUTURE_DATE``              expense_date is after today
``EXPENSE_TOO_OLD``          expense_date predates the policy's claim window
``PROHIBITED_CATEGORY``      category is on the policy's prohibited list
``OVER_CATEGORY_LIMIT``      amount exceeds that category's cap
``RECEIPT_REQUIRED``         amount is over the receipt threshold and none attached
``AMOUNT_MISMATCH``          entered amount != the parsed receipt total
===========================  ======================================================
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from compliance_tools.policy import BaselinePolicy
from compliance_tools.schemas import (
    LineItemInput,
    PolicyCheckStatus,
    PolicyResult,
    PolicyViolation,
    RecommendedAction,
)


def check_policy(
    item: LineItemInput,
    policy: BaselinePolicy,
    *,
    today: date | None = None,
) -> PolicyResult:
    """Validate one line item. ``today`` is injectable to keep date rules testable."""
    today = today or date.today()
    violations: list[PolicyViolation] = []

    # --- Data sanity ---------------------------------------------------------
    if item.amount <= Decimal("0"):
        violations.append(
            PolicyViolation(
                code="NON_POSITIVE_AMOUNT", message="Amount must be greater than 0", field="amount"
            )
        )

    if item.expense_date > today:
        violations.append(
            PolicyViolation(
                code="FUTURE_DATE", message="Expense date is in the future", field="expense_date"
            )
        )
    elif policy.max_expense_age_days is not None:
        cutoff = today - timedelta(days=policy.max_expense_age_days)
        if item.expense_date < cutoff:
            violations.append(
                PolicyViolation(
                    code="EXPENSE_TOO_OLD",
                    message=(
                        f"Expense is older than the {policy.max_expense_age_days}-day "
                        f"claim window (on or before {cutoff.isoformat()})"
                    ),
                    field="expense_date",
                )
            )

    # --- Category rules ------------------------------------------------------
    if item.category is not None and item.category in policy.prohibited_categories:
        violations.append(
            PolicyViolation(
                code="PROHIBITED_CATEGORY",
                message=f"Category '{item.category.value}' is not reimbursable",
                field="category",
            )
        )

    cap = policy.limit_for(item.category)
    if cap is not None and policy.exceeds_cap(item.amount, cap):
        violations.append(
            PolicyViolation(
                code="OVER_CATEGORY_LIMIT",
                message=(
                    f"{item.amount} {item.currency} exceeds the "
                    f"{cap} {policy.currency} limit for '{item.category.value}'"
                ),
                field="amount",
            )
        )

    # --- Receipt rules -------------------------------------------------------
    needs_receipt = policy.receipt_required_over is not None and policy.exceeds_cap(
        item.amount, policy.receipt_required_over
    )
    if needs_receipt and not item.has_receipt:
        violations.append(
            PolicyViolation(
                code="RECEIPT_REQUIRED",
                message=(
                    f"A receipt is required for expenses over "
                    f"{policy.receipt_required_over} {policy.currency}"
                ),
                field="has_receipt",
            )
        )

    if item.receipt_total is not None and item.receipt_total != item.amount:
        violations.append(
            PolicyViolation(
                code="AMOUNT_MISMATCH",
                message=(
                    f"Entered amount {item.amount} does not match the parsed "
                    f"receipt total {item.receipt_total}"
                ),
                field="amount",
            )
        )

    return _verdict(violations)


def _verdict(violations: list[PolicyViolation]) -> PolicyResult:
    """Map violations to a status and the action a caller should take."""
    if not violations:
        return PolicyResult(
            status=PolicyCheckStatus.PASS,
            violations=[],
            recommended_action=RecommendedAction.ACCEPT,
        )

    # A missing receipt is the one failure the employee can fix without re-entering
    # anything, so it gets its own, narrower action.
    codes = {v.code for v in violations}
    action = (
        RecommendedAction.REQUEST_RECEIPT
        if codes == {"RECEIPT_REQUIRED"}
        else RecommendedAction.RETURN_TO_EMPLOYEE
    )
    return PolicyResult(
        status=PolicyCheckStatus.FAIL, violations=violations, recommended_action=action
    )

"""Company travel policy engine — loads rules and evaluates compliance."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

POLICY_PATH = Path(__file__).resolve().parent.parent / "database" / "company_policy.json"


def load_policy(path: Path | None = None) -> dict[str, Any]:
    """Load company policy from JSON file."""
    policy_file = path or POLICY_PATH
    with open(policy_file, encoding="utf-8") as f:
        return json.load(f)


def get_city_limits(destination: str, policy: dict[str, Any] | None = None) -> dict[str, float]:
    """Return daily limits for a destination, applying city overrides if present."""
    policy = policy or load_policy()
    base = dict(policy["daily_limits"])
    base.update(policy.get("per_trip_limits", {}))
    overrides = policy.get("city_overrides", {})
    for city, limits in overrides.items():
        if city.lower() in destination.lower():
            base.update(limits)
            break
    return {k: float(v) for k, v in base.items()}


def get_purpose_multiplier(purpose: str, policy: dict[str, Any] | None = None) -> float:
    """Return budget multiplier for trip purpose."""
    policy = policy or load_policy()
    multipliers = policy.get("purpose_multipliers", {})
    key = purpose.lower().replace(" ", "_")
    return float(multipliers.get(key, 1.0))


def compute_budget_breakdown(
    destination: str,
    duration_days: int,
    purpose: str,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute per-category budget breakdown for a trip."""
    policy = policy or load_policy()
    limits = get_city_limits(destination, policy)
    multiplier = get_purpose_multiplier(purpose, policy)
    per_trip = set(policy.get("per_trip_limits", {}))

    breakdown: dict[str, float] = {}
    for category, limit in limits.items():
        days = 1 if category in per_trip else duration_days
        breakdown[category] = round(limit * days * multiplier, 2)

    total = round(sum(breakdown.values()), 2)
    return {
        "destination": destination,
        "duration_days": duration_days,
        "purpose": purpose,
        "currency": policy.get("currency", "INR"),
        "daily_limits": limits,
        "purpose_multiplier": multiplier,
        "breakdown": breakdown,
        "total_budget": total,
    }


def check_compliance(
    trip_plan: dict[str, Any],
    employee_id: str,
    policy: dict[str, Any] | None = None,
    *,
    for_pre_approval: bool = False,
) -> dict[str, Any]:
    """Evaluate a trip plan against company policy."""
    policy = policy or load_policy()
    violations: list[str] = []

    duration = int(trip_plan.get("duration_days", 0))
    max_duration = policy["trip_limits"]["max_duration_days"]
    if duration > max_duration:
        violations.append(
            f"Trip duration {duration} days exceeds maximum allowed {max_duration} days"
        )
    if duration <= 0:
        violations.append("Trip duration must be at least 1 day")

    destination = trip_plan.get("destination", "")
    purpose = trip_plan.get("purpose", "")
    expected = compute_budget_breakdown(destination, duration, purpose, policy)

    submitted_breakdown = trip_plan.get("breakdown") or trip_plan.get("budget_breakdown", {})
    if isinstance(submitted_breakdown, str):
        submitted_breakdown = json.loads(submitted_breakdown)

    for category, limit in expected["breakdown"].items():
        submitted = float(submitted_breakdown.get(category, 0))
        max_allowed = limit * policy["trip_limits"]["max_total_budget_multiplier"]
        if submitted > max_allowed:
            violations.append(
                f"{category.title()} budget ₹{submitted:.2f} exceeds limit ₹{max_allowed:.2f}"
            )

    if not for_pre_approval:
        total = sum(float(v) for v in submitted_breakdown.values()) if submitted_breakdown else expected["total_budget"]
        pre_approval_threshold = policy["trip_limits"]["require_pre_approval_above"]
        if total > pre_approval_threshold and not trip_plan.get("approval_token"):
            violations.append(
                f"Total budget ₹{total:.2f} requires pre-approval (threshold: ₹{pre_approval_threshold:.2f})"
            )

    prohibited = set(policy.get("prohibited_categories", []))
    for category in submitted_breakdown:
        if category.lower() in prohibited:
            violations.append(f"Category '{category}' is prohibited by company policy")

    return {
        "compliant": len(violations) == 0,
        "violations": violations,
        "employee_id": employee_id,
        "expected_budget": expected,
    }


# Default claim-level limits used when policy JSON doesn't define them.
_DEFAULT_CLAIM_LIMITS: dict[str, Any] = {
    "meal_limit": 75.0,
    "hotel_night_limit": 200.0,
    "receipt_threshold": 25.0,
    "prohibited_categories": ["alcohol", "gambling", "personal", "entertainment"],
    "category_limits": {
        "Meals & Entertainment": 75.0,
        "Travel - Hotel": 200.0,
        "Travel - Air": 1500.0,
        "Travel - Ground": 100.0,
        "Office Supplies": 150.0,
        "Software/Subscriptions": 200.0,
        "Client Entertainment": 150.0,
    },
}


def _get_claim_policy(policy: dict[str, Any]) -> dict[str, Any]:
    """Extract or build claim-level policy limits from the loaded policy JSON."""
    claim_policy = policy.get("claim_limits", {})
    merged = dict(_DEFAULT_CLAIM_LIMITS)
    merged.update(claim_policy)
    # Merge category_limits separately so partial overrides work
    if "category_limits" in claim_policy:
        merged["category_limits"] = {
            **_DEFAULT_CLAIM_LIMITS["category_limits"],
            **claim_policy["category_limits"],
        }
    return merged


def check_expense_claim(
    claim: dict[str, Any],
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Validate a single expense claim against company policy.

    Parameters
    ----------
    claim : dict with keys:
        - employee_id   (str)
        - category      (str)  — one of the 8 standard categories
        - amount        (float)
        - claim_date    (str)  — ISO format YYYY-MM-DD
        - description   (str)
        - merchant      (str)
        - has_receipt   (bool) — whether a receipt was attached

    Returns
    -------
    dict with:
        - compliant         (bool)
        - status            (str)  — "compliant" | "non-compliant"
        - violations        (list[str])
        - recommended_action (str) — "Auto-approve" | "Flag for review" | "Reject"
        - policy_references (list[str])
        - risk_level        (str)  — "low" | "medium" | "high"
    """
    policy = policy or load_policy()
    cp = _get_claim_policy(policy)

    violations: list[str] = []
    policy_references: list[str] = []

    amount = float(claim.get("amount", 0))
    category = str(claim.get("category", "")).strip()
    merchant = str(claim.get("merchant", "")).strip()
    has_receipt = bool(claim.get("has_receipt", True))
    description = str(claim.get("description", "")).strip()

    # 1. Prohibited category check
    prohibited: list[str] = cp.get("prohibited_categories", [])
    if category.lower() in [p.lower() for p in prohibited]:
        violations.append(f"Category '{category}' is prohibited by company policy.")
        policy_references.append("prohibited_categories")

    # 2. Per-category amount limit check
    category_limits: dict[str, float] = cp.get("category_limits", {})
    if category in category_limits:
        limit = category_limits[category]
        if amount > limit:
            violations.append(
                f"Amount ${amount:.2f} exceeds the {category} limit of ${limit:.2f}."
            )
            policy_references.append(f"category_limits.{category}")

    # 3. Receipt threshold check
    receipt_threshold = float(cp.get("receipt_threshold", 25.0))
    if amount >= receipt_threshold and not has_receipt:
        violations.append(
            f"Receipt required for claims of ${receipt_threshold:.2f} or more (claim: ${amount:.2f})."
        )
        policy_references.append("receipt_threshold")

    # 4. Missing or empty required fields
    if not merchant:
        violations.append("Merchant name is missing.")
        policy_references.append("required_fields")
    if not category:
        violations.append("Expense category is missing.")
        policy_references.append("required_fields")
    if amount <= 0:
        violations.append("Claim amount must be greater than zero.")
        policy_references.append("required_fields")

    # 5. Determine recommended action and risk level
    compliant = len(violations) == 0

    if compliant:
        recommended_action = "Auto-approve"
        risk_level = "low"
    elif any("prohibited" in v.lower() for v in violations):
        recommended_action = "Reject"
        risk_level = "high"
    elif len(violations) >= 2:
        recommended_action = "Reject"
        risk_level = "high"
    else:
        recommended_action = "Flag for review"
        risk_level = "medium"

    return {
        "compliant": compliant,
        "status": "compliant" if compliant else "non-compliant",
        "violations": violations,
        "recommended_action": recommended_action,
        "policy_references": list(set(policy_references)),
        "risk_level": risk_level,
        "claim_summary": {
            "merchant": merchant,
            "category": category,
            "amount": amount,
            "has_receipt": has_receipt,
        },
    }
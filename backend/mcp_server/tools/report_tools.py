"""Trip reconciliation and report generation MCP tools."""

from __future__ import annotations

import json
from typing import Any

from backend.database.db import get_db, row_to_dict, rows_to_dicts
from backend.mcp_server.policy_engine import load_policy


def reconcile_trip(
    approval_token: str,
    receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Reconcile submitted receipts against a pre-approved trip budget.

    Args:
        approval_token: Pre-approval token from pre_approve_trip.
        receipts: List of receipt dicts with merchant, amount, category, date.

    Returns:
        matched/unmatched receipts, overage per category, compliance_rate %.
    """
    with get_db() as conn:
        trip = row_to_dict(
            conn.execute(
                "SELECT * FROM trip_plans WHERE approval_token = ?",
                (approval_token,),
            ).fetchone()
        )

    if not trip:
        return {"error": f"No trip found for token: {approval_token}"}

    budget_breakdown = json.loads(trip["budget_breakdown"])
    spent_by_category: dict[str, float] = {cat: 0.0 for cat in budget_breakdown}
    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []

    for receipt in receipts:
        category = receipt.get("category", "miscellaneous")
        amount = float(receipt.get("amount", 0))
        if category in spent_by_category:
            spent_by_category[category] += amount
            matched.append({**receipt, "status": "matched", "category": category})
        else:
            unmatched.append({**receipt, "status": "unmatched", "reason": f"Unknown category: {category}"})

    overage: dict[str, float] = {}
    compliant_categories = 0
    total_categories = len(budget_breakdown)

    for category, budget in budget_breakdown.items():
        spent = round(spent_by_category.get(category, 0), 2)
        budget_f = float(budget)
        diff = round(spent - budget_f, 2)
        if diff > 0:
            overage[category] = diff
        if spent <= budget_f:
            compliant_categories += 1

    compliance_rate = round((compliant_categories / total_categories) * 100, 1) if total_categories else 100.0
    total_spent = round(sum(spent_by_category.values()), 2)
    budget_cap = float(trip["budget_cap"])

    return {
        "approval_token": approval_token,
        "trip_id": trip["id"],
        "employee_id": trip["employee_id"],
        "matched": matched,
        "unmatched": unmatched,
        "spent_by_category": {k: round(v, 2) for k, v in spent_by_category.items()},
        "budget_breakdown": budget_breakdown,
        "overage": overage,
        "total_spent": total_spent,
        "budget_cap": budget_cap,
        "budget_remaining": round(budget_cap - total_spent, 2),
        "compliance_rate": compliance_rate,
    }


def generate_trip_report(approval_token: str) -> dict[str, Any]:
    """
    Generate a comprehensive trip expense report for managers.

    Args:
        approval_token: Pre-approval token from pre_approve_trip.

    Returns:
        total by category, violation_count, total_at_risk, compliance_rate %,
        and manager_narrative.
    """
    with get_db() as conn:
        trip = row_to_dict(
            conn.execute(
                "SELECT * FROM trip_plans WHERE approval_token = ?",
                (approval_token,),
            ).fetchone()
        )
        if not trip:
            return {"error": f"No trip found for token: {approval_token}"}

        claims = rows_to_dicts(
            conn.execute(
                "SELECT * FROM expense_claims WHERE trip_plan_id = ?",
                (trip["id"],),
            ).fetchall()
        )
        receipts = rows_to_dicts(
            conn.execute(
                "SELECT * FROM receipts WHERE trip_plan_id = ?",
                (trip["id"],),
            ).fetchall()
        )
        employee = row_to_dict(
            conn.execute(
                "SELECT * FROM employees WHERE id = ?",
                (trip["employee_id"],),
            ).fetchone()
        )

    budget_breakdown = json.loads(trip["budget_breakdown"])
    policy = load_policy()
    receipt_threshold = policy.get("receipt_required_above", 25)

    totals_by_category: dict[str, float] = {cat: 0.0 for cat in budget_breakdown}
    violations: list[str] = []
    total_at_risk = 0.0

    for claim in claims:
        cat = claim.get("category", "miscellaneous")
        amount = float(claim["amount"])
        if cat in totals_by_category:
            totals_by_category[cat] += amount
        else:
            totals_by_category[cat] = amount

        if claim.get("policy_violation"):
            violations.append(f"Policy violation on claim {claim['id']}: {claim.get('description', claim['merchant'])}")

        if float(claim.get("duplicate_risk", 0)) >= 0.7:
            violations.append(f"Duplicate risk on claim {claim['id']}: {claim['merchant']} ₹{amount:.2f}")
            total_at_risk += amount

        budget_limit = float(budget_breakdown.get(cat, 0))
        if budget_limit and amount > budget_limit:
            over = amount - budget_limit
            violations.append(f"Over-budget {cat}: ₹{over:.2f} on {claim['merchant']}")
            total_at_risk += over

        if amount > receipt_threshold and not claim.get("receipt_id"):
            violations.append(f"Missing receipt for ₹{amount:.2f} at {claim['merchant']}")
            total_at_risk += amount * 0.5

    for category, budget in budget_breakdown.items():
        spent = totals_by_category.get(category, 0)
        if spent > float(budget):
            overage = spent - float(budget)
            if f"Over-budget {category}" not in " ".join(violations):
                violations.append(f"Category {category} overage: ₹{overage:.2f}")
                total_at_risk += overage

    compliant_cats = sum(
        1 for cat, budget in budget_breakdown.items()
        if totals_by_category.get(cat, 0) <= float(budget)
    )
    compliance_rate = round((compliant_cats / len(budget_breakdown)) * 100, 1) if budget_breakdown else 100.0

    emp_name = employee["name"] if employee else trip["employee_id"]
    total_spent = round(sum(totals_by_category.values()), 2)
    budget_cap = float(trip["budget_cap"])

    narrative_parts = [
        f"Trip report for {emp_name} to {trip['destination']} ({trip['duration_days']} days).",
        f"Purpose: {trip['purpose']}.",
        f"Total spent: ₹{total_spent:.2f} of ₹{budget_cap:.2f} approved budget.",
    ]

    if compliance_rate >= 90:
        narrative_parts.append("Overall compliance is excellent.")
    elif compliance_rate >= 70:
        narrative_parts.append("Compliance is acceptable with minor issues requiring review.")
    else:
        narrative_parts.append("Significant compliance issues detected — manager review required.")

    if violations:
        narrative_parts.append(f"{len(violations)} issue(s) flagged totaling ₹{total_at_risk:.2f} at risk.")
    else:
        narrative_parts.append("No policy violations or duplicate claims detected.")

    if receipts:
        narrative_parts.append(f"{len(receipts)} receipt(s) on file for {len(claims)} claim(s).")
    elif claims:
        narrative_parts.append("Warning: claims submitted without supporting receipts.")

    return {
        "approval_token": approval_token,
        "trip_id": trip["id"],
        "employee": emp_name,
        "destination": trip["destination"],
        "totals_by_category": {k: round(v, 2) for k, v in totals_by_category.items()},
        "budget_breakdown": budget_breakdown,
        "total_spent": total_spent,
        "budget_cap": budget_cap,
        "violation_count": len(violations),
        "violations": violations,
        "total_at_risk": round(total_at_risk, 2),
        "compliance_rate": compliance_rate,
        "claim_count": len(claims),
        "receipt_count": len(receipts),
        "manager_narrative": " ".join(narrative_parts),
    }

"""Trip planning and pre-approval MCP tools."""

from __future__ import annotations

import json
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

from backend.database.db import get_db
from backend.mcp_server.policy_engine import check_compliance, compute_budget_breakdown


def _ensure_employee(conn, employee_id: str) -> None:
    """Guarantee the employee row exists so the trip_plans FK insert can't fail.

    trip_plans.employee_id references employees(id) with foreign keys enforced;
    without this, pre-approving a trip for an unknown employee (e.g. an unseeded
    DB) raises IntegrityError and the trip is silently never persisted.
    """
    conn.execute(
        """
        INSERT OR IGNORE INTO employees (id, name, email, department)
        VALUES (?, ?, ?, ?)
        """,
        (employee_id, employee_id, f"{employee_id}@auxilab.io", "Unknown"),
    )


def plan_trip_budget(
    destination: str,
    duration_days: int,
    purpose: str,
) -> dict[str, Any]:
    """
    Generate a budget breakdown by category for a business trip.

    Args:
        destination: Trip destination city or region.
        duration_days: Number of days for the trip.
        purpose: Business purpose (e.g. client_meeting, conference, training).

    Returns:
        Budget breakdown with per-category amounts and total.
    """
    result = compute_budget_breakdown(destination, duration_days, purpose)
    return {
        "destination": result["destination"],
        "duration_days": result["duration_days"],
        "purpose": result["purpose"],
        "currency": result["currency"],
        "breakdown": result["breakdown"],
        "total_budget": result["total_budget"],
        "daily_limits": result["daily_limits"],
        "purpose_multiplier": result["purpose_multiplier"],
    }


def check_policy_compliance(
    trip_plan: dict[str, Any],
    employee_id: str,
) -> dict[str, Any]:
    """
    Check whether a trip plan complies with company travel policy.

    Args:
        trip_plan: Trip plan dict with destination, duration_days, purpose, breakdown.
        employee_id: Employee identifier.

    Returns:
        compliant bool and list of policy violations.
    """
    return check_compliance(trip_plan, employee_id)


def pre_approve_trip(
    trip_plan: dict[str, Any],
    employee_id: str,
) -> dict[str, Any]:
    """
    Pre-approve a trip and issue an approval token with budget cap.

    Args:
        trip_plan: Trip plan dict with destination, duration_days, purpose, breakdown.
        employee_id: Employee identifier.

    Returns:
        approval_token, budget_cap, and expiry timestamp.
    """
    compliance = check_compliance(trip_plan, employee_id, for_pre_approval=True)
    if not compliance["compliant"]:
        return {
            "approved": False,
            "approval_token": None,
            "budget_cap": None,
            "expiry": None,
            "violations": compliance["violations"],
        }

    destination = trip_plan.get("destination", "")
    duration = int(trip_plan.get("duration_days", 1))
    purpose = trip_plan.get("purpose", "client_meeting")

    breakdown = trip_plan.get("breakdown") or trip_plan.get("budget_breakdown")
    if not breakdown:
        budget = compute_budget_breakdown(destination, duration, purpose)
        breakdown = budget["breakdown"]

    if isinstance(breakdown, str):
        breakdown = json.loads(breakdown)

    budget_cap = round(sum(float(v) for v in breakdown.values()), 2)
    approval_token = f"TS-{secrets.token_hex(8).upper()}"
    expiry = (datetime.utcnow() + timedelta(days=90)).isoformat() + "Z"
    trip_id = str(uuid.uuid4())

    with get_db() as conn:
        # Ensure the FK target exists, then persist the trip in the same
        # transaction so the approval token is always backed by a saved row.
        _ensure_employee(conn, employee_id)
        conn.execute(
            """
            INSERT INTO trip_plans
                (id, employee_id, destination, duration_days, purpose,
                 budget_breakdown, approval_token, budget_cap, expiry, status,
                 compliance_checked, violations)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved', 1, ?)
            """,
            (
                trip_id,
                employee_id,
                destination,
                duration,
                purpose,
                json.dumps(breakdown),
                approval_token,
                budget_cap,
                expiry,
                json.dumps([]),
            ),
        )

    return {
        "approved": True,
        "approval_token": approval_token,
        "budget_cap": budget_cap,
        "expiry": expiry,
        "trip_id": trip_id,
        "violations": [],
    }

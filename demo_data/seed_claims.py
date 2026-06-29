"""Seed TripSense demo database with 15 synthetic expense claims.

Indian merchants, cities, and INR amounts aligned with company_policy.json
(hotel ₹5,000/night, meals ₹800/day, transport ₹2,750/trip, misc ₹400/day;
receipts required above ₹2,000).

Distribution:
  - 8 compliant claims
  - 4 policy violations
  - 2 near-duplicate pairs
  - 1 missing receipt (amount > ₹2,000 receipt threshold)
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.database.db import get_db, init_db
from backend.mcp_server.tools.trip_tools import pre_approve_trip
from backend.mcp_server.policy_engine import compute_budget_breakdown


EMPLOYEES = [
    {"id": "EMP-001", "name": "Alice Chen", "email": "alice.chen@auxilab.io", "department": "Sales", "role": "employee", "manager_id": "EMP-005"},
    {"id": "EMP-002", "name": "Bob Martinez", "email": "bob.martinez@auxilab.io", "department": "Engineering", "role": "employee", "manager_id": "EMP-005"},
    {"id": "EMP-003", "name": "Carol Williams", "email": "carol.williams@auxilab.io", "department": "Marketing", "role": "employee", "manager_id": "EMP-005"},
    {"id": "EMP-004", "name": "David Kim", "email": "david.kim@auxilab.io", "department": "Sales", "role": "employee", "manager_id": "EMP-005"},
    {"id": "EMP-005", "name": "Eve Johnson", "email": "eve.johnson@auxilab.io", "department": "Operations", "role": "manager", "manager_id": None},
]

TRIPS = [
    {"employee_id": "EMP-001", "destination": "Delhi", "duration_days": 3, "purpose": "client_meeting"},
    {"employee_id": "EMP-002", "destination": "Mumbai", "duration_days": 4, "purpose": "conference"},
    {"employee_id": "EMP-003", "destination": "Bangalore", "duration_days": 2, "purpose": "training"},
    {"employee_id": "EMP-004", "destination": "Chennai", "duration_days": 5, "purpose": "sales_visit"},
]


def seed_employees(conn) -> None:
    # Insert manager first to satisfy foreign key on manager_id
    ordered = sorted(EMPLOYEES, key=lambda e: e["manager_id"] is not None)
    for emp in ordered:
        conn.execute(
            "INSERT OR IGNORE INTO employees (id, name, email, department, role, manager_id) VALUES (?, ?, ?, ?, ?, ?)",
            (emp["id"], emp["name"], emp["email"], emp["department"], emp["role"], emp["manager_id"]),
        )


def seed_trips() -> dict[str, str]:
    """Pre-approve demo trips and return employee_id → approval_token mapping."""
    tokens: dict[str, str] = {}
    for trip in TRIPS:
        budget = compute_budget_breakdown(trip["destination"], trip["duration_days"], trip["purpose"])
        trip_plan = {
            "destination": trip["destination"],
            "duration_days": trip["duration_days"],
            "purpose": trip["purpose"],
            "breakdown": budget["breakdown"],
        }
        result = pre_approve_trip(trip_plan, trip["employee_id"])
        if result.get("approval_token"):
            tokens[trip["employee_id"]] = result["approval_token"]
    return tokens


def seed_claims(conn, trip_tokens: dict[str, str]) -> None:
    base_date = datetime(2026, 5, 10)
    trip_ids: dict[str, str] = {}
    for emp_id, token in trip_tokens.items():
        row = conn.execute("SELECT id FROM trip_plans WHERE approval_token = ?", (token,)).fetchone()
        if row:
            trip_ids[emp_id] = row[0]

    # Amounts in INR, aligned with company_policy.json limits:
    #   hotel ≤ ₹5,000/night, meals ≤ ₹800/day, transport ≤ ₹2,750/trip,
    #   misc ≤ ₹400/day, receipts required above ₹2,000.
    claims = [
        # --- 8 COMPLIANT (claims 1-8) ---
        {"id": "CLM-001", "employee_id": "EMP-001", "merchant": "Taj Palace Delhi", "amount": 4800.00, "category": "hotel", "days_offset": 0, "receipt": True, "violation": 0, "dup_risk": 0.0},
        {"id": "CLM-002", "employee_id": "EMP-001", "merchant": "Uber", "amount": 450.00, "category": "transport", "days_offset": 0, "receipt": True, "violation": 0, "dup_risk": 0.0},
        {"id": "CLM-003", "employee_id": "EMP-001", "merchant": "Zomato", "amount": 650.00, "category": "meals", "days_offset": 1, "receipt": True, "violation": 0, "dup_risk": 0.0},
        {"id": "CLM-004", "employee_id": "EMP-002", "merchant": "Lemon Tree Mumbai", "amount": 5000.00, "category": "hotel", "days_offset": 2, "receipt": True, "violation": 0, "dup_risk": 0.0},
        {"id": "CLM-005", "employee_id": "EMP-002", "merchant": "IndiGo Flight", "amount": 2500.00, "category": "transport", "days_offset": 2, "receipt": True, "violation": 0, "dup_risk": 0.0},
        {"id": "CLM-006", "employee_id": "EMP-003", "merchant": "OYO Bangalore", "amount": 3500.00, "category": "hotel", "days_offset": 4, "receipt": True, "violation": 0, "dup_risk": 0.0},
        {"id": "CLM-007", "employee_id": "EMP-003", "merchant": "Swiggy", "amount": 480.00, "category": "meals", "days_offset": 4, "receipt": True, "violation": 0, "dup_risk": 0.0},
        {"id": "CLM-008", "employee_id": "EMP-004", "merchant": "Auto Rickshaw", "amount": 150.00, "category": "transport", "days_offset": 6, "receipt": True, "violation": 0, "dup_risk": 0.0},

        # --- 4 POLICY VIOLATIONS (claims 9-12) ---
        {"id": "CLM-009", "employee_id": "EMP-002", "merchant": "Marriott Mumbai", "amount": 7500.00, "category": "hotel", "days_offset": 1, "receipt": True, "violation": 1, "dup_risk": 0.0, "desc": "Hotel ₹7,500/night exceeds ₹5,000/night limit"},
        {"id": "CLM-010", "employee_id": "EMP-001", "merchant": "Hotel Restaurant", "amount": 1200.00, "category": "meals", "days_offset": 3, "receipt": True, "violation": 1, "dup_risk": 0.0, "desc": "Meal ₹1,200 exceeds ₹800/day limit"},
        {"id": "CLM-011", "employee_id": "EMP-004", "merchant": "Entertainment Lounge", "amount": 2500.00, "category": "entertainment", "days_offset": 7, "receipt": True, "violation": 1, "dup_risk": 0.0, "desc": "Prohibited category: entertainment"},
        {"id": "CLM-012", "employee_id": "EMP-004", "merchant": "Taj Krishna Hyderabad", "amount": 7000.00, "category": "hotel", "days_offset": 8, "receipt": True, "violation": 1, "dup_risk": 0.0, "desc": "Hotel ₹7,000/night exceeds ₹5,000/night limit"},

        # --- 2 NEAR-DUPLICATES (claims 13-14, same merchant+amount within 3 days) ---
        {"id": "CLM-013", "employee_id": "EMP-003", "merchant": "Dominos", "amount": 540.00, "category": "meals", "days_offset": 3, "receipt": True, "violation": 0, "dup_risk": 0.0},
        {"id": "CLM-014", "employee_id": "EMP-003", "merchant": "Dominos", "amount": 540.00, "category": "meals", "days_offset": 4, "receipt": True, "violation": 0, "dup_risk": 0.85},

        # --- 1 MISSING RECEIPT (claim 15, amount > ₹2,000 receipt threshold) ---
        # Bulk printing/office supplies legitimately exceeds the typical misc
        # range; the high amount is what makes the missing receipt a violation.
        {"id": "CLM-015", "employee_id": "EMP-002", "merchant": "Office Supplies (Printing)", "amount": 2800.00, "category": "miscellaneous", "days_offset": 5, "receipt": False, "violation": 0, "dup_risk": 0.0, "desc": "Missing receipt for bulk printing supplies"},
    ]

    for claim in claims:
        claim_date = (base_date + timedelta(days=claim["days_offset"])).strftime("%Y-%m-%d")
        trip_id = trip_ids.get(claim["employee_id"])
        receipt_id = None

        if claim.get("receipt"):
            receipt_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO receipts (id, employee_id, trip_plan_id, merchant, receipt_date, amount, line_items, ocr_confidence, reconciliation_flag, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt_id,
                    claim["employee_id"],
                    trip_id,
                    claim["merchant"],
                    claim_date,
                    claim["amount"],
                    json.dumps([{"description": claim["merchant"], "amount": claim["amount"]}]),
                    0.92,
                    0,
                    claim["category"],
                ),
            )

        conn.execute(
            """
            INSERT INTO expense_claims
                (id, employee_id, trip_plan_id, merchant, amount, claim_date, category, status, receipt_id, description, policy_violation, duplicate_risk)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'submitted', ?, ?, ?, ?)
            """,
            (
                claim["id"],
                claim["employee_id"],
                trip_id,
                claim["merchant"],
                claim["amount"],
                claim_date,
                claim["category"],
                receipt_id,
                claim.get("desc", ""),
                claim["violation"],
                claim["dup_risk"],
            ),
        )


def main() -> None:
    print("Initializing TripSense database...")
    init_db()

    with get_db() as conn:
        conn.execute("DELETE FROM expense_claims")
        conn.execute("DELETE FROM receipts")
        conn.execute("DELETE FROM trip_plans")
        conn.execute("DELETE FROM employees")
        seed_employees(conn)

    print("Seeding demo trips...")
    trip_tokens = seed_trips()

    with get_db() as conn:
        seed_claims(conn, trip_tokens)

    print("Demo data seeded successfully!")
    print(f"  Employees: {len(EMPLOYEES)}")
    print(f"  Trips: {len(TRIPS)}")
    print(f"  Claims: 15 (8 compliant, 4 violations, 2 near-duplicates, 1 missing receipt)")
    for emp_id, token in trip_tokens.items():
        print(f"  {emp_id} -> {token}")


if __name__ == "__main__":
    main()

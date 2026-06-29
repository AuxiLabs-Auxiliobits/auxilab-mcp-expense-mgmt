"""
run_demo.py — TripSense MCP Server | Full Demo Flow
====================================================
Runs all 5 required MCP tools against the 15-claim synthetic dataset.
No external API key or frontend needed.

Usage:
    cd tripsense
    python demo_data/run_demo.py
"""

from __future__ import annotations

import sys
import os
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database.db import init_db
from backend.mcp_server.policy_engine import check_expense_claim
from backend.mcp_server.tools.receipt_tools import (
    classify_spend_category,
    detect_duplicate_claim,
    parse_receipt,
)
from backend.mcp_server.tools.report_tools import generate_trip_report

# ---------------------------------------------------------------------------
# 15-Claim Synthetic Dataset
# Mix: 8 compliant, 4 policy violations, 2 near-duplicates, 1 missing receipt
# ---------------------------------------------------------------------------
EMPLOYEE_ID = "EMP-001"

CLAIMS = [
    # --- 8 COMPLIANT CLAIMS ---
    {
        "id": "C01",
        "employee_id": EMPLOYEE_ID,
        "merchant": "Delta Airlines",
        "amount": 420.00,
        "category": "Travel - Air",
        "claim_date": "2025-06-01",
        "description": "Flight to client site NYC",
        "has_receipt": True,
        "receipt_text": "text: Delta Airlines\nDate: 06/01/2025\nFlight NYC\nTotal $420.00\nTax $38.00\nVisa Card",
    },
    {
        "id": "C02",
        "employee_id": EMPLOYEE_ID,
        "merchant": "Marriott Hotels",
        "amount": 180.00,
        "category": "Travel - Hotel",
        "claim_date": "2025-06-01",
        "description": "Hotel stay NYC 1 night",
        "has_receipt": True,
        "receipt_text": "text: Marriott Hotels\nDate: 06/01/2025\n1 night $180.00\nTax $18.00\nTotal $198.00\nCredit Card",
    },
    {
        "id": "C03",
        "employee_id": EMPLOYEE_ID,
        "merchant": "Uber",
        "amount": 32.00,
        "category": "Travel - Ground",
        "claim_date": "2025-06-01",
        "description": "Airport transfer to hotel",
        "has_receipt": True,
        "receipt_text": None,
    },
    {
        "id": "C04",
        "employee_id": EMPLOYEE_ID,
        "merchant": "Starbucks",
        "amount": 18.50,
        "category": "Meals & Entertainment",
        "claim_date": "2025-06-02",
        "description": "Team coffee meeting",
        "has_receipt": True,
        "receipt_text": None,
    },
    {
        "id": "C05",
        "employee_id": EMPLOYEE_ID,
        "merchant": "Zoom",
        "amount": 149.00,
        "category": "Software/Subscriptions",
        "claim_date": "2025-06-03",
        "description": "Zoom Pro monthly subscription",
        "has_receipt": True,
        "receipt_text": None,
    },
    {
        "id": "C06",
        "employee_id": EMPLOYEE_ID,
        "merchant": "Staples",
        "amount": 45.00,
        "category": "Office Supplies",
        "claim_date": "2025-06-04",
        "description": "Printer paper and pens",
        "has_receipt": True,
        "receipt_text": None,
    },
    {
        "id": "C07",
        "employee_id": EMPLOYEE_ID,
        "merchant": "Uber",
        "amount": 28.00,
        "category": "Travel - Ground",
        "claim_date": "2025-06-05",
        "description": "Cab to office",
        "has_receipt": True,
        "receipt_text": None,
    },
    {
        "id": "C08",
        "employee_id": EMPLOYEE_ID,
        "merchant": "IndiGo Airlines",
        "amount": 310.00,
        "category": "Travel - Air",
        "claim_date": "2025-06-06",
        "description": "Return flight",
        "has_receipt": True,
        "receipt_text": None,
    },

    # --- 4 POLICY VIOLATIONS ---
    {
        "id": "C09",
        "employee_id": EMPLOYEE_ID,
        "merchant": "Nobu Restaurant",
        "amount": 187.00,           # VIOLATION: exceeds $75 meal limit
        "category": "Meals & Entertainment",
        "claim_date": "2025-06-02",
        "description": "Client dinner",
        "has_receipt": True,
        "receipt_text": "text: Nobu Restaurant\nDate: 06/02/2025\nDinner $187.00\nTax $16.83\nTotal $203.83\nAmex",
    },
    {
        "id": "C10",
        "employee_id": EMPLOYEE_ID,
        "merchant": "Marriott Hotels",
        "amount": 380.00,           # VIOLATION: exceeds $200 hotel/night limit
        "category": "Travel - Hotel",
        "claim_date": "2025-06-03",
        "description": "Hotel NYC 2 nights",
        "has_receipt": True,
        "receipt_text": None,
    },
    {
        "id": "C11",
        "employee_id": EMPLOYEE_ID,
        "merchant": "Vegas Casino",
        "amount": 200.00,           # VIOLATION: prohibited category
        "category": "gambling",
        "claim_date": "2025-06-04",
        "description": "Team outing",
        "has_receipt": True,
        "receipt_text": None,
    },
    {
        "id": "C12",
        "employee_id": EMPLOYEE_ID,
        "merchant": "City Bar",
        "amount": 95.00,            # VIOLATION: prohibited category
        "category": "alcohol",
        "claim_date": "2025-06-05",
        "description": "Team drinks",
        "has_receipt": True,
        "receipt_text": None,
    },

    # --- 2 NEAR-DUPLICATES ---
    {
        "id": "C13",
        "employee_id": EMPLOYEE_ID,
        "merchant": "Uber",
        "amount": 32.00,            # DUPLICATE of C03 — same merchant+amount, date +2 days
        "category": "Travel - Ground",
        "claim_date": "2025-06-03",
        "description": "Airport transfer",
        "has_receipt": True,
        "receipt_text": None,
    },
    {
        "id": "C14",
        "employee_id": EMPLOYEE_ID,
        "merchant": "Starbucks",
        "amount": 18.50,            # DUPLICATE of C04 — same merchant+amount, date +1 day
        "category": "Meals & Entertainment",
        "claim_date": "2025-06-03",
        "description": "Coffee",
        "has_receipt": True,
        "receipt_text": None,
    },

    # --- 1 MISSING RECEIPT ---
    {
        "id": "C15",
        "employee_id": EMPLOYEE_ID,
        "merchant": "Hilton Hotels",
        "amount": 175.00,           # MISSING RECEIPT — above threshold
        "category": "Travel - Hotel",
        "claim_date": "2025-06-07",
        "description": "Hotel stay",
        "has_receipt": False,       # No receipt attached
        "receipt_text": None,
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _divider(title: str = "") -> None:
    line = "─" * 60
    if title:
        print(f"\n{line}")
        print(f"  {title}")
        print(line)
    else:
        print(line)


def _print_result(label: str, result: dict) -> None:
    print(f"  [{label}] {json.dumps(result, indent=4, default=str)}")


# ---------------------------------------------------------------------------
# Main Demo Flow
# ---------------------------------------------------------------------------

def run_demo() -> None:
    print("\n" + "=" * 60)
    print("  TripSense MCP — Full Demo Flow")
    print("  15-claim synthetic expense report")
    print("=" * 60)

    init_db()

    # Clear previous demo runs so duplicate detector starts fresh
    from backend.database.db import get_db
    with get_db() as conn:
        conn.execute("DELETE FROM expense_claims")
        conn.commit()

    report = {
        "total_claims": len(CLAIMS),
        "per_claim": [],
        "category_totals": {},
        "violation_count": 0,
        "total_at_risk": 0.0,
        "auto_approved": 0,
        "flagged": 0,
        "rejected": 0,
        "duplicate_flags": 0,
    }

    for claim in CLAIMS:
        _divider(f"Claim {claim['id']} — {claim['merchant']}  ${claim['amount']:.2f}")

        # STEP 1 — Spend Category Classifier
        cat_result = classify_spend_category(claim["merchant"], claim["description"])
        print(f"  🏷  Category : {cat_result['display_category']} "
              f"(confidence: {cat_result['confidence_score']})")

        # STEP 2 — Expense Policy Checker
        policy_result = check_expense_claim(claim)
        status_icon = "✅" if policy_result["compliant"] else "❌"
        print(f"  {status_icon} Policy   : {policy_result['status'].upper()} "
              f"→ {policy_result['recommended_action']}")
        if policy_result["violations"]:
            for v in policy_result["violations"]:
                print(f"             ⚠  {v}")

        # STEP 3 — Duplicate Claim Detector
        dup_result = detect_duplicate_claim(
            employee_id=claim["employee_id"],
            merchant=claim["merchant"],
            amount=claim["amount"],
            date=claim["claim_date"],
        )
        risk = dup_result["duplicate_risk_score"]
        dup_icon = "🔴" if risk >= 0.8 else ("🟡" if risk >= 0.4 else "🟢")
        print(f"  {dup_icon} Duplicate : risk={risk:.2f}  "
              f"ref={dup_result.get('matched_claim_reference') or 'None'}")

        # STEP 4 — Receipt Parser (only when receipt text provided)
        receipt_parsed = None
        if claim.get("receipt_text"):
            receipt_parsed = parse_receipt(claim["receipt_text"])
            recon = receipt_parsed.get("reconciliation_errors", [])
            recon_str = "OK" if not recon else f"ERRORS: {recon}"
            print(f"  🧾 Receipt  : merchant={receipt_parsed.get('merchant')}  "
                  f"total={receipt_parsed.get('total')}  "
                  f"tax={receipt_parsed.get('tax')}  "
                  f"reconciliation={recon_str}")
        elif not claim["has_receipt"]:
            print("  🧾 Receipt  : ⚠  MISSING — no receipt attached")

        # Accumulate report data
        action = policy_result["recommended_action"]
        category_label = cat_result["display_category"]
        report["category_totals"][category_label] = (
            report["category_totals"].get(category_label, 0.0) + claim["amount"]
        )
        if not policy_result["compliant"]:
            report["violation_count"] += 1
            report["total_at_risk"] += claim["amount"]
        if risk >= 0.8:
            report["duplicate_flags"] += 1

        if action == "Auto-approve":
            report["auto_approved"] += 1
        elif action == "Flag for review":
            report["flagged"] += 1
        else:
            report["rejected"] += 1

        report["per_claim"].append({
            "id": claim["id"],
            "merchant": claim["merchant"],
            "amount": claim["amount"],
            "category": category_label,
            "policy_status": policy_result["status"],
            "recommended_action": action,
            "duplicate_risk": risk,
        })

    # ---------------------------------------------------------------------------
    # STEP 5 — Expense Report Summariser (computed inline)
    # ---------------------------------------------------------------------------
    compliance_rate = round(
        (report["auto_approved"] / report["total_claims"]) * 100, 1
    )

    _divider("EXPENSE REPORT SUMMARY")
    print(f"\n  Employee     : {EMPLOYEE_ID}")
    print(f"  Total Claims : {report['total_claims']}")
    print(f"\n  📊 Totals by Category:")
    for cat, total in sorted(report["category_totals"].items()):
        print(f"     {cat:<30} ${total:.2f}")

    print(f"\n  Violations        : {report['violation_count']}")
    print(f"  Total At Risk     : ${report['total_at_risk']:.2f}")
    print(f"  Compliance Rate   : {compliance_rate}%")
    print(f"  Duplicate Flags   : {report['duplicate_flags']}")
    print(f"\n  Recommendations:")
    print(f"     ✅ Auto-approve : {report['auto_approved']}")
    print(f"     🟡 Flag         : {report['flagged']}")
    print(f"     ❌ Reject       : {report['rejected']}")

    narrative = (
        f"Employee {EMPLOYEE_ID} submitted {report['total_claims']} expense claims "
        f"totalling ${sum(report['category_totals'].values()):.2f}. "
        f"Compliance rate is {compliance_rate}% with {report['violation_count']} policy "
        f"violation(s) and ${report['total_at_risk']:.2f} flagged at risk. "
        f"{report['duplicate_flags']} potential duplicate(s) detected. "
        f"{report['auto_approved']} claim(s) are ready for auto-approval, "
        f"{report['flagged']} require manager review, and {report['rejected']} "
        f"should be rejected outright."
    )
    print(f"\n  📝 Manager Narrative:\n  {narrative}")
    _divider()
    print("  ✅ Demo complete — all 5 MCP tools executed successfully.\n")


if __name__ == "__main__":
    run_demo()

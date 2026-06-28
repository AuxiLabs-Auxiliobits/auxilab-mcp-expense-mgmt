#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Expense Management Platform -- offline demo script.

Runs all 5 core-engine tools with synthetic inputs.
No server, no Azure, no LLM credentials required -- everything runs offline.

Usage:
    python demo.py
"""

import sys
import textwrap
from datetime import date, datetime
from decimal import Decimal

# Make locally installed editable packages importable.
# If you ran `pip install -e ./core-engine`, this sys.path insert is a no-op.
sys.path.insert(0, "core-engine/src")

from expense_core.policy.baseline import BaselinePolicy, CapBoundary, load_baseline_policy
from expense_core.schemas.enums import Category, DuplicateRisk
from expense_core.schemas.tools import LineItemInput
from expense_core.tools.category_classifier import classify_category
from expense_core.tools.duplicate_detector import (
    CandidateLineItem,
    HistoricalLineItem,
    detect_duplicates,
)
from expense_core.tools.policy_checker import check_policy
from expense_core.tools.receipt_parser import parse_receipt
from expense_core.tools.report_summariser import SummaryLineItem, summarise_report

DIVIDER = "-" * 62
TODAY = date(2024, 6, 15)


def section(title):
    print("\n" + DIVIDER)
    print("  " + title)
    print(DIVIDER)


def ok_fail(cond):
    return "[PASS]" if cond else "[FAIL]"


# ----------------------------------------------------------------------------
# 1. Policy Checker
# ----------------------------------------------------------------------------

def demo_policy():
    section("1. Policy Checker  (deterministic -- zero LLM)")

    default_policy = load_baseline_policy()

    # Custom policy that prohibits Client Entertainment.
    strict_policy = BaselinePolicy(
        per_meal_limit=Decimal("75"),
        per_hotel_night_limit=Decimal("250"),
        prohibited_categories=[Category.CLIENT_ENTERTAINMENT],
        receipt_required_threshold=Decimal("25"),
        max_file_mb=25,
        allowed_extensions=[".pdf", ".jpg", ".jpeg", ".png", ".heic"],
        duplicate_near_match_days=3,
        cap_boundary=CapBoundary.INCLUSIVE,
        llm_confidence_routing_threshold=0.7,
        currency="USD",
    )

    cases = [
        (
            "Valid client lunch $45.00, receipt matches",
            LineItemInput(
                employee_id="emp-001",
                category=Category.MEALS_ENTERTAINMENT,
                amount=Decimal("45.00"),
                merchant="Noodle House",
                description="Team lunch - project kickoff",
                expense_date=date(2024, 6, 1),
                receipt_total=Decimal("45.00"),
            ),
            default_policy,
        ),
        (
            "Prohibited category (Client Entertainment blocked by policy)",
            LineItemInput(
                employee_id="emp-001",
                category=Category.CLIENT_ENTERTAINMENT,
                amount=Decimal("200.00"),
                merchant="Broadway Tickets",
                description="Client entertainment - Broadway show",
                expense_date=date(2024, 6, 1),
            ),
            strict_policy,
        ),
        (
            "Amount mismatch: entered $50.00, receipt says $47.50",
            LineItemInput(
                employee_id="emp-001",
                category=Category.MEALS_ENTERTAINMENT,
                amount=Decimal("50.00"),
                merchant="Coffee Corner",
                description="Client coffee meeting",
                expense_date=date(2024, 6, 1),
                receipt_total=Decimal("47.50"),
            ),
            default_policy,
        ),
        (
            "Future-dated expense (date: 2025-01-01, today: 2024-06-15)",
            LineItemInput(
                employee_id="emp-001",
                category=Category.TRAVEL_AIR,
                amount=Decimal("320.00"),
                merchant="Delta Airlines",
                description="NYC to Chicago - client visit",
                expense_date=date(2025, 1, 1),
            ),
            default_policy,
        ),
    ]

    for label, item, policy in cases:
        result = check_policy(item, policy, today=TODAY)
        passed = result.status.value == "pass"
        status = ok_fail(passed)
        print(f"  {status}  {label}")
        if not passed:
            for v in result.violations:
                print(f"           Reason: {v.message} [{v.code}]")


# ----------------------------------------------------------------------------
# 2. Receipt Parser
# ----------------------------------------------------------------------------

def demo_receipt():
    section("2. Receipt Parser  (regex offline fallback)")

    raw_text = textwrap.dedent("""
        NOODLE HOUSE
        123 Main St, San Francisco

        2024-06-01  12:47 PM

        Pad Thai (x2)        18.00
        Green Curry          14.50
        Diet Coke (x2)        7.00
        Sparkling Water       5.50
        Subtotal             45.00
        Tax (8.625%)          3.88
        Total                48.88

        VISA  ****-4321
    """).strip()

    result = parse_receipt(raw_text)

    print(f"  Merchant   : {result.merchant}")
    print(f"  Total      : ${result.total}")
    print(f"  Tax        : ${result.tax}")
    rec_status = ok_fail(result.reconciles)
    print(f"  Reconciles : {rec_status}  (sum of items + tax == total, delta=${result.delta})")
    print("  Line items :")
    for li in result.line_items:
        print(f"    * {li.description:30s}  ${li.amount}")


# ----------------------------------------------------------------------------
# 3. Category Classifier
# ----------------------------------------------------------------------------

def demo_classifier():
    section("3. Category Classifier  (keyword fallback, no LLM needed)")

    cases = [
        ("Team lunch at Noodle House",          "Noodle House"),
        ("GitHub Copilot annual subscription",  "GitHub"),
        ("Delta Airlines JFK to LAX",           "Delta Airlines"),
        ("Parking at SFO airport",              "SFO Parking"),
        ("Marriott NYC -- 2 nights",            "Marriott"),
        ("Unknown widget from AcmeCo",          "AcmeCo"),
    ]

    for desc, merchant in cases:
        r = classify_category(desc, merchant)
        conf = f"{r.confidence:.0%}"
        status = ok_fail(r.confidence >= 0.7)
        print(f"  {status}  {desc[:44]:44s}  -> {r.category.value}  ({conf})")


# ----------------------------------------------------------------------------
# 4. Duplicate Detector
# ----------------------------------------------------------------------------

def demo_duplicate():
    section("4. Duplicate Detector  (deterministic -- zero LLM)")

    receipt_dt = datetime(2024, 6, 1, 12, 47)
    emp = "emp-001"
    total = Decimal("48.88")

    candidate = CandidateLineItem(
        employee_id=emp,
        receipt_datetime=receipt_dt,
        total=total,
    )

    # First submission -- empty history, no duplicates.
    history = []
    r1 = detect_duplicates(candidate, history)
    print(f"  First submission    risk={r1.risk.value:6s}  {ok_fail(r1.risk == DuplicateRisk.NONE)}")

    # Add to history, resubmit -- should flag as duplicate.
    history.append(
        HistoricalLineItem(
            line_item_id="li-abc-001",
            employee_id=emp,
            receipt_datetime=receipt_dt,
            total=total,
        )
    )
    r2 = detect_duplicates(candidate, history)
    is_dup = r2.risk in (DuplicateRisk.HIGH, DuplicateRisk.MEDIUM)
    print(f"  Resubmit same rcpt  risk={r2.risk.value:6s}  {ok_fail(is_dup)} DUPLICATE DETECTED")
    if r2.matches:
        print(f"           Reason: {r2.matches[0].reason} match on (employee, receipt_datetime, total)")

    # Different amount -- not a duplicate.
    diff = CandidateLineItem(employee_id=emp, receipt_datetime=receipt_dt, total=Decimal("12.00"))
    r3 = detect_duplicates(diff, history)
    print(f"  Different amount    risk={r3.risk.value:6s}  {ok_fail(r3.risk == DuplicateRisk.NONE)}")


# ----------------------------------------------------------------------------
# 5. Report Summariser
# ----------------------------------------------------------------------------

def demo_report():
    section("5. Report Summariser  (deterministic aggregation + templated narrative)")

    items = [
        SummaryLineItem(category=Category.MEALS_ENTERTAINMENT,    amount=Decimal("48.88"),  is_compliant=True),
        SummaryLineItem(category=Category.TRAVEL_AIR,             amount=Decimal("320.00"), is_compliant=True),
        SummaryLineItem(category=Category.SOFTWARE_SUBSCRIPTIONS, amount=Decimal("19.00"),  is_compliant=True),
        SummaryLineItem(category=Category.OFFICE_SUPPLIES,        amount=Decimal("28.50"),  is_compliant=False),
    ]

    result = summarise_report(items)

    grand_total = sum(result.total_by_category.values(), Decimal("0"))
    top_cat = max(result.total_by_category, key=result.total_by_category.get)

    print(f"  Total spend        : ${grand_total}")
    print(f"  Line items         : {len(items)}")
    print(f"  Violations flagged : {result.violation_count}  (${result.total_at_risk} at risk)")
    print(f"  Compliance rate    : {result.compliance_rate_pct}%")
    print(f"  Top category       : {top_cat.value}  (${result.total_by_category[top_cat]})")
    print(f"  Narrative          : {result.narrative}")


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    print(DIVIDER)
    print("  Expense Management Platform -- Core Engine Demo")
    print("  (offline mode: no Azure, no LLM credentials needed)")
    print(DIVIDER)

    demo_policy()
    demo_receipt()
    demo_classifier()
    demo_duplicate()
    demo_report()

    print("\n" + DIVIDER)
    print("  Demo complete.")
    print("  Next steps:")
    print("    cd api && pytest          # full integration test suite")
    print("    make api                  # start the REST API on :8000")
    print("    make mcp                  # start the MCP server")
    print(DIVIDER)
    print()

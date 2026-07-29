#!/usr/bin/env python3
"""Terminal demo — exercises all five tools with no dependencies beyond pydantic.

    python cli.py            # run every tool
    python cli.py policy     # run one

Useful when you want a fast check that the engine works, in CI, or over SSH where a
browser UI isn't an option. For the full experience use ``python app.py``.
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from decimal import Decimal

from compliance_tools import (
    CandidateLineItem,
    Category,
    DuplicateRisk,
    LineItemInput,
    SummaryLineItem,
    check_policy,
    classify_category,
    detect_duplicates,
    load_policy,
    parse_receipt,
    summarise_report,
)
from local_db import get_store

RULE = "-" * 72
POLICY = load_policy()
TODAY = date(2026, 6, 15)


def header(title: str) -> None:
    print(f"\n{RULE}\n  {title}\n{RULE}")


def mark(ok: bool) -> str:
    return "[ok]  " if ok else "[flag]"


# --------------------------------------------------------------------------- #
def demo_policy() -> None:
    header("1. Policy Checker  (deterministic, no model)")

    cases = [
        (
            "Compliant team lunch, receipt attached",
            LineItemInput(
                employee_id="emp-001",
                category=Category.MEALS_ENTERTAINMENT,
                amount=Decimal("45.00"),
                merchant="Noodle House",
                description="Team lunch",
                expense_date=date(2026, 6, 1),
                has_receipt=True,
                receipt_total=Decimal("45.00"),
            ),
        ),
        (
            "Dinner over the $75 category cap",
            LineItemInput(
                employee_id="emp-001",
                category=Category.MEALS_ENTERTAINMENT,
                amount=Decimal("187.00"),
                merchant="The Chophouse",
                description="Client dinner",
                expense_date=date(2026, 6, 1),
                has_receipt=True,
            ),
        ),
        (
            "Prohibited category",
            LineItemInput(
                employee_id="emp-001",
                category=Category.CLIENT_ENTERTAINMENT,
                amount=Decimal("200.00"),
                merchant="Broadway Tickets",
                description="Show tickets",
                expense_date=date(2026, 6, 1),
                has_receipt=True,
            ),
        ),
        (
            "Receipt missing above the $25 threshold",
            LineItemInput(
                employee_id="emp-001",
                category=Category.OFFICE_SUPPLIES,
                amount=Decimal("60.00"),
                merchant="Staples",
                description="Printer paper",
                expense_date=date(2026, 6, 1),
                has_receipt=False,
            ),
        ),
        (
            "Entered amount disagrees with the receipt",
            LineItemInput(
                employee_id="emp-001",
                category=Category.MEALS_ENTERTAINMENT,
                amount=Decimal("50.00"),
                merchant="Coffee Corner",
                description="Client coffee",
                expense_date=date(2026, 6, 1),
                has_receipt=True,
                receipt_total=Decimal("47.50"),
            ),
        ),
        (
            "Future-dated expense",
            LineItemInput(
                employee_id="emp-001",
                category=Category.TRAVEL_AIR,
                amount=Decimal("320.00"),
                merchant="Delta Airlines",
                description="Client visit",
                expense_date=date(2027, 1, 1),
                has_receipt=True,
            ),
        ),
    ]

    for label, item in cases:
        result = check_policy(item, POLICY, today=TODAY)
        passed = result.status.value == "pass"
        print(f"  {mark(passed)} {label}")
        for violation in result.violations:
            print(f"          {violation.code}: {violation.message}")


def demo_receipt() -> None:
    header("2. Receipt Parser  (extraction + arithmetic verification)")

    receipt = """NOODLE HOUSE
123 Main St, San Francisco

2026-06-01  12:47

Pad Thai (x2)          18.00
Green Curry            14.50
Diet Coke (x2)          7.00
Sparkling Water         5.50
Subtotal               45.00
Tax (8.625%)            3.88
Total                  48.88

VISA  ****-4321"""

    result = parse_receipt(receipt)
    print(f"  Merchant   : {result.merchant}")
    print(f"  Timestamp  : {result.receipt_datetime}")
    print(f"  Payment    : {result.payment_method}")
    print(f"  Tax        : {result.tax}")
    print(f"  Total      : {result.total}")
    print(f"  {mark(result.reconciles)} Reconciles (items + tax == total, delta={result.delta})")
    print("  Line items :")
    for line in result.line_items:
        print(f"          {line.description:<28} {line.amount:>8}")

    tampered = receipt.replace("Total                  48.88", "Total                  58.88")
    bad = parse_receipt(tampered)
    print(
        f"  {mark(bad.reconciles)} Same receipt with the total altered to 58.88 "
        f"-> caught, off by {bad.delta}"
    )


def demo_classifier() -> None:
    header("3. Category Classifier  (keyword matching, no model)")

    cases = [
        ("Team lunch at Noodle House", "Noodle House"),
        ("Copilot annual subscription", "GitHub"),
        ("JFK to LAX", "Delta Airlines"),
        ("Airport parking", "SFO Parking"),
        ("2 nights downtown", "Marriott"),
        ("Blue widget", "AcmeCo"),
    ]
    for description, merchant in cases:
        result = classify_category(description, merchant)
        confident = result.confidence >= 0.7
        print(
            f"  {mark(confident)} {description:<32} -> {result.category.value:<26} "
            f"{result.confidence:.0%}"
        )


def demo_duplicates() -> None:
    header("4. Duplicate Detector  (screened against local SQLite history)")

    store = get_store()
    history = store.history_for("emp-002")
    print(f"  Stored history for emp-002: {len(history)} item(s)")

    candidate = CandidateLineItem(
        employee_id="emp-002",
        receipt_datetime=datetime(2026, 6, 5, 7, 30),
        total=Decimal("42.50"),
    )
    result = detect_duplicates(candidate, history, near_match_days=3)
    found = result.risk is not DuplicateRisk.NONE
    print(
        f"  {mark(not found)} Re-submitting the $42.50 Uber ride -> risk={result.risk.value} "
        f"(score {result.risk_score})"
    )
    for match in result.matches:
        print(
            f"          {match.reason} against {match.line_item_id} "
            f"({match.receipt_datetime}, {match.total})"
        )

    novel = CandidateLineItem(
        employee_id="emp-002",
        receipt_datetime=datetime(2026, 6, 9, 9, 0),
        total=Decimal("19.99"),
    )
    clean = detect_duplicates(novel, history, near_match_days=3)
    print(
        f"  {mark(clean.risk is DuplicateRisk.NONE)} A genuinely new $19.99 expense "
        f"-> risk={clean.risk.value}"
    )


def demo_report() -> None:
    header("5. Report Summariser  (aggregation + narrative)")

    items = [
        SummaryLineItem(
            category=Category.MEALS_ENTERTAINMENT, amount=Decimal("48.88"), is_compliant=True
        ),
        SummaryLineItem(category=Category.TRAVEL_AIR, amount=Decimal("320.00"), is_compliant=True),
        SummaryLineItem(
            category=Category.TRAVEL_HOTEL, amount=Decimal("462.00"), is_compliant=False
        ),
        SummaryLineItem(
            category=Category.SOFTWARE_SUBSCRIPTIONS, amount=Decimal("100.00"), is_compliant=True
        ),
        SummaryLineItem(
            category=Category.OFFICE_SUPPLIES, amount=Decimal("28.50"), is_compliant=False
        ),
    ]
    result = summarise_report(items)

    print(f"  Line items      : {len(items)}")
    print(f"  Compliance rate : {result.compliance_rate_pct}%")
    print(f"  Flagged         : {result.violation_count} item(s), {result.total_at_risk} at risk")
    print("  Spend by category:")
    for category, amount in sorted(result.total_by_category.items(), key=lambda kv: -kv[1]):
        print(f"          {category.value:<28} {amount:>9}")
    print(f"\n  {result.narrative}")


DEMOS = {
    "policy": demo_policy,
    "receipt": demo_receipt,
    "classify": demo_classifier,
    "duplicates": demo_duplicates,
    "report": demo_report,
}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if argv:
        unknown = [name for name in argv if name not in DEMOS]
        if unknown:
            print(f"Unknown demo(s): {', '.join(unknown)}")
            print(f"Available: {', '.join(DEMOS)}")
            return 2
        selected = [DEMOS[name] for name in argv]
    else:
        selected = list(DEMOS.values())

    print(RULE)
    print("  Expense Compliance Tools — offline demo")
    print("  No cloud, no credentials, no network.")
    print(RULE)

    for demo in selected:
        demo()

    print(f"\n{RULE}")
    print("  Done. Next:  python app.py         browser UI")
    print("               python mcp_server.py  MCP server for AI agents")
    print(RULE)
    return 0


if __name__ == "__main__":
    sys.exit(main())

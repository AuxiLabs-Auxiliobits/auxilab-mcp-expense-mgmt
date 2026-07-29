"""Demo handlers — the logic behind each tab, with no Gradio in sight.

Kept separate from :mod:`app` for two reasons. It is what lets the demo fall back to the
terminal when Gradio cannot be imported, and it means every handler is an ordinary
function that can be called and asserted on directly, rather than only through a running
server.

Nothing here imports Gradio, and a test enforces that.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path

from compliance_tools import (
    CandidateLineItem,
    Category,
    LineItemInput,
    SummaryLineItem,
    check_policy,
    classify_category,
    detect_duplicates,
    load_policy,
    parse_receipt,
    summarise_report,
)
from compliance_tools.receipt_parser import read_text
from local_db import get_store


@lru_cache(maxsize=1)
def _policy():
    """The active policy, read once on first use rather than at import."""
    return load_policy()


SAMPLE_RECEIPT = """NOODLE HOUSE
123 Main St, San Francisco

2026-06-01  12:47

Pad Thai (x2)          18.00
Green Curry            14.50
Diet Coke (x2)          7.00
Sparkling Water         5.50
Subtotal               45.00
Tax (8.625%)            3.88
Total                  48.88

VISA  ****-4321
"""

CATEGORIES = [c.value for c in Category]


def _text(value: object) -> str:
    """Normalise a component value to a stripped string.

    Gradio hands back ``None`` for a cleared component in some versions, so every handler
    goes through this rather than calling ``.strip()`` on whatever arrived.
    """
    return "" if value is None else str(value).strip()


def _decimal(value: object, field: str) -> Decimal:
    try:
        return Decimal(_text(value))
    except (InvalidOperation, ValueError) as e:
        raise ValueError(f"{field} must be a number, got {value!r}") from e


def _date(value: object, field: str) -> date:
    try:
        return date.fromisoformat(_text(value))
    except ValueError as e:
        raise ValueError(f"{field} must look like YYYY-MM-DD, got {value!r}") from e


def _datetime(value: object, field: str) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError as e:
        raise ValueError(
            f"{field} must be an ISO timestamp like 2026-06-05T07:30:00, got {value!r}"
        ) from e


def _money(value: Decimal) -> str:
    return f"{value:,.2f}"


# --------------------------------------------------------------------------- #
# 1. Policy Checker
# --------------------------------------------------------------------------- #
def run_policy_checker(
    employee_id: str,
    amount: str,
    merchant: str,
    expense_date: str,
    category: str,
    description: str,
    has_receipt: bool,
    receipt_total: str,
) -> tuple[str, dict]:
    item = LineItemInput(
        employee_id=_text(employee_id) or "emp-001",
        category=Category(category) if category else None,
        amount=_decimal(amount, "Amount"),
        merchant=_text(merchant) or "Unknown",
        description=_text(description),
        expense_date=_date(expense_date, "Expense date"),
        has_receipt=bool(has_receipt),
        receipt_total=(_decimal(receipt_total, "Receipt total") if _text(receipt_total) else None),
    )
    result = check_policy(item, _policy())

    if result.status.value == "pass":
        report = "## PASS\n\nNo policy violations. Recommended action: **accept**."
    else:
        rows = "\n".join(
            f"| `{v.code}` | {v.message} | {v.field or '—'} |" for v in result.violations
        )
        report = (
            f"## FAIL — {len(result.violations)} violation(s)\n\n"
            f"| Code | Detail | Field |\n|---|---|---|\n{rows}\n\n"
            f"Recommended action: **{result.recommended_action.value}**"
        )
    return report, result.model_dump(mode="json")


# --------------------------------------------------------------------------- #
# 2. Receipt Parser
# --------------------------------------------------------------------------- #
def run_receipt_parser(receipt_text: str, file_path: str | None) -> tuple[str, list, dict]:
    text = read_text(file_path) if file_path else _text(receipt_text)
    if not text.strip():
        raise ValueError("Paste receipt text or upload a file.")

    result = parse_receipt(text)
    rows = [[li.description, _money(li.amount)] for li in result.line_items]
    rows.append(["Tax", _money(result.tax)])
    rows.append(["TOTAL", _money(result.total)])

    verdict = (
        "## Reconciles\n\nLine items plus tax match the stated total."
        if result.reconciles
        else f"## Does not reconcile\n\nOff by **{_money(result.delta)}** — "
        "the stated total disagrees with the itemised lines."
    )
    meta = (
        f"\n\n**Merchant:** {result.merchant}  \n"
        f"**Timestamp:** {result.receipt_datetime or 'not found'}  \n"
        f"**Payment:** {result.payment_method or 'not found'}"
    )
    return verdict + meta, rows, result.model_dump(mode="json")


# --------------------------------------------------------------------------- #
# 3. Category Classifier
# --------------------------------------------------------------------------- #
def run_category_classifier(description: str, merchant: str) -> tuple[str, dict]:
    description, merchant = _text(description), _text(merchant)
    if not description and not merchant:
        raise ValueError("Enter a description or a merchant.")

    result = classify_category(description, merchant)
    confidence = "high" if result.confidence >= 0.7 else "low"
    report = (
        f"## {result.category.value}\n\n"
        f"**Confidence:** {result.confidence:.0%} ({confidence})  \n"
        f"**Why:** {result.rationale}"
    )
    return report, result.model_dump(mode="json")


# --------------------------------------------------------------------------- #
# 4. Duplicate Detector
# --------------------------------------------------------------------------- #
def run_duplicate_detector(
    employee_id: str, total: str, receipt_datetime: str, near_match_days: int
) -> tuple[str, list, dict]:
    candidate = CandidateLineItem(
        employee_id=_text(employee_id) or "emp-002",
        receipt_datetime=_datetime(receipt_datetime, "Receipt timestamp"),
        total=_decimal(total, "Total"),
    )
    history = get_store().history_for(candidate.employee_id)
    # A Slider yields a float even with step=1; timedelta would accept it, but the tool's
    # contract is an integer number of days.
    result = detect_duplicates(candidate, history, near_match_days=int(near_match_days))

    rows = [
        [m.line_item_id, m.reason, str(m.receipt_datetime or "—"), _money(m.total)]
        for m in result.matches
    ]
    if result.matches:
        report = (
            f"## {result.risk.value.upper()} risk\n\n"
            f"Score **{result.risk_score:.2f}** — {len(result.matches)} match(es) "
            f"across {len(history)} stored item(s) for `{candidate.employee_id}`."
        )
    else:
        report = (
            f"## No duplicates\n\nCompared against {len(history)} stored item(s) "
            f"for `{candidate.employee_id}`."
        )
    return report, rows, result.model_dump(mode="json")


# --------------------------------------------------------------------------- #
# 5. Report Summariser
# --------------------------------------------------------------------------- #
def run_report_summariser(employee_id: str, items_json: str) -> tuple[str, list, dict]:
    employee_id, items_json = _text(employee_id), _text(items_json)

    if items_json:
        parsed = json.loads(items_json)
        if not isinstance(parsed, list):
            # Iterating a dict would yield its keys and produce a baffling pydantic error.
            raise ValueError(
                f"Expected a JSON list of items, got a {type(parsed).__name__}. "
                'Example: [{"category": "Travel - Air", "amount": "320.00", "is_compliant": true}]'
            )
        items = [SummaryLineItem.model_validate(i) for i in parsed]
        source = f"{len(items)} item(s) supplied directly"
    else:
        items = get_store().summary_items(employee_id or None)
        scope = f"employee `{employee_id}`" if employee_id else "all employees"
        source = f"{len(items)} stored item(s) for {scope}"

    if not items:
        return f"## Nothing to summarise\n\nNo items found for {source}.", [], {}

    result = summarise_report(items)
    rows = [
        [cat.value, _money(amt)]
        for cat, amt in sorted(result.total_by_category.items(), key=lambda kv: -kv[1])
    ]
    grand = sum(result.total_by_category.values(), Decimal("0"))
    rows.append(["TOTAL", _money(grand)])

    report = (
        f"## {result.compliance_rate_pct}% compliant\n\n"
        f"**Source:** {source}  \n"
        f"**Total spend:** {_money(grand)}  \n"
        f"**Flagged:** {result.violation_count} item(s), {_money(result.total_at_risk)} at risk\n\n"
        f"> {result.narrative}"
    )
    return report, rows, result.model_dump(mode="json")


def _display_path(path: str) -> str:
    """Abbreviate the home directory to ``~``.

    Keeps the status line short, and keeps a username out of any screenshot taken of it.
    """
    try:
        return "~/" + Path(path).relative_to(Path.home()).as_posix()
    except ValueError:
        return path


def database_status() -> str:
    stats = get_store().stats()
    return (
        f"**{stats['line_items']}** line items · **{stats['employees']}** employees · "
        f"**{stats['analyses']}** recorded tool runs · `{_display_path(stats['path'])}`"
    )

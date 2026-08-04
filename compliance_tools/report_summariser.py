"""Tool 5 — Report Summariser.

Aggregates a set of line items into per-category totals, a violation count, the amount
at risk, and a compliance rate — then writes a short narrative around those numbers.

Every figure is computed here in Python. If you supply an ``llm`` it is asked only to
phrase the summary, and it is handed the finished numbers as facts; it never gets to
produce them. Offline, a templated narrative says the same thing.
"""

from __future__ import annotations

from decimal import Decimal

from compliance_tools.llm import ChatMessage, LLMGateway, OfflineProvider, is_offline
from compliance_tools.schemas import Category, ReportSummary, SummaryLineItem


def summarise_report(items: list[SummaryLineItem], llm: LLMGateway | None = None) -> ReportSummary:
    """Aggregate line items and produce a narrative summary."""
    llm = llm or OfflineProvider()

    total_by_category: dict[Category, Decimal] = {}
    total_at_risk = Decimal("0")
    violation_count = 0

    for item in items:
        total_by_category[item.category] = (
            total_by_category.get(item.category, Decimal("0")) + item.amount
        )
        if not item.is_compliant:
            violation_count += 1
            total_at_risk += item.amount

    count = len(items)
    compliance_rate = 100.0 if count == 0 else round((count - violation_count) / count * 100, 2)

    narrative = _narrative(
        llm, total_by_category, violation_count, total_at_risk, compliance_rate, count
    )

    return ReportSummary(
        total_by_category=total_by_category,
        violation_count=violation_count,
        total_at_risk=total_at_risk,
        compliance_rate_pct=compliance_rate,
        narrative=narrative,
    )


def _narrative(
    llm: LLMGateway,
    by_category: dict[Category, Decimal],
    violations: int,
    at_risk: Decimal,
    rate: float,
    count: int,
) -> str:
    grand_total = sum(by_category.values(), Decimal("0"))
    top = max(by_category, key=lambda c: by_category[c]).value if by_category else "n/a"

    facts = (
        f"{count} line items totalling {grand_total}. Highest spend category: {top}. "
        f"{violations} violation(s), {at_risk} at risk, compliance rate {rate}%."
    )
    raw = llm.complete(
        [
            ChatMessage(
                role="system",
                content=(
                    "Write a one-paragraph factual expense summary from the given figures. "
                    "Do not invent numbers that were not provided."
                ),
            ),
            ChatMessage(role="user", content=facts),
        ]
    )

    if is_offline(raw):
        return (
            f"Reviewed {count} line item(s) totalling {grand_total}. "
            f"Highest spend category: {top}. "
            f"{violations} item(s) flagged ({at_risk} at risk); compliance rate {rate}%."
        )
    return raw

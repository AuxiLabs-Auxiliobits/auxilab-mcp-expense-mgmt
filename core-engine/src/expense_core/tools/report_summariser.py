"""Tool 5 — Report Summariser. Deterministic aggregation + optional LLM narrative (SCOPING §4).

All numbers (totals, violation count, at-risk, compliance rate) are computed
deterministically. The LLM only writes prose around them; offline it falls back to a
templated narrative so the tool is fully functional without Azure.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from expense_core.llm.gateway import ChatMessage, LLMGateway
from expense_core.llm.providers import LocalEchoProvider
from expense_core.schemas.enums import Category
from expense_core.schemas.tools import ReportSummary


class SummaryLineItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: Category
    amount: Decimal
    is_compliant: bool


def summarise_report(items: list[SummaryLineItem], llm: LLMGateway | None = None) -> ReportSummary:
    llm = llm or LocalEchoProvider()

    total_by_category: dict[Category, Decimal] = {}
    total_at_risk = Decimal("0")
    violation_count = 0
    for it in items:
        total_by_category[it.category] = total_by_category.get(it.category, Decimal("0")) + it.amount
        if not it.is_compliant:
            violation_count += 1
            total_at_risk += it.amount

    n = len(items)
    compliance_rate = 100.0 if n == 0 else round((n - violation_count) / n * 100, 2)

    narrative = _narrative(llm, total_by_category, violation_count, total_at_risk, compliance_rate, n)

    return ReportSummary(
        total_by_category=total_by_category,
        violation_count=violation_count,
        total_at_risk=total_at_risk,
        compliance_rate_pct=compliance_rate,
        narrative=narrative,
    )


def _narrative(
    llm: LLMGateway,
    by_cat: dict[Category, Decimal],
    violations: int,
    at_risk: Decimal,
    rate: float,
    n: int,
) -> str:
    grand_total = sum(by_cat.values(), Decimal("0"))
    facts = (
        f"{n} line items totalling {grand_total}. {violations} violation(s), "
        f"{at_risk} at risk, compliance rate {rate}%."
    )
    raw = llm.complete(
        [
            ChatMessage(role="system", content="Write a one-paragraph factual expense summary."),
            ChatMessage(role="user", content=facts),
        ]
    )
    if raw == LocalEchoProvider.SENTINEL:
        top = max(by_cat, key=by_cat.get).value if by_cat else "n/a"
        return (
            f"Reviewed {n} line item(s) totalling {grand_total}. Highest spend category: {top}. "
            f"{violations} item(s) flagged ({at_risk} at risk); compliance rate {rate}%."
        )
    return raw

"""The five stateless expense-engine tools (SCOPING §4, §11).

Pure wrappers over `expense_core` — no DB, no auth, no RBAC (those belong to the API layer
and to the business tools). LLM-using tools default to the offline `LocalEchoProvider`, so the
server runs with no Azure; pass `use_llm=True` to opt into a real provider when wired.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import Field

from expense_core.llm.gateway import LLMGateway
from expense_core.policy import load_baseline_policy
from expense_core.schemas.enums import Category
from expense_core.schemas.tools import LineItemInput
from expense_core.tools import (
    check_policy,
    classify_category,
    detect_duplicates,
    parse_receipt,
    summarise_report,
)
from expense_core.tools.duplicate_detector import CandidateLineItem, HistoricalLineItem
from expense_core.tools.report_summariser import SummaryLineItem

from expense_mcp.annotations import COMPUTE
from expense_mcp.instance import mcp

# Baseline ruleset loaded once at import (Admin-owned packaged JSON — read-only, stateless).
_BASELINE_POLICY = load_baseline_policy()


def _resolve_llm(use_llm: bool) -> LLMGateway | None:
    if not use_llm:
        return None
    endpoint = os.getenv("AZURE_FOUNDRY_ENDPOINT")
    deployment = os.getenv("AZURE_FOUNDRY_DEPLOYMENT")
    if not endpoint or not deployment:
        return None
    from expense_core.llm.providers import AzureFoundryProvider  # lazy: needs [azure]

    return AzureFoundryProvider(endpoint=endpoint, deployment=deployment)


@mcp.tool(annotations=COMPUTE)
def policy_checker(
    employee_id: str,
    amount: Annotated[Decimal, Field(gt=0)],
    merchant: str,
    expense_date: date,
    category: Category | None = None,
    currency: str = "USD",
    description: str = "",
    receipt_datetime: datetime | None = None,
    receipt_total: Decimal | None = None,
    has_receipt: bool = False,
    today: date | None = None,
) -> dict[str, Any]:
    """Validate one line item against the baseline ruleset (deterministic intake checks).
    Returns `{status, violations[], recommended_action}`."""
    item = LineItemInput(
        employee_id=employee_id, category=category, amount=amount, currency=currency,
        merchant=merchant, description=description, expense_date=expense_date,
        receipt_datetime=receipt_datetime, receipt_total=receipt_total, has_receipt=has_receipt,
    )
    return check_policy(item, _BASELINE_POLICY, today=today).model_dump(mode="json")


@mcp.tool(annotations=COMPUTE)
def receipt_parser(receipt_text: str, use_llm: bool = False) -> dict[str, Any]:
    """Extract structured receipt fields and reconcile the math. Returns
    `{merchant, receipt_datetime, total, tax, line_items[], payment_method, reconciles, delta}`."""
    return parse_receipt(receipt_text, llm=_resolve_llm(use_llm)).model_dump(mode="json")


@mcp.tool(annotations=COMPUTE)
def category_classifier(description: str, merchant: str, use_llm: bool = False) -> dict[str, Any]:
    """Classify an expense into one of the 8 categories. Returns `{category, confidence, rationale}`."""
    return classify_category(description, merchant, llm=_resolve_llm(use_llm)).model_dump(mode="json")


@mcp.tool(annotations=COMPUTE)
def duplicate_detector(
    candidate: CandidateLineItem,
    history: list[HistoricalLineItem],
    near_match_days: int = 3,
) -> dict[str, Any]:
    """Flag duplicate line items against history. Returns `{risk_score, risk, matches[]}`."""
    return detect_duplicates(candidate, history, near_match_days=near_match_days).model_dump(mode="json")


@mcp.tool(annotations=COMPUTE)
def report_summariser(items: list[SummaryLineItem], use_llm: bool = False) -> dict[str, Any]:
    """Aggregate a sheet/period and write a narrative. Returns `{total_by_category,
    violation_count, total_at_risk, compliance_rate_pct, narrative}`."""
    return summarise_report(items, llm=_resolve_llm(use_llm)).model_dump(mode="json")

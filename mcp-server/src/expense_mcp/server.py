"""MCP server: the five expense tools (SCOPING §4, §11).

Stateless FastMCP server that wraps `expense_core`. Every handler maps typed MCP
parameters onto the engine's Pydantic input models, calls the engine function, and
returns `result.model_dump(mode="json")` — JSON-safe (Decimals → strings, enums →
values). No DB, no auth, no RBAC: those live in the API layer (SCOPING §2).

LLM-using tools (receipt_parser, category_classifier, report_summariser) default to
the engine's `LocalEchoProvider`, so the server runs fully offline with no Azure. Pass
`use_llm=True` to opt into a real provider when one is wired (see `_resolve_llm`).
"""

from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
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

mcp = FastMCP("auxilab-mcp-expense-mgmt")

# Baseline ruleset loaded once at import (Admin-owned, packaged JSON — SCOPING §4, §20.B).
# Read-only here; the server never mutates it, keeping the tools stateless.
_BASELINE_POLICY = load_baseline_policy()


def _resolve_llm(use_llm: bool) -> LLMGateway | None:
    """Pick the LLM provider for a tool call (SCOPING §2, §11).

    Defaults to offline `LocalEchoProvider` (returns None so the engine uses its own
    default). When `use_llm` is set and Azure Foundry env vars are present, wire the
    real provider; otherwise stay offline so the server never fails closed on missing
    credentials.
    """
    if not use_llm:
        return None
    endpoint = os.getenv("AZURE_FOUNDRY_ENDPOINT")
    deployment = os.getenv("AZURE_FOUNDRY_DEPLOYMENT")
    if not endpoint or not deployment:
        return None  # fall back to engine default (LocalEchoProvider)
    from expense_core.llm.providers import AzureFoundryProvider  # lazy: needs [azure]

    return AzureFoundryProvider(endpoint=endpoint, deployment=deployment)


# --------------------------------------------------------------------------- #
# 1) Policy Checker — pure rules, no LLM (SCOPING §4, §6.1).
# --------------------------------------------------------------------------- #
@mcp.tool()
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
    """Validate one line item against the baseline ruleset (SCOPING §4, §6.1).

    Deterministic intake checks: receipt threshold, per-category caps, prohibited
    categories, submission window, data sanity. `today` is injectable for testing.
    Returns `{status, violations[], recommended_action}`.
    """
    item = LineItemInput(
        employee_id=employee_id,
        category=category,
        amount=amount,
        currency=currency,
        merchant=merchant,
        description=description,
        expense_date=expense_date,
        receipt_datetime=receipt_datetime,
        receipt_total=receipt_total,
        has_receipt=has_receipt,
    )
    result = check_policy(item, _BASELINE_POLICY, today=today)
    return result.model_dump(mode="json")


# --------------------------------------------------------------------------- #
# 2) Receipt Parser — LLM extract + deterministic reconciliation (SCOPING §4, §20.E).
# --------------------------------------------------------------------------- #
@mcp.tool()
def receipt_parser(receipt_text: str, use_llm: bool = False) -> dict[str, Any]:
    """Extract structured receipt fields and reconcile the math (SCOPING §4, §20.E).

    The LLM (or offline heuristic) proposes fields; Σ line items + tax == total is
    always recomputed deterministically. Returns
    `{merchant, receipt_datetime, total, tax, line_items[], payment_method,
    reconciles, delta}`.
    """
    result = parse_receipt(receipt_text, llm=_resolve_llm(use_llm))
    return result.model_dump(mode="json")


# --------------------------------------------------------------------------- #
# 3) Category Classifier — LLM + keyword fallback (SCOPING §4, §20.E).
# --------------------------------------------------------------------------- #
@mcp.tool()
def category_classifier(
    description: str, merchant: str, use_llm: bool = False
) -> dict[str, Any]:
    """Classify an expense into exactly one of the 8 categories (SCOPING §4, §20.E).

    Offline, a deterministic keyword map decides (e.g. Uber → Travel - Ground).
    Returns `{category, confidence, rationale}`.
    """
    result = classify_category(description, merchant, llm=_resolve_llm(use_llm))
    return result.model_dump(mode="json")


# --------------------------------------------------------------------------- #
# 4) Duplicate Detector — pure rules, no LLM (SCOPING §4, §6.1, §8).
# --------------------------------------------------------------------------- #
@mcp.tool()
def duplicate_detector(
    candidate: CandidateLineItem,
    history: list[HistoricalLineItem],
    near_match_days: int = 3,
) -> dict[str, Any]:
    """Flag duplicate line items against history (SCOPING §4, §6.1, §8).

    Unique key = (employee, receipt_datetime, final total). Detects EXACT_KEY,
    NEAR_MATCH_WINDOW, and INTRA_SHEET. Returns `{risk_score, risk, matches[]}`.
    """
    result = detect_duplicates(candidate, history, near_match_days=near_match_days)
    return result.model_dump(mode="json")


# --------------------------------------------------------------------------- #
# 5) Report Summariser — deterministic aggregation + LLM narrative (SCOPING §4).
# --------------------------------------------------------------------------- #
@mcp.tool()
def report_summariser(
    items: list[SummaryLineItem], use_llm: bool = False
) -> dict[str, Any]:
    """Aggregate a sheet/period and write a narrative (SCOPING §4).

    All numbers are computed deterministically; the LLM only writes prose (templated
    offline). Returns `{total_by_category, violation_count, total_at_risk,
    compliance_rate_pct, narrative}`.
    """
    result = summarise_report(items, llm=_resolve_llm(use_llm))
    return result.model_dump(mode="json")


def main() -> None:
    """Console-script entry point: serve the five tools over stdio (SCOPING §11)."""
    mcp.run()


if __name__ == "__main__":
    main()

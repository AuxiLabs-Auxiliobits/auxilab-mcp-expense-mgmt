#!/usr/bin/env python3
"""Local MCP server exposing the five expense-compliance tools over stdio.

Run it directly::

    python mcp_server.py

There is no authentication, no cloud connection, and no network call anywhere in this
process. Everything executes locally against ``local_db/sqlite.db``.

Two tools can read that database instead of making you supply data by hand:

* ``duplicate_detector`` compares against stored history by default, which is what makes
  it useful in a chat client — the model doesn't have to remember prior expenses.
* ``report_summariser`` aggregates stored items when you don't pass any explicitly.

Environment variables (all optional):

``EXPENSE_DB_PATH``
    Database location. Defaults to ``local_db/sqlite.db``.
``EXPENSE_POLICY_PATH``
    Custom policy JSON. Defaults to the packaged ``compliance_tools/baseline_policy.json``.
``EXPENSE_RECEIPT_DIR``
    Directory ``receipt_parser`` may read files from. **Defaults to the working
    directory** — reads are sandboxed out of the box. Set it to another path to move the
    boundary, or to ``*`` to remove it.
``EXPENSE_PERSIST``
    Set to ``0`` to stop recording tool runs to the audit trail.
``EXPENSE_LOG_LEVEL``
    Log verbosity. Defaults to ``INFO``. Logs go to stderr — stdout carries the protocol.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from compliance_tools import (
    CandidateLineItem,
    Category,
    HistoricalLineItem,
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

log = logging.getLogger("expense-mcp")

mcp = FastMCP("expense-compliance")


#: Set ``EXPENSE_RECEIPT_DIR`` to this to turn the sandbox off entirely.
SANDBOX_DISABLED = "*"


@lru_cache(maxsize=1)
def _policy():
    """The active policy, loaded once on first use rather than at import.

    Deferring it keeps a bad ``EXPENSE_POLICY_PATH`` from turning into an import error
    with no context, and keeps module import free of file I/O — which matters because an
    MCP client imports this module on every launch.
    """
    configured = os.getenv("EXPENSE_POLICY_PATH") or None
    try:
        return load_policy(configured)
    except (OSError, ValueError) as e:
        source = configured or "the packaged baseline policy"
        raise RuntimeError(f"Could not load policy from {source}: {e}") from e


def _persist_enabled() -> bool:
    return os.getenv("EXPENSE_PERSIST", "1") != "0"


def _store():
    """The shared store. ``get_store`` resolves ``EXPENSE_DB_PATH`` itself."""
    return get_store()


def _sandbox_root() -> Path | None:
    """The directory ``receipt_parser`` may read from. ``None`` means unrestricted.

    **Reads are confined to the working directory by default.** The server runs with the
    user's own privileges, so without a boundary a crafted tool call could ask for any
    file the user can read and get the contents back in the result — and the caller is
    frequently a language model acting on text it was given.

    The working directory is the boundary because it is the one an MCP client already
    controls: ``cwd`` is a standard field in a server definition, so pointing the sandbox
    somewhere else needs no knowledge of this project. ``EXPENSE_RECEIPT_DIR`` overrides
    it, and ``EXPENSE_RECEIPT_DIR=*`` opts out entirely.
    """
    configured = os.getenv("EXPENSE_RECEIPT_DIR")
    if configured == SANDBOX_DISABLED:
        return None
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.cwd().resolve()


def _resolve_receipt_path(file_path: str) -> Path:
    """Resolve a caller-supplied receipt path and enforce the sandbox.

    Resolution happens before the check, so ``../`` and symlinks cannot escape the root.
    """
    resolved = Path(file_path).expanduser().resolve()
    root = _sandbox_root()

    if root is not None and not resolved.is_relative_to(root):
        raise ValueError(
            f"Refusing to read {resolved}: receipt files must be inside {root}. "
            f"Set EXPENSE_RECEIPT_DIR to another directory, or to "
            f"'{SANDBOX_DISABLED}' to allow any path."
        )

    return resolved


def _record(tool: str, result: dict[str, Any], line_item_id: str | None = None) -> None:
    """Append to the local audit trail. Never let bookkeeping break a tool call."""
    if not _persist_enabled():
        return
    try:
        _store().record_analysis(tool, result, line_item_id)
    except Exception:  # pragma: no cover - defensive
        log.warning("could not record %s run to the audit trail", tool, exc_info=True)


# --------------------------------------------------------------------------- #
# 1. Policy Checker
# --------------------------------------------------------------------------- #
@mcp.tool()
def policy_checker(
    employee_id: Annotated[str, Field(description="Who is claiming the expense")],
    amount: Annotated[Decimal, Field(gt=0, description="Amount claimed, in `currency`")],
    merchant: Annotated[str, Field(description="Who was paid, e.g. 'Marriott'")],
    expense_date: Annotated[date, Field(description="Date the expense was incurred (YYYY-MM-DD)")],
    category: Annotated[
        Category | None,
        Field(description="Expense category. Omit if unknown — run category_classifier first."),
    ] = None,
    currency: Annotated[str, Field(description="ISO 4217 code")] = "USD",
    description: Annotated[str, Field(description="What the expense was for")] = "",
    receipt_datetime: Annotated[
        datetime | None, Field(description="Timestamp printed on the receipt")
    ] = None,
    receipt_total: Annotated[
        Decimal | None,
        Field(description="Total read off the receipt. Supply it to check it matches `amount`."),
    ] = None,
    has_receipt: Annotated[bool, Field(description="Whether a receipt is attached")] = False,
) -> dict[str, Any]:
    """Check one expense against the active spend policy.

    Fully deterministic — no model involved. Checks category caps, prohibited categories,
    receipt requirements, the claim window, and whether the claimed amount matches the
    receipt.

    Returns `{status, violations[], recommended_action}` where `status` is
    `pass` or `fail`, each violation carries a machine-readable `code`, and
    `recommended_action` is one of `accept`, `request_receipt`, `return_to_employee`.
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
    # `today` is deliberately not exposed as a tool parameter: date rules must be
    # evaluated against the real clock. Letting a caller supply "today" would let it
    # decide whether an expense is future-dated or outside the claim window.
    result = check_policy(item, _policy()).model_dump(mode="json")
    _record("policy_checker", result)
    return result


# --------------------------------------------------------------------------- #
# 2. Receipt Parser
# --------------------------------------------------------------------------- #
@mcp.tool()
def receipt_parser(
    receipt_text: Annotated[
        str, Field(description="Raw receipt text. Takes precedence over `file_path`.")
    ] = "",
    file_path: Annotated[
        str,
        Field(description="Path to a local .txt, .text, .md or .pdf receipt (max 10 MB)"),
    ] = "",
) -> dict[str, Any]:
    """Extract structured fields from a receipt and verify its arithmetic.

    Supply exactly one of `receipt_text` or `file_path`.

    The `reconciles` flag is recomputed here from the extracted numbers — it reports
    whether the line items plus tax actually add up to the stated total, and `delta` gives
    the discrepancy. A receipt that does not reconcile should be treated as unverified.

    Returns `{merchant, receipt_datetime, total, tax, line_items[], payment_method,
    reconciles, delta}`.
    """
    if not receipt_text and not file_path:
        raise ValueError("Provide either receipt_text or file_path.")

    text = receipt_text or read_text(_resolve_receipt_path(file_path))
    result = parse_receipt(text).model_dump(mode="json")
    _record("receipt_parser", result)
    return result


# --------------------------------------------------------------------------- #
# 3. Category Classifier
# --------------------------------------------------------------------------- #
@mcp.tool()
def category_classifier(
    description: Annotated[str, Field(description="What the expense was for")],
    merchant: Annotated[str, Field(description="Who was paid — improves accuracy")] = "",
) -> dict[str, Any]:
    """Classify an expense into one of the eight standard categories.

    Categories: Meals & Entertainment, Travel - Air, Travel - Hotel, Travel - Ground,
    Office Supplies, Software / Subscriptions, Client Entertainment, Other.

    Returns `{category, confidence, rationale}`. A confidence below 0.5 means nothing
    matched and the result defaulted to `Other` — treat that as needing human review
    rather than as a classification.
    """
    result = classify_category(description, merchant).model_dump(mode="json")
    _record("category_classifier", result)
    return result


# --------------------------------------------------------------------------- #
# 4. Duplicate Detector
# --------------------------------------------------------------------------- #
@mcp.tool()
def duplicate_detector(
    employee_id: Annotated[str, Field(description="Whose expenses to screen against")],
    total: Annotated[Decimal, Field(description="Final total of the expense being screened")],
    receipt_datetime: Annotated[
        datetime | None,
        Field(description="Timestamp on the receipt. Sharpens matching considerably."),
    ] = None,
    near_match_days: Annotated[
        int,
        Field(ge=0, le=365, description="How many days apart two equal totals may be"),
    ] = 3,
    sheet_id: Annotated[
        str | None,
        Field(description="Submission id; items sharing it are flagged as intra-sheet"),
    ] = None,
    history: Annotated[
        list[HistoricalLineItem] | None,
        Field(description="Compare against these instead of the local database"),
    ] = None,
) -> dict[str, Any]:
    """Screen an expense against previously recorded ones for duplicates.

    By default it compares against everything stored locally for `employee_id`, so you do
    not need to supply prior expenses — pass `history` only to override that.

    Totals must match exactly for anything to be flagged, and expenses from other
    employees are never matched. Returns `{risk_score, risk, matches[], compared_against}`
    where `risk` is `none`, `medium` or `high`, and each match explains itself with
    `EXACT_KEY`, `INTRA_SHEET` or `NEAR_MATCH_WINDOW`.
    """
    candidate = CandidateLineItem(
        employee_id=employee_id, receipt_datetime=receipt_datetime, total=total
    )

    if history is None:
        prior = _store().history_for(employee_id, sheet_id=sheet_id)
    else:
        prior = [HistoricalLineItem.model_validate(h) for h in history]

    result = detect_duplicates(candidate, prior, near_match_days=near_match_days).model_dump(
        mode="json"
    )
    result["compared_against"] = len(prior)
    _record("duplicate_detector", result)
    return result


# --------------------------------------------------------------------------- #
# 5. Report Summariser
# --------------------------------------------------------------------------- #
@mcp.tool()
def report_summariser(
    items: Annotated[
        list[SummaryLineItem] | None,
        Field(description="Summarise these instead of the local database"),
    ] = None,
    employee_id: Annotated[
        str | None, Field(description="Narrow the database query to one employee")
    ] = None,
) -> dict[str, Any]:
    """Aggregate expenses into totals, a violation count and a compliance rate.

    With no `items` this summarises what is stored locally, optionally narrowed to one
    `employee_id` — so you can ask for a report without supplying any data.

    Every figure is computed arithmetically; the narrative only describes them. Returns
    `{total_by_category, violation_count, total_at_risk, compliance_rate_pct, narrative,
    item_count}`.
    """
    if items is None:
        line_items = _store().summary_items(employee_id)
    else:
        line_items = [SummaryLineItem.model_validate(i) for i in items]

    result = summarise_report(line_items).model_dump(mode="json")
    result["item_count"] = len(line_items)
    _record("report_summariser", result)
    return result


def main() -> None:
    """Serve the five tools over stdio."""
    logging.basicConfig(
        level=os.getenv("EXPENSE_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log.info("expense-compliance MCP server — 5 tools, offline, db=%s", _store().path)
    mcp.run()


if __name__ == "__main__":
    main()

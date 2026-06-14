"""Tool 4 — Duplicate Detector. Pure rules, NO LLM (SCOPING §4, §6.1, §8).

Unique key = (employee, receipt_datetime, final total). Detects:
  • EXACT_KEY        — same employee + receipt_datetime + total (block; DB unique index too)
  • NEAR_MATCH_WINDOW— same employee + total within ±duplicate_near_match_days
  • INTRA_SHEET      — duplicate line items within the same sheet being submitted
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from expense_core.schemas.enums import DuplicateRisk
from expense_core.schemas.tools import DuplicateMatch, DuplicateResult


class HistoricalLineItem(BaseModel):
    """A prior line item to compare against (from DB or the current sheet)."""

    model_config = ConfigDict(frozen=True)

    line_item_id: str
    employee_id: str
    receipt_datetime: datetime | None
    total: Decimal
    same_sheet: bool = False


class CandidateLineItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    employee_id: str
    receipt_datetime: datetime | None
    total: Decimal


def detect_duplicates(
    candidate: CandidateLineItem,
    history: list[HistoricalLineItem],
    *,
    near_match_days: int = 3,
) -> DuplicateResult:
    matches: list[DuplicateMatch] = []

    for h in history:
        if h.employee_id != candidate.employee_id:
            continue  # cross-employee dups are out of scope here (SCOPING §15 → route to human)

        reason = _classify_match(candidate, h, near_match_days)
        if reason:
            matches.append(
                DuplicateMatch(
                    line_item_id=h.line_item_id,
                    reason=reason,
                    receipt_datetime=h.receipt_datetime,
                    total=h.total,
                )
            )

    return _score(matches)


def _classify_match(
    c: CandidateLineItem, h: HistoricalLineItem, near_match_days: int
) -> str | None:
    if c.total != h.total:
        return None  # totals must match for any duplicate signal

    if h.same_sheet:
        return "INTRA_SHEET"

    if c.receipt_datetime is not None and h.receipt_datetime is not None:
        if c.receipt_datetime == h.receipt_datetime:
            return "EXACT_KEY"
        if abs(c.receipt_datetime - h.receipt_datetime) <= timedelta(days=near_match_days):
            return "NEAR_MATCH_WINDOW"
    elif c.receipt_datetime is None and h.receipt_datetime is None:
        return "EXACT_KEY"  # both undated + same total → treat as exact

    return None


def _score(matches: list[DuplicateMatch]) -> DuplicateResult:
    if not matches:
        return DuplicateResult(risk_score=0.0, risk=DuplicateRisk.NONE, matches=[])

    reasons = {m.reason for m in matches}
    if "EXACT_KEY" in reasons or "INTRA_SHEET" in reasons:
        return DuplicateResult(risk_score=1.0, risk=DuplicateRisk.HIGH, matches=matches)
    # Only near-matches.
    return DuplicateResult(risk_score=0.6, risk=DuplicateRisk.MEDIUM, matches=matches)

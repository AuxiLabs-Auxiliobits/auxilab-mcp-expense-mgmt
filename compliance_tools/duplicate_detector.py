"""Tool 4 — Duplicate Detector.

Screens a candidate line item against previously seen ones. Deterministic, no model.

The identity of an expense is ``(employee, receipt timestamp, total)``. Matching totals
are treated as a necessary condition for any duplicate signal — two different amounts are
two different expenses, however close together they were filed.

============================  ==============================================  ========
Reason                        Meaning                                         Risk
============================  ==============================================  ========
``EXACT_KEY``                 same employee, timestamp and total              HIGH
``INTRA_SHEET``               the same item claimed twice in one submission   HIGH
``NEAR_MATCH_WINDOW``         same employee and total, timestamps within N    MEDIUM
                              days of each other
============================  ==============================================  ========
"""

from __future__ import annotations

from datetime import timedelta

from compliance_tools.schemas import (
    CandidateLineItem,
    DuplicateMatch,
    DuplicateResult,
    DuplicateRisk,
    HistoricalLineItem,
)


def detect_duplicates(
    candidate: CandidateLineItem,
    history: list[HistoricalLineItem],
    *,
    near_match_days: int = 3,
) -> DuplicateResult:
    """Compare ``candidate`` against ``history`` and score the duplicate risk."""
    matches: list[DuplicateMatch] = []

    for prior in history:
        # Cross-employee duplicates are a different problem (shared receipts, expense
        # splitting) and need human review rather than an automated block.
        if prior.employee_id != candidate.employee_id:
            continue

        reason = _classify(candidate, prior, near_match_days)
        if reason:
            matches.append(
                DuplicateMatch(
                    line_item_id=prior.line_item_id,
                    reason=reason,
                    receipt_datetime=prior.receipt_datetime,
                    total=prior.total,
                )
            )

    return _score(matches)


def _classify(
    candidate: CandidateLineItem, prior: HistoricalLineItem, near_match_days: int
) -> str | None:
    if candidate.total != prior.total:
        return None  # totals must match for any duplicate signal

    if prior.same_sheet:
        return "INTRA_SHEET"

    candidate_at, prior_at = candidate.receipt_datetime, prior.receipt_datetime

    # Neither is dated: an identical total from the same employee is the strongest signal
    # available, so treat it as exact.
    if candidate_at is None and prior_at is None:
        return "EXACT_KEY"

    # Exactly one is dated — not enough in common to call it a duplicate.
    if candidate_at is None or prior_at is None:
        return None

    if candidate_at == prior_at:
        return "EXACT_KEY"
    if abs(candidate_at - prior_at) <= timedelta(days=near_match_days):
        return "NEAR_MATCH_WINDOW"
    return None


def _score(matches: list[DuplicateMatch]) -> DuplicateResult:
    if not matches:
        return DuplicateResult(risk_score=0.0, risk=DuplicateRisk.NONE, matches=[])

    reasons = {m.reason for m in matches}
    if reasons & {"EXACT_KEY", "INTRA_SHEET"}:
        return DuplicateResult(risk_score=1.0, risk=DuplicateRisk.HIGH, matches=matches)
    return DuplicateResult(risk_score=0.6, risk=DuplicateRisk.MEDIUM, matches=matches)

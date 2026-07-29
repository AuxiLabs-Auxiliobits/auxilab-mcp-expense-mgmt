"""Duplicate Detector — match classification, risk scoring, and what must NOT match."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from compliance_tools import detect_duplicates
from compliance_tools.schemas import CandidateLineItem, DuplicateRisk, HistoricalLineItem

DT = datetime(2026, 6, 1, 12, 0)


def candidate(**overrides) -> CandidateLineItem:
    base = {"employee_id": "emp-001", "receipt_datetime": DT, "total": Decimal("120.00")}
    base.update(overrides)
    return CandidateLineItem(**base)


def prior(**overrides) -> HistoricalLineItem:
    base = {
        "line_item_id": "li-001",
        "employee_id": "emp-001",
        "receipt_datetime": DT,
        "total": Decimal("120.00"),
    }
    base.update(overrides)
    return HistoricalLineItem(**base)


# --------------------------------------------------------------------------- #
# Positive detections
# --------------------------------------------------------------------------- #
def test_exact_key_is_high_risk():
    result = detect_duplicates(candidate(), [prior()])
    assert result.risk is DuplicateRisk.HIGH
    assert result.risk_score == 1.0
    assert result.matches[0].reason == "EXACT_KEY"


def test_intra_sheet_duplicate_is_high_risk():
    result = detect_duplicates(
        candidate(), [prior(receipt_datetime=datetime(2026, 5, 1), same_sheet=True)]
    )
    assert result.risk is DuplicateRisk.HIGH
    assert result.matches[0].reason == "INTRA_SHEET"


def test_near_match_inside_window_is_medium_risk():
    result = detect_duplicates(
        candidate(receipt_datetime=datetime(2026, 6, 4, 9, 0)), [prior()], near_match_days=3
    )
    assert result.risk is DuplicateRisk.MEDIUM
    assert result.risk_score == 0.6
    assert result.matches[0].reason == "NEAR_MATCH_WINDOW"


def test_two_undated_items_with_the_same_total_are_exact():
    result = detect_duplicates(candidate(receipt_datetime=None), [prior(receipt_datetime=None)])
    assert result.matches[0].reason == "EXACT_KEY"


# --------------------------------------------------------------------------- #
# Negative cases — the important half
# --------------------------------------------------------------------------- #
def test_empty_history_is_clean():
    result = detect_duplicates(candidate(), [])
    assert result.risk is DuplicateRisk.NONE
    assert result.matches == []


def test_different_total_is_never_a_duplicate():
    result = detect_duplicates(candidate(total=Decimal("120.01")), [prior()])
    assert result.risk is DuplicateRisk.NONE


def test_different_employee_is_ignored():
    """Cross-employee collisions are a separate problem and must not auto-flag."""
    result = detect_duplicates(candidate(), [prior(employee_id="emp-999")])
    assert result.risk is DuplicateRisk.NONE


def test_outside_the_near_match_window_is_clean():
    result = detect_duplicates(
        candidate(receipt_datetime=datetime(2026, 6, 10, 9, 0)), [prior()], near_match_days=3
    )
    assert result.risk is DuplicateRisk.NONE


def test_one_dated_one_undated_does_not_match():
    result = detect_duplicates(candidate(), [prior(receipt_datetime=None)])
    assert result.risk is DuplicateRisk.NONE


@pytest.mark.parametrize("days", [0, 1, 3, 7, 30])
def test_window_boundary_is_inclusive(days):
    from datetime import timedelta

    at_edge = DT + timedelta(days=days)
    result = detect_duplicates(candidate(receipt_datetime=at_edge), [prior()], near_match_days=days)
    assert result.risk is not DuplicateRisk.NONE


def test_just_outside_the_window_is_clean():
    from datetime import timedelta

    result = detect_duplicates(
        candidate(receipt_datetime=DT + timedelta(days=3, seconds=1)),
        [prior()],
        near_match_days=3,
    )
    assert result.risk is DuplicateRisk.NONE


# --------------------------------------------------------------------------- #
# Multiple matches
# --------------------------------------------------------------------------- #
def test_exact_match_outranks_near_matches():
    from datetime import timedelta

    history = [
        prior(line_item_id="li-near", receipt_datetime=DT + timedelta(days=2)),
        prior(line_item_id="li-exact"),
    ]
    result = detect_duplicates(candidate(), history)
    assert result.risk is DuplicateRisk.HIGH
    assert len(result.matches) == 2


def test_all_matches_are_reported():
    history = [prior(line_item_id=f"li-{i}") for i in range(4)]
    result = detect_duplicates(candidate(), history)
    assert {m.line_item_id for m in result.matches} == {"li-0", "li-1", "li-2", "li-3"}


# --------------------------------------------------------------------------- #
# Against the SQLite store
# --------------------------------------------------------------------------- #
def test_detects_the_seeded_duplicate_pair(seeded_store):
    """The demo dataset ships with a deliberate duplicate; it must be found."""
    history = seeded_store.history_for("emp-002")
    result = detect_duplicates(
        CandidateLineItem(
            employee_id="emp-002",
            receipt_datetime=datetime(2026, 6, 5, 7, 30),
            total=Decimal("42.50"),
        ),
        history,
    )
    assert result.risk is DuplicateRisk.HIGH


def test_a_novel_expense_is_clean_against_the_store(seeded_store):
    result = detect_duplicates(
        CandidateLineItem(
            employee_id="emp-002",
            receipt_datetime=datetime(2026, 6, 9, 9, 0),
            total=Decimal("19.99"),
        ),
        seeded_store.history_for("emp-002"),
    )
    assert result.risk is DuplicateRisk.NONE

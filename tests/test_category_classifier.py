"""Category Classifier — keyword coverage and the guardrails around model output."""

from __future__ import annotations

import pytest

from compliance_tools import classify_category
from compliance_tools.schemas import Category


@pytest.mark.parametrize(
    ("description", "merchant", "expected"),
    [
        ("Airport transfer", "Uber", Category.TRAVEL_GROUND),
        ("Ride to the office", "Lyft", Category.TRAVEL_GROUND),
        ("Airport parking", "SFO Parking", Category.TRAVEL_GROUND),
        ("2 nights downtown", "Marriott", Category.TRAVEL_HOTEL),
        ("Weekend stay", "Airbnb", Category.TRAVEL_HOTEL),
        ("JFK to LAX", "Delta Airlines", Category.TRAVEL_AIR),
        ("Checked baggage fee", "United", Category.TRAVEL_AIR),
        ("Team lunch", "Noodle House", Category.MEALS_ENTERTAINMENT),
        ("Morning coffee", "Blue Bottle Cafe", Category.MEALS_ENTERTAINMENT),
        ("Copilot annual subscription", "GitHub", Category.SOFTWARE_SUBSCRIPTIONS),
        ("Conference wi-fi access", "Boingo", Category.SOFTWARE_SUBSCRIPTIONS),
        ("Annual license renewal", "Atlassian", Category.SOFTWARE_SUBSCRIPTIONS),
        ("Printer paper", "Staples", Category.OFFICE_SUPPLIES),
        ("Client theatre tickets", "Ticketmaster", Category.CLIENT_ENTERTAINMENT),
    ],
)
def test_keyword_classification(description, merchant, expected):
    result = classify_category(description, merchant)
    assert result.category is expected
    assert result.confidence >= 0.9
    assert result.rationale


def test_unknown_expense_defaults_to_other_with_low_confidence():
    result = classify_category("Blue widget", "AcmeCo")
    assert result.category is Category.OTHER
    assert result.confidence < 0.5


def test_ground_transport_wins_over_air_for_airport_parking():
    """'Airport parking' contains 'airport' — it must not be classed as air travel."""
    assert classify_category("Airport parking", "SFO").category is Category.TRAVEL_GROUND


def test_classification_is_case_insensitive():
    lower = classify_category("airport transfer", "uber")
    upper = classify_category("AIRPORT TRANSFER", "UBER")
    assert lower.category is upper.category


def test_empty_input_is_other_not_an_error():
    assert classify_category("", "").category is Category.OTHER


def test_classification_is_deterministic():
    first = classify_category("Team lunch", "Noodle House")
    second = classify_category("Team lunch", "Noodle House")
    assert first == second


# --------------------------------------------------------------------------- #
# The LLM seam
# --------------------------------------------------------------------------- #
class _StubLLM:
    def __init__(self, response: str) -> None:
        self.response = response

    def complete(self, messages, *, temperature=0.0, max_tokens=1024) -> str:
        return self.response

    @property
    def model_version(self) -> str:
        return "stub-1"


def test_valid_llm_response_is_used():
    llm = _StubLLM('{"category": "Office Supplies", "confidence": 0.81, "rationale": "model"}')
    result = classify_category("Blue widget", "AcmeCo", llm=llm)
    assert result.category is Category.OFFICE_SUPPLIES
    assert result.confidence == pytest.approx(0.81)


def test_hallucinated_category_cannot_escape_the_enum():
    """A model inventing a category must not produce one — fall back to keywords."""
    llm = _StubLLM('{"category": "Cryptocurrency", "confidence": 0.99, "rationale": "nope"}')
    result = classify_category("Team lunch", "Noodle House", llm=llm)
    assert result.category is Category.MEALS_ENTERTAINMENT


@pytest.mark.parametrize(
    "response",
    ["", "not json", "{}", '{"category": "Other"}', '{"category": "Other", "confidence": "high"}'],
)
def test_unusable_llm_responses_fall_back(response):
    result = classify_category("Airport transfer", "Uber", llm=_StubLLM(response))
    assert result.category is Category.TRAVEL_GROUND


def test_out_of_range_confidence_is_rejected():
    llm = _StubLLM('{"category": "Office Supplies", "confidence": 5.0, "rationale": "x"}')
    result = classify_category("Team lunch", "Noodle House", llm=llm)
    assert result.category is Category.MEALS_ENTERTAINMENT

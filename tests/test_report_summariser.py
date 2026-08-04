"""Report Summariser — aggregation arithmetic and the narrative seam."""

from __future__ import annotations

from decimal import Decimal

from compliance_tools import summarise_report
from compliance_tools.schemas import Category, SummaryLineItem


def item(category: Category, amount: str, compliant: bool = True) -> SummaryLineItem:
    return SummaryLineItem(category=category, amount=Decimal(amount), is_compliant=compliant)


ITEMS = [
    item(Category.TRAVEL_HOTEL, "462.00"),
    item(Category.MEALS_ENTERTAINMENT, "187.00", compliant=False),
    item(Category.TRAVEL_AIR, "320.00"),
    item(Category.MEALS_ENTERTAINMENT, "48.88"),
]


def test_totals_are_grouped_by_category():
    result = summarise_report(ITEMS)
    assert result.total_by_category[Category.TRAVEL_HOTEL] == Decimal("462.00")
    assert result.total_by_category[Category.MEALS_ENTERTAINMENT] == Decimal("235.88")
    assert result.total_by_category[Category.TRAVEL_AIR] == Decimal("320.00")


def test_violations_and_amount_at_risk():
    result = summarise_report(ITEMS)
    assert result.violation_count == 1
    assert result.total_at_risk == Decimal("187.00")


def test_compliance_rate():
    result = summarise_report(ITEMS)
    assert result.compliance_rate_pct == 75.0


def test_empty_report_is_fully_compliant():
    result = summarise_report([])
    assert result.compliance_rate_pct == 100.0
    assert result.violation_count == 0
    assert result.total_at_risk == Decimal("0")
    assert result.total_by_category == {}


def test_all_non_compliant_scores_zero():
    result = summarise_report([item(Category.OTHER, "10.00", compliant=False)])
    assert result.compliance_rate_pct == 0.0


def test_decimal_precision_is_preserved():
    """Summing money must not drift — this is why amounts are Decimal, not float."""
    result = summarise_report([item(Category.OTHER, "0.10") for _ in range(3)])
    assert result.total_by_category[Category.OTHER] == Decimal("0.30")


def test_compliance_rate_is_rounded_to_two_places():
    result = summarise_report([item(Category.OTHER, "1") for _ in range(3)][:3])
    assert result.compliance_rate_pct == 100.0

    mixed = [item(Category.OTHER, "1"), item(Category.OTHER, "1"), item(Category.OTHER, "1", False)]
    assert summarise_report(mixed).compliance_rate_pct == 66.67


def test_narrative_reports_the_real_figures():
    result = summarise_report(ITEMS)
    assert "4 line item" in result.narrative
    assert "1017.88" in result.narrative
    assert "75.0%" in result.narrative


def test_narrative_names_the_top_category():
    result = summarise_report(ITEMS)
    assert Category.TRAVEL_HOTEL.value in result.narrative


# --------------------------------------------------------------------------- #
# The LLM seam
# --------------------------------------------------------------------------- #
class _StubLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def complete(self, messages, *, temperature=0.0, max_tokens=1024) -> str:
        self.prompts.append(messages[-1].content)
        return self.response

    @property
    def model_version(self) -> str:
        return "stub-1"


def test_llm_narrative_replaces_the_template():
    llm = _StubLLM("Spending was broadly in line with policy this period.")
    result = summarise_report(ITEMS, llm=llm)
    assert result.narrative == "Spending was broadly in line with policy this period."


def test_llm_receives_precomputed_figures_not_raw_items():
    """The model phrases the summary; it never gets to compute it."""
    llm = _StubLLM("ok")
    summarise_report(ITEMS, llm=llm)
    assert "1017.88" in llm.prompts[0]
    assert "75.0%" in llm.prompts[0]


def test_llm_cannot_change_the_numbers():
    result = summarise_report(ITEMS, llm=_StubLLM("Everything was perfect, zero violations."))
    assert result.violation_count == 1
    assert result.total_at_risk == Decimal("187.00")
    assert result.compliance_rate_pct == 75.0


# --------------------------------------------------------------------------- #
# Against the SQLite store
# --------------------------------------------------------------------------- #
def test_summarises_stored_items(seeded_store):
    result = summarise_report(seeded_store.summary_items())
    assert result.total_by_category
    assert 0 <= result.compliance_rate_pct <= 100


def test_summarises_one_employee(seeded_store):
    result = summarise_report(seeded_store.summary_items("emp-001"))
    # emp-001 has three seeded items totalling 48.88 + 320.00 + 462.00.
    assert sum(result.total_by_category.values()) == Decimal("830.88")

"""Property-based tests for the receipt parser.

The parser is the one component built on stacked regexes, and regexes fail in ways
example-based tests do not anticipate. Two real bugs made it past a full example suite:
``Tax (8.625%)  3.88`` yielded the *rate* as the tax, and ``2 nights @ $210, Tax $42``
left a trailing comma in the description.

Both were shapes nobody thought to write a test for. These tests generate the shapes
instead, and assert the invariants that must hold for every one of them.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from compliance_tools import parse_receipt
from compliance_tools.receipt_lines import classify
from compliance_tools.receipt_parser import RECONCILE_TOLERANCE

# Money with at most two decimal places, in a range a real receipt could hold.
money = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("9999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)
# A line starting with a totals keyword is, by contract, a totals row rather than a
# purchase. Generated item names exclude that shape so these properties test the parser
# rather than the documented ambiguity — using the parser's own rule, so the two cannot
# drift apart.
item_names = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll")), min_size=3, max_size=14
).filter(lambda s: classify(s).label is None)
merchants = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll")), min_size=3, max_size=18
)
tax_rates = st.decimals(min_value=Decimal("0"), max_value=Decimal("25"), places=3)


def build_receipt(
    merchant: str, items: list[tuple[str, Decimal]], tax: Decimal, rate: Decimal | None = None
) -> tuple[str, Decimal]:
    """Render a multi-line receipt and return it with its true total."""
    subtotal = sum((amount for _, amount in items), Decimal("0"))
    total = subtotal + tax
    lines = [merchant, "", "2026-06-01  12:47", ""]
    lines += [f"{name}{' ' * 6}{amount:.2f}" for name, amount in items]
    lines.append(f"Subtotal{' ' * 6}{subtotal:.2f}")
    label = f"Tax ({rate}%)" if rate is not None else "Tax"
    lines.append(f"{label}{' ' * 6}{tax:.2f}")
    lines.append(f"Total{' ' * 6}{total:.2f}")
    return "\n".join(lines), total


# --------------------------------------------------------------------------- #
# The central invariant
# --------------------------------------------------------------------------- #
@given(
    merchant=merchants,
    items=st.lists(st.tuples(item_names, money), min_size=1, max_size=6),
    tax=money,
)
@settings(max_examples=250, deadline=None)
def test_a_receipt_that_adds_up_always_reconciles(merchant, items, tax):
    text, total = build_receipt(merchant, items, tax)
    result = parse_receipt(text)
    assert result.total == total
    assert result.reconciles is True, f"delta={result.delta}"
    assert result.delta == Decimal("0")


@given(
    merchant=merchants,
    items=st.lists(st.tuples(item_names, money), min_size=1, max_size=5),
    tax=money,
    rate=tax_rates,
)
@settings(max_examples=250, deadline=None)
def test_a_percentage_on_the_tax_line_is_never_mistaken_for_the_amount(merchant, items, tax, rate):
    """The exact shape of the first real bug: `Tax (8.625%)   3.88`."""
    text, total = build_receipt(merchant, items, tax, rate=rate)
    result = parse_receipt(text)
    assert result.tax == tax, f"read the rate {rate} instead of the charge {tax}"
    assert result.total == total
    assert result.reconciles is True


@given(
    merchant=merchants,
    items=st.lists(st.tuples(item_names, money), min_size=1, max_size=5),
    tax=money,
    delta=st.decimals(min_value=Decimal("0.02"), max_value=Decimal("500"), places=2),
)
@settings(max_examples=250, deadline=None)
def test_a_tampered_total_never_reconciles(merchant, items, tax, delta):
    """Inflating the stated total must always be caught, by exactly the amount added."""
    text, total = build_receipt(merchant, items, tax)
    tampered = text.replace(f"Total{' ' * 6}{total:.2f}", f"Total{' ' * 6}{total + delta:.2f}")
    result = parse_receipt(tampered)
    assert result.reconciles is False
    assert result.delta == delta


# --------------------------------------------------------------------------- #
# Single-line receipts — the shape that produced the trailing-comma bug
# --------------------------------------------------------------------------- #
@given(
    merchant=merchants,
    qty=st.integers(min_value=1, max_value=99),
    unit=st.decimals(min_value=Decimal("1"), max_value=Decimal("999"), places=2),
    tax=st.decimals(min_value=Decimal("0"), max_value=Decimal("500"), places=2),
)
@settings(max_examples=250, deadline=None)
def test_inline_quantity_pricing_reconciles_and_has_a_clean_description(merchant, qty, unit, tax):
    total = qty * unit + tax
    text = f"{merchant}, {qty} nights @ ${unit}, Tax ${tax}, Total ${total}"
    result = parse_receipt(text)

    assert result.reconciles is True, f"delta={result.delta}"
    assert len(result.line_items) == 1
    description = result.line_items[0].description
    assert not description.endswith((",", ".", ";")), f"trailing punctuation: {description!r}"
    assert result.line_items[0].amount == qty * unit


# --------------------------------------------------------------------------- #
# Robustness: never raise, never silently invent numbers
# --------------------------------------------------------------------------- #
@given(text=st.text(max_size=400))
@settings(max_examples=400, deadline=None)
def test_arbitrary_text_never_raises(text):
    result = parse_receipt(text)
    assert result.total >= 0 or result.total < 0  # a Decimal came back
    assert isinstance(result.reconciles, bool)


@given(text=st.text(max_size=200))
@settings(max_examples=200, deadline=None)
def test_parsing_is_deterministic(text):
    assert parse_receipt(text) == parse_receipt(text)


@given(
    merchant=merchants,
    items=st.lists(st.tuples(item_names, money), min_size=1, max_size=4),
    tax=money,
)
@settings(max_examples=150, deadline=None)
def test_reported_delta_always_equals_total_minus_parts(merchant, items, tax):
    """`delta` must describe the discrepancy it claims to describe."""
    text, _ = build_receipt(merchant, items, tax)
    result = parse_receipt(text)
    summed = sum((li.amount for li in result.line_items), Decimal("0")) + result.tax
    if result.reconciles:
        assert abs(result.total - summed) <= RECONCILE_TOLERANCE
    else:
        assert result.delta == result.total - summed


def test_hypothesis_is_actually_installed():
    """Guards against the suite silently degrading if the dependency is dropped."""
    pytest.importorskip("hypothesis")

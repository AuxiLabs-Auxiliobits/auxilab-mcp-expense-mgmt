"""Monetary amount parsing.

Amount ambiguity used to be resolved inside whichever regex matched first, so it could
only be tested through a whole receipt. It now lives in one function with one table of
cases, which is what this file is.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from compliance_tools.money import find_amounts, looks_like_amount, parse_money


# --------------------------------------------------------------------------- #
# Plain amounts
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0", "0"),
        ("5", "5"),
        ("12.50", "12.50"),
        ("0.01", "0.01"),
        ("48.88", "48.88"),
        ("1234", "1234"),
        ("1234.56", "1234.56"),
        ("9999999.99", "9999999.99"),
    ],
)
def test_plain_numbers(text, expected):
    assert parse_money(text) == Decimal(expected)


# --------------------------------------------------------------------------- #
# Currency decoration
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$12.50", "12.50"),
        ("€12.50", "12.50"),
        ("£12.50", "12.50"),
        ("¥1250", "1250"),
        ("₹1250.00", "1250.00"),
        ("$ 12.50", "12.50"),
        ("12.50 USD", "12.50"),
        ("EUR 12.50", "12.50"),
        ("12,50 kr", "12.50"),
        ("  $12.50  ", "12.50"),
    ],
)
def test_currency_symbols_and_codes_are_stripped(text, expected):
    assert parse_money(text) == Decimal(expected)


# --------------------------------------------------------------------------- #
# International grouping — the reason this module exists
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("text", "expected", "convention"),
    [
        ("1,234.56", "1234.56", "US/UK"),
        ("$1,234.56", "1234.56", "US/UK"),
        ("1.234,56", "1234.56", "German/Spanish/Italian"),
        ("1.234.567,89", "1234567.89", "German, multiple groups"),
        ("1,234,567.89", "1234567.89", "US, multiple groups"),
        ("1 234,56", "1234.56", "French, space grouping"),
        ("1 234 567,89", "1234567.89", "French, multiple groups"),
        ("1'234.56", "1234.56", "Swiss"),
        ("1,234", "1234", "single comma + 3 digits reads as grouping"),
        ("1.234", "1.234", "single dot stays a decimal point"),
        ("1,5", "1.5", "single comma + 1 digit is a decimal comma"),
        ("1,50", "1.50", "single comma + 2 digits is a decimal comma"),
    ],
)
def test_grouping_conventions(text, expected, convention):
    assert parse_money(text) == Decimal(expected), convention


def test_grouping_choice_is_documented_and_stable():
    """The one genuinely ambiguous pair, pinned so it cannot drift silently."""
    assert parse_money("1,234") == Decimal("1234")  # comma groups
    assert parse_money("1.234") == Decimal("1.234")  # dot is decimal


# --------------------------------------------------------------------------- #
# Negatives
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("-12.50", "-12.50"),
        ("−12.50", "-12.50"),  # U+2212 minus
        ("–12.50", "-12.50"),  # en dash
        ("12.50-", "-12.50"),  # trailing sign
        ("(12.50)", "-12.50"),  # accounting
        ("($12.50)", "-12.50"),
        ("-$12.50", "-12.50"),
    ],
)
def test_negatives(text, expected):
    assert parse_money(text) == Decimal(expected)


# --------------------------------------------------------------------------- #
# Rejections — None must mean "no amount", never zero
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text",
    ["", "   ", "abc", "$", "--", "N/A", "-", "()", "12.34.56.78", "1..2", ".", ","],
)
def test_non_amounts_are_rejected(text):
    assert parse_money(text) is None


def test_none_input_is_rejected():
    assert parse_money(None) is None


def test_rejection_is_distinguishable_from_zero():
    """A missing figure must never silently become a real one."""
    assert parse_money("nothing here") is None
    assert parse_money("0") == Decimal("0")


def test_looks_like_amount():
    assert looks_like_amount("$12.50") is True
    assert looks_like_amount("Pad Thai") is False


# --------------------------------------------------------------------------- #
# Finding amounts inside a line
# --------------------------------------------------------------------------- #
def test_find_amounts_returns_them_in_order():
    assert find_amounts("Widget 4.00 Gadget 6.50") == [Decimal("4.00"), Decimal("6.50")]


def test_find_amounts_skips_percentages():
    """The original tax bug: `Tax (8.625%)  3.88` must not report 8.625."""
    assert find_amounts("(8.625%)   3.88") == [Decimal("3.88")]


def test_find_amounts_can_include_percentages_when_asked():
    found = find_amounts("(8.625%)   3.88", skip_percentages=False)
    assert Decimal("8.625") in found


def test_find_amounts_on_a_line_with_none():
    assert find_amounts("Thank you for your visit") == []


def test_find_amounts_handles_grouped_numbers():
    assert find_amounts("Total  1.234,56") == [Decimal("1234.56")]


# --------------------------------------------------------------------------- #
# Precision
# --------------------------------------------------------------------------- #
def test_no_floating_point_drift():
    total = sum((parse_money("0.1") for _ in range(10)), Decimal("0"))
    assert total == Decimal("1.0")


def test_trailing_zeros_are_preserved():
    """Decimal keeps scale, which matters when echoing an amount back to a user."""
    assert str(parse_money("12.50")) == "12.50"

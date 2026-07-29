"""Line classification.

Every parser bug so far came from two regexes disagreeing about what a piece of text was.
Classification now happens once per line, which means it can be tested once per line —
these are the cases that used to be reachable only through a whole receipt.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from compliance_tools.receipt_lines import LineKind, classify, normalise, scan


def kind_of(text: str) -> LineKind:
    return classify(text).kind


# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #
def test_blank_lines_are_dropped():
    assert normalise("A\n\n\n   \nB") == ["A", "B"]


def test_lines_are_stripped():
    assert normalise("   A   \n  B  ") == ["A", "B"]


def test_carriage_returns_are_handled():
    assert normalise("A\r\nB\rC") == ["A", "B", "C"]


def test_tabs_become_a_gutter():
    """A tab is how a lot of exported text renders the amount column."""
    assert classify(normalise("Widget\t12.00")[0]).kind is LineKind.ITEM


@pytest.mark.parametrize("space", [" ", " ", " "])
def test_unicode_spaces_are_folded(space):
    """PDF text layers are full of these; untreated they defeat every gutter rule."""
    line = normalise(f"Widget{space}{space}12.00")[0]
    assert classify(line).kind is LineKind.ITEM


def test_single_line_receipts_are_split_on_separator_commas():
    assert normalise("Shop, Tax $2.00, Total $22.00") == ["Shop", "Tax $2.00", "Total $22.00"]


def test_thousands_separators_do_not_split_a_single_line():
    """`$1,250` must survive the comma split intact."""
    assert normalise("Hire, 2 rooms @ $1,250, Total $2500") == [
        "Hire",
        "2 rooms @ $1,250",
        "Total $2500",
    ]


def test_commas_in_a_multi_line_receipt_are_punctuation():
    lines = normalise("SHOP\n123 Main St, San Francisco\nTotal 5.00")
    assert "123 Main St, San Francisco" in lines


# --------------------------------------------------------------------------- #
# Labels — the ordered rule that decides most lines
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Subtotal      45.00", LineKind.SUBTOTAL),
        ("Sub total     45.00", LineKind.SUBTOTAL),
        ("Sub-Total     45.00", LineKind.SUBTOTAL),
        ("Total         48.88", LineKind.TOTAL),
        ("TOTAL         48.88", LineKind.TOTAL),
        ("Grand Total   48.88", LineKind.TOTAL),
        ("Amount Due    48.88", LineKind.TOTAL),
        ("Balance Due   48.88", LineKind.TOTAL),
        ("Tax            3.88", LineKind.TAX),
        ("VAT           10.00", LineKind.TAX),
        ("GST            5.00", LineKind.TAX),
        ("Sales Tax      3.88", LineKind.TAX),
        ("VISA ****-4321", LineKind.SETTLEMENT),
        ("Mastercard ****-9911", LineKind.SETTLEMENT),
        ("Cash          50.00", LineKind.SETTLEMENT),
        ("Change         1.12", LineKind.SETTLEMENT),
        ("Thank you for your visit", LineKind.NOISE),
        ("Server: Alice", LineKind.NOISE),
        ("Order #12345", LineKind.NOISE),
    ],
)
def test_label_rows(text, expected):
    assert kind_of(text) is expected


def test_subtotal_wins_over_total():
    """'Subtotal' contains 'total'; longest-first ordering decides it."""
    line = classify("Subtotal   45.00")
    assert line.kind is LineKind.SUBTOTAL
    assert line.label == "subtotal"


def test_label_amount_is_extracted():
    assert classify("Total      48.88").amount == Decimal("48.88")


def test_tax_line_reports_the_charge_not_the_rate():
    """The original bug, now a one-line test instead of a whole-receipt one."""
    line = classify("Tax (8.625%)   3.88")
    assert line.kind is LineKind.TAX
    assert line.amount == Decimal("3.88")


def test_a_label_with_no_amount_has_none():
    line = classify("Thank you for your visit")
    assert line.amount is None


# --------------------------------------------------------------------------- #
# False positives — purchases that only look like totals rows
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "item",
    [
        "Postcard",  # contains "card"
        "Cardamom Tea",  # starts with "card" but not on a boundary
        "Taxi Receipt Book",  # starts with "tax" but not on a boundary
        "Taxidermy Kit",
        "Cashew Nuts",  # starts with "cash"
        "Ordinary Soap",  # starts with "ord"
        "Totally Ordinary Thing",  # starts with "total" but not on a boundary
        "Reference Book",  # starts with "ref"
        "Tellurium Sample",  # starts with "tel"
    ],
)
def test_purchases_that_resemble_labels_are_still_items(item):
    assert kind_of(f"{item}          10.00") is LineKind.ITEM


@pytest.mark.parametrize("item", ["Total Recall DVD", "Tax Guide 2026", "Change Purse"])
def test_a_whole_word_label_at_the_start_is_a_totals_row(item):
    """Documented ambiguity: on a real receipt these read as totals rows."""
    assert kind_of(f"{item}          10.00") is not LineKind.ITEM


# --------------------------------------------------------------------------- #
# Items
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("text", "description", "amount"),
    [
        ("Pad Thai (x2)          18.00", "Pad Thai (x2)", "18.00"),
        ("Widget..................4.50", "Widget", "4.50"),
        ("Coffee   $3.50", "Coffee", "3.50"),
        ("Espresso 3.50", "Espresso", "3.50"),
        ("Imported Cheese   12,50", "Imported Cheese", "12.50"),
        ("Bulk order   1,250.00", "Bulk order", "1250.00"),
        ("Refund item   -5.00", "Refund item", "-5.00"),
        ("Discount   (2.00)", "Discount", "-2.00"),
    ],
)
def test_item_shapes(text, description, amount):
    line = classify(text)
    assert line.kind is LineKind.ITEM
    assert line.description == description
    assert line.amount == Decimal(amount)


def test_ocr_collapsed_gutter_is_still_an_item():
    """OCR routinely reduces a column of spaces to one; rejecting that loses purchases."""
    line = classify("Sparkling Water 5.50")
    assert line.kind is LineKind.ITEM
    assert line.amount == Decimal("5.50")


def test_a_single_space_without_decimals_is_not_an_item():
    """'Aisle 5 3' should not be read as a purchase — too weak a signal."""
    assert kind_of("Aisle 5 3") is not LineKind.ITEM


def test_a_bare_amount_is_not_a_purchase():
    assert kind_of("12.00      3.00") is not LineKind.ITEM


def test_quantity_priced_items_multiply_out():
    line = classify("2 nights @ $210")
    assert line.kind is LineKind.ITEM
    assert line.amount == Decimal("420")
    assert line.description == "2 nights @ $210"


def test_quantity_priced_item_is_not_claimed_by_the_gutter_rule():
    """`3 rooms @ $99.00` is 297, not 99 — classification order matters."""
    assert classify("3 rooms @ $99.00").amount == Decimal("297.00")


def test_an_email_address_is_not_a_quantity_price():
    assert kind_of("Contact: alice@example.com") is LineKind.NOISE


# --------------------------------------------------------------------------- #
# Dates
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text",
    ["2026-06-01", "2026-06-01  12:47", "06/14/2026", "14.06.2026", "12:47", "12:47:31 PM"],
)
def test_date_and_time_lines(text):
    assert kind_of(text) is LineKind.DATE


def test_a_time_beside_money_is_not_a_date_line():
    """A line carrying an amount is a transaction, whatever else is on it."""
    assert kind_of("Delivery 18:00 slot     4.50") is LineKind.ITEM


# --------------------------------------------------------------------------- #
# Whole-document scan
# --------------------------------------------------------------------------- #
RECEIPT = """NOODLE HOUSE
123 Main St, San Francisco

2026-06-01  12:47

Pad Thai (x2)          18.00
Green Curry            14.50
Subtotal               32.50
Tax (8.625%)            2.80
Total                  35.30

VISA  ****-4321
Thank you for your visit"""


def test_scan_marks_the_merchant():
    lines = scan(RECEIPT)
    merchants = [line for line in lines if line.kind is LineKind.MERCHANT]
    assert len(merchants) == 1
    assert merchants[0].text == "NOODLE HOUSE"


def test_scan_classifies_every_line_exactly_once():
    lines = scan(RECEIPT)
    assert len(lines) == len(normalise(RECEIPT))
    assert all(isinstance(line.kind, LineKind) for line in lines)


def test_scan_finds_the_expected_structure():
    kinds = [line.kind for line in scan(RECEIPT)]
    assert kinds.count(LineKind.ITEM) == 2
    assert kinds.count(LineKind.SUBTOTAL) == 1
    assert kinds.count(LineKind.TAX) == 1
    assert kinds.count(LineKind.TOTAL) == 1
    assert kinds.count(LineKind.SETTLEMENT) == 1


def test_scan_is_inspectable():
    """`scan` is the debugging entry point; its lines must render readably."""
    rendered = [str(line) for line in scan(RECEIPT)]
    assert any("total" in line and "35.30" in line for line in rendered)


def test_scan_of_empty_text():
    assert scan("") == []

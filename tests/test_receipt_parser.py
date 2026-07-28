"""Receipt Parser — extraction shapes and, above all, the reconciliation maths."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from compliance_tools import parse_receipt
from compliance_tools.llm import ChatMessage
from compliance_tools.receipt_parser import parse_receipt_file, read_text

MULTILINE = """NOODLE HOUSE
123 Main St, San Francisco

2026-06-01  12:47

Pad Thai (x2)          18.00
Green Curry            14.50
Diet Coke (x2)          7.00
Sparkling Water         5.50
Subtotal               45.00
Tax (8.625%)            3.88
Total                  48.88

VISA  ****-4321
"""

SINGLE_LINE = "Marriott Hotels, 2 nights @ $210, Tax $42, Total $462"


# --------------------------------------------------------------------------- #
# Multi-line printed receipts
# --------------------------------------------------------------------------- #
def test_multiline_receipt_reconciles():
    result = parse_receipt(MULTILINE)
    assert result.total == Decimal("48.88")
    assert result.tax == Decimal("3.88")
    assert result.reconciles is True
    assert result.delta == Decimal("0")


def test_multiline_merchant_and_metadata():
    result = parse_receipt(MULTILINE)
    assert result.merchant == "NOODLE HOUSE"
    assert result.payment_method == "VISA"


def test_timestamp_survives_padding_between_date_and_time():
    """Printed receipts pad the gap: '2026-06-01  12:47'."""
    assert parse_receipt(MULTILINE).receipt_datetime == datetime(2026, 6, 1, 12, 47)


def test_bare_date_does_not_absorb_a_time_from_the_next_line():
    result = parse_receipt("Shop\n\n2026-06-01\n12:47 is not the receipt time\nTotal 10.00")
    assert result.receipt_datetime == datetime(2026, 6, 1, 0, 0)


def test_us_style_slash_date():
    result = parse_receipt("Shop\n\n06/14/2026\nWidget   10.00\nTotal    10.00")
    assert result.receipt_datetime == datetime(2026, 6, 14, 0, 0)


@pytest.mark.parametrize(
    "item",
    [
        "Postcard",
        "Cardamom Tea",
        "Ordinary Soap",
        "Taxi Receipt Book",
        "Taxidermy Kit",
        "Cashew Nuts",
    ],
)
def test_items_that_only_look_like_totals_rows_are_kept(item):
    """A label counts only at the start of the line *and* on a word boundary.

    Substring matching dropped 'Postcard' (contains 'card'); bare prefix matching dropped
    'Cardamom Tea' and 'Taxi Receipt Book'. Each time a real purchase vanished and the
    receipt stopped reconciling with nothing to explain it. Found by the property tests.
    """
    receipt = f"Corner Shop\n\n{item}          10.00\nTax            0.00\nTotal          10.00"
    result = parse_receipt(receipt)
    assert [li.description for li in result.line_items] == [item]
    assert result.reconciles is True


@pytest.mark.parametrize(
    "item", ["Total Recall DVD", "Tax Guide 2026", "Balance Board", "Change Purse Strap"]
)
def test_a_purchase_named_exactly_like_a_totals_row_is_still_treated_as_one(item):
    """The documented ambiguity, pinned so it stays deliberate.

    A line beginning with the whole word 'Total', 'Tax' or 'Balance' reads as a totals row
    on any real receipt, so it is skipped. Documented in the README troubleshooting.
    """
    receipt = f"Shop\n\n{item}          10.00\nTax            0.00\nTotal          10.00"
    assert [li.description for li in parse_receipt(receipt).line_items] != [item]


def test_genuine_totals_rows_are_still_skipped():
    receipt = (
        "Shop\n\nWidget          6.00\nGadget          4.00\n"
        "Subtotal       10.00\nTax             1.00\nTotal          11.00\nVISA ****-1234"
    )
    result = parse_receipt(receipt)
    assert [li.description for li in result.line_items] == ["Widget", "Gadget"]
    assert result.reconciles is True


def test_line_items_exclude_subtotal_tax_and_total():
    result = parse_receipt(MULTILINE)
    descriptions = [li.description for li in result.line_items]
    assert descriptions == ["Pad Thai (x2)", "Green Curry", "Diet Coke (x2)", "Sparkling Water"]
    assert sum(li.amount for li in result.line_items) == Decimal("45.00")


# --------------------------------------------------------------------------- #
# Single-line summaries
# --------------------------------------------------------------------------- #
def test_single_line_quantity_pricing_reconciles():
    result = parse_receipt(SINGLE_LINE)
    assert result.merchant.startswith("Marriott")
    assert result.total == Decimal("462")
    assert result.tax == Decimal("42")
    assert result.reconciles is True


def test_quantity_description_does_not_swallow_the_separator():
    """'2 nights @ $210, Tax ...' must not leave a trailing comma in the description."""
    result = parse_receipt(SINGLE_LINE)
    assert len(result.line_items) == 1
    assert result.line_items[0].description == "2 nights @ $210"
    assert result.line_items[0].amount == Decimal("420")


def test_thousands_separator_in_a_unit_price_is_kept():
    result = parse_receipt("Venue Hire, 2 rooms @ $1,250, Tax $0, Total $2500")
    assert result.line_items[0].amount == Decimal("2500")
    assert result.reconciles is True


# --------------------------------------------------------------------------- #
# The point of the tool: catching arithmetic that doesn't add up
# --------------------------------------------------------------------------- #
def test_altered_total_is_caught():
    tampered = MULTILINE.replace("Total                  48.88", "Total                  58.88")
    result = parse_receipt(tampered)
    assert result.reconciles is False
    assert result.delta == Decimal("10.00")


def test_missing_line_item_is_caught():
    short = MULTILINE.replace("Green Curry            14.50\n", "")
    result = parse_receipt(short)
    assert result.reconciles is False
    assert result.delta == Decimal("14.50")


def test_rounding_within_a_cent_still_reconciles():
    receipt = "Cafe\n\nEspresso                 3.33\nTax                      0.00\nTotal   3.34"
    result = parse_receipt(receipt)
    assert result.reconciles is True


def test_two_cents_out_does_not_reconcile():
    receipt = "Cafe\n\nEspresso                 3.33\nTax                      0.00\nTotal   3.35"
    result = parse_receipt(receipt)
    assert result.reconciles is False


# --------------------------------------------------------------------------- #
# Degenerate input must not raise
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text", ["", "   ", "no numbers at all", "!!!"])
def test_unparseable_input_returns_zeroed_result(text):
    result = parse_receipt(text)
    assert result.total == Decimal("0")
    assert result.reconciles is True  # 0 == 0


def test_receipt_without_itemisation_synthesises_a_line():
    result = parse_receipt("Corner Shop, Tax $2.00, Total $22.00")
    assert result.reconciles is True
    assert len(result.line_items) == 1
    assert result.line_items[0].amount == Decimal("20.00")


# --------------------------------------------------------------------------- #
# The LLM seam
# --------------------------------------------------------------------------- #
class _StubLLM:
    """Stands in for a model, returning whatever the test wants."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[list[ChatMessage]] = []

    def complete(self, messages, *, temperature=0.0, max_tokens=1024) -> str:
        self.calls.append(messages)
        return self.response

    @property
    def model_version(self) -> str:
        return "stub-1"


def test_llm_output_is_used_when_valid():
    llm = _StubLLM(
        '{"merchant": "From Model", "receipt_datetime": "2026-06-01T12:47:00", '
        '"total": 48.88, "tax": 3.88, "line_items": [{"description": "Meal", "amount": 45.00}], '
        '"payment_method": "VISA"}'
    )
    result = parse_receipt(MULTILINE, llm=llm)
    assert result.merchant == "From Model"
    assert llm.calls, "the model should have been consulted"


def test_malformed_llm_output_falls_back_to_regex():
    result = parse_receipt(MULTILINE, llm=_StubLLM("not json at all"))
    assert result.merchant == "NOODLE HOUSE"
    assert result.reconciles is True


def test_llm_arithmetic_is_never_trusted():
    """A model claiming a receipt balances cannot make it balance."""
    llm = _StubLLM(
        '{"merchant": "Fraud Inc", "receipt_datetime": null, "total": 999.00, "tax": 0, '
        '"line_items": [{"description": "Widget", "amount": 1.00}], "payment_method": null}'
    )
    result = parse_receipt("anything", llm=llm)
    assert result.reconciles is False
    assert result.delta == Decimal("998.00")


# --------------------------------------------------------------------------- #
# Filesystem input
# --------------------------------------------------------------------------- #
def test_reads_text_file(tmp_path):
    path = tmp_path / "receipt.txt"
    path.write_text(MULTILINE, encoding="utf-8")
    assert parse_receipt_file(path).total == Decimal("48.88")


def test_reads_bundled_sample_receipt():
    from pathlib import Path

    sample = Path(__file__).resolve().parent.parent / "demo" / "sample_receipt.txt"
    if not sample.exists():  # pragma: no cover - samples are generated
        pytest.skip("run demo/generate_samples.py first")
    assert parse_receipt_file(sample).reconciles is True


def test_reads_bundled_sample_pdf():
    from pathlib import Path

    pytest.importorskip("pypdf")
    sample = Path(__file__).resolve().parent.parent / "demo" / "sample_receipt.pdf"
    if not sample.exists():  # pragma: no cover - samples are generated
        pytest.skip("run demo/generate_samples.py first")
    text = read_text(sample)
    assert "NOODLE HOUSE" in text
    assert parse_receipt(text).total == Decimal("48.88")


# --------------------------------------------------------------------------- #
# File validation — fail loudly, never return empty text that reads as a $0 receipt
# --------------------------------------------------------------------------- #
def test_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError, match="No receipt file"):
        read_text(tmp_path / "nope.txt")


def test_directory_is_not_a_receipt(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_text(tmp_path)


@pytest.mark.parametrize("suffix", [".exe", ".zip", ".png", ".sqlite", ""])
def test_unsupported_file_types_are_rejected(tmp_path, suffix):
    path = tmp_path / f"receipt{suffix}"
    path.write_bytes(b"anything")
    with pytest.raises(ValueError, match="as a receipt"):
        read_text(path)


@pytest.mark.parametrize("suffix", [".txt", ".text", ".md"])
def test_supported_text_types_are_accepted(tmp_path, suffix):
    path = tmp_path / f"receipt{suffix}"
    path.write_text("Shop, Total $5.00", encoding="utf-8")
    assert "Shop" in read_text(path)


def test_extension_check_is_case_insensitive(tmp_path):
    path = tmp_path / "receipt.TXT"
    path.write_text("Shop, Total $5.00", encoding="utf-8")
    assert "Shop" in read_text(path)


def test_oversized_file_is_refused(tmp_path, monkeypatch):
    import compliance_tools.receipt_parser as parser

    monkeypatch.setattr(parser, "MAX_RECEIPT_BYTES", 32)
    path = tmp_path / "big.txt"
    path.write_text("x" * 200, encoding="utf-8")
    with pytest.raises(ValueError, match="over the"):
        read_text(path)


def test_undecodable_bytes_do_not_crash(tmp_path):
    """Replacement decoding beats an exception on a slightly mangled receipt."""
    path = tmp_path / "receipt.txt"
    path.write_bytes(b"Caf\xe9 Noir\n\nEspresso  3.00\nTax  0.00\nTotal  3.00")
    assert parse_receipt(read_text(path)).total == Decimal("3.00")

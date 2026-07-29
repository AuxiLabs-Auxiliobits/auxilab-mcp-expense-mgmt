"""Turning receipt text into classified lines.

The parser used to be a stack of regexes applied to the whole document: one to find the
tax, one to find the total, one to find items, each scanning independently and each able
to match text another had already claimed. Every bug it produced came from that overlap —
the tax pattern matching a percentage inside a label, an item pattern swallowing a list
separator, a label matching in the middle of a purchase name.

This module replaces that with one decision per line:

    normalise  ->  classify each line  ->  extract its amount

A line is exactly one :class:`LineKind`. Nothing else re-reads the document. That makes
the parser's behaviour inspectable — ``scan(text)`` shows you precisely how every line was
understood — and makes each rule testable on its own, rather than only through the
end-to-end result.

The classification is ordered, and the order is the specification:

1. A **label** at the start of a line, ending on a word boundary — ``Total``, ``Tax``,
   ``VISA``. This is checked first because a totals row can otherwise look exactly like a
   purchase.
2. A **date or time**.
3. A **purchase**: a description, a gutter, and an amount at the end of the line.
4. Anything else is **noise**.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum

from compliance_tools.money import AMOUNT_PATTERN, find_amounts, parse_money


class LineKind(StrEnum):
    """What a line of a receipt turned out to be."""

    MERCHANT = "merchant"
    DATE = "date"
    ITEM = "item"  # a purchased thing, or any charge that adds to the total
    SUBTOTAL = "subtotal"
    TAX = "tax"
    TOTAL = "total"
    SETTLEMENT = "settlement"  # how it was paid: card, cash tendered, change given
    NOISE = "noise"


#: Labels that begin a line and determine its kind. Ordered longest-first within each
#: group so "sub total" is tested before "total" and wins.
#:
#: Charges that add to the total (tip, gratuity, service, delivery) are deliberately NOT
#: here — they are purchases as far as the arithmetic is concerned, and excluding them
#: made a receipt with a tip fail to reconcile.
_LABELS: tuple[tuple[str, LineKind], ...] = (
    ("sub-total", LineKind.SUBTOTAL),
    ("sub total", LineKind.SUBTOTAL),
    ("subtotal", LineKind.SUBTOTAL),
    ("grand total", LineKind.TOTAL),
    ("amount due", LineKind.TOTAL),
    ("balance due", LineKind.TOTAL),
    ("total due", LineKind.TOTAL),
    ("total", LineKind.TOTAL),
    ("sales tax", LineKind.TAX),
    ("tax", LineKind.TAX),
    ("vat", LineKind.TAX),
    ("gst", LineKind.TAX),
    ("hst", LineKind.TAX),
    ("pst", LineKind.TAX),
    ("american express", LineKind.SETTLEMENT),
    ("mastercard", LineKind.SETTLEMENT),
    ("discover", LineKind.SETTLEMENT),
    ("amex", LineKind.SETTLEMENT),
    ("visa", LineKind.SETTLEMENT),
    ("debit", LineKind.SETTLEMENT),
    ("credit", LineKind.SETTLEMENT),
    ("cash", LineKind.SETTLEMENT),
    ("card", LineKind.SETTLEMENT),
    ("tendered", LineKind.SETTLEMENT),
    ("change", LineKind.SETTLEMENT),
    ("balance", LineKind.SETTLEMENT),
    ("payment", LineKind.SETTLEMENT),
    ("thank you", LineKind.NOISE),
    ("merchant id", LineKind.NOISE),
    ("terminal", LineKind.NOISE),
    ("invoice", LineKind.NOISE),
    ("receipt", LineKind.NOISE),
    ("server", LineKind.NOISE),
    ("order", LineKind.NOISE),
    ("table", LineKind.NOISE),
    ("auth", LineKind.NOISE),
    ("ref", LineKind.NOISE),
    ("tel", LineKind.NOISE),
)

#: One alternation, longest-first, anchored at the start and closed on a word boundary.
#: The boundary is what keeps "Cardamom Tea" and "Taxi Receipt Book" from being read as
#: totals rows, and the anchor is what keeps "Postcard" from matching "card".
_LABEL_MATCH = re.compile(
    r"\s*(?P<label>" + "|".join(re.escape(text) for text, _ in _LABELS) + r")\b",
    re.IGNORECASE,
)
_LABEL_KINDS = dict(_LABELS)

#: Payment brands, recognised anywhere in a settlement line.
_PAYMENT_BRANDS = (
    "american express",
    "mastercard",
    "discover",
    "amex",
    "visa",
    "debit",
    "cash",
)

#: "2 nights @ $210" — a quantity times a unit price. Recognised during classification
#: rather than as a post-hoc fallback, so a quantity-priced line is decided once like any
#: other item and cannot be claimed first by the gutter rules below, which would report
#: the unit price as the line total.
_ITEM_QUANTITY_PRICED = re.compile(
    r"(?P<qty>\d+)\s*(?P<unit>[A-Za-z ]{0,20}?)\s*@\s*[$€£¥₹]?\s*"
    r"(?P<price>\d+(?:,\d{3})*(?:[.,]\d+)?)"
)

#: A purchase line: description, gutter, amount at the end.
#:
#: Two gutters are accepted. Two or more spaces or dots is the classic printed layout. A
#: single space is accepted only when the amount is unmistakably money — a currency symbol
#: or exactly two decimal places — because OCR frequently collapses the gutter, and
#: rejecting those lines silently loses real purchases.
_ITEM_WIDE_GUTTER = re.compile(r"^(?P<description>.+?)[\s.]{2,}(?P<amount>\S+)$")
_ITEM_TIGHT_GUTTER = re.compile(
    r"^(?P<description>.+?\S)\s(?P<amount>[(\-−–]?\s*[$€£¥₹]?\s*"
    r"(?:\d{1,3}(?:[ .,']\d{3})+|\d+)[.,]\d{2}\s*[-−–)]?)$"
)

#: Commas that separate facts rather than group thousands. A comma followed by exactly
#: three digits belongs to the number ("$1,250") and must not split the line.
_SEPARATOR_COMMA = re.compile(r",(?!\d{3}(?:\D|$))")

_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_NUMERIC_DATE = re.compile(r"\b\d{1,2}[/.]\d{1,2}[/.]\d{2,4}\b")
_CLOCK = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp]\.?[Mm]\.?)?\b")


@dataclass(frozen=True, slots=True)
class ClassifiedLine:
    """A single line of a receipt and what it was understood to be.

    A dataclass rather than a pydantic model on purpose. Everything crossing a public
    boundary in this project is validated by pydantic, but this is internal plumbing: the
    values are produced by the classifier a few lines above, never by a caller, so there
    is nothing to validate. One model instance per line also measurably slowed a long
    receipt down, and a receipt can have hundreds of lines.
    """

    index: int
    text: str
    kind: LineKind
    label: str | None = None
    amount: Decimal | None = None
    description: str | None = None

    def __str__(self) -> str:  # pragma: no cover - debugging aid
        money = "" if self.amount is None else f" = {self.amount}"
        return f"[{self.index:>3}] {self.kind.value:<10} {self.text!r}{money}"


def normalise(text: str) -> list[str]:
    """Split into stripped, non-empty lines with unicode whitespace folded to spaces.

    Non-breaking and narrow spaces come out of PDFs constantly; left alone they defeat
    every gutter and grouping rule downstream.
    """
    folded = text.replace(" ", " ").replace(" ", " ").replace(" ", " ")
    folded = folded.replace("\t", "  ").replace("\r", "\n")
    lines = [line.strip() for line in folded.split("\n") if line.strip()]

    # A receipt written on one line is split on its commas, turning the single-line
    # shape into the same line-per-fact structure as a printed receipt so that one
    # classifier handles both. Commas in a multi-line receipt are left alone: there
    # they are punctuation ("123 Main St, San Francisco"), not separators.
    if len(lines) == 1 and "," in lines[0]:
        return [part.strip() for part in _SEPARATOR_COMMA.split(lines[0]) if part.strip()]

    return lines


def classify(text: str, index: int = 0) -> ClassifiedLine:
    """Decide what one line is. See the module docstring for the rule order."""
    label_match = _LABEL_MATCH.match(text)
    if label_match:
        label = label_match.group("label").lower()
        kind = _LABEL_KINDS[label]
        remainder = text[label_match.end() :]
        return ClassifiedLine(
            index=index,
            text=text,
            kind=kind,
            label=label,
            amount=_amount_after_label(remainder),
            description=_payment_brand(text) if kind is LineKind.SETTLEMENT else None,
        )

    if _looks_like_date(text):
        return ClassifiedLine(index=index, text=text, kind=LineKind.DATE)

    item = _as_item(text)
    if item is not None:
        description, amount = item
        return ClassifiedLine(
            index=index,
            text=text,
            kind=LineKind.ITEM,
            amount=amount,
            description=description,
        )

    return ClassifiedLine(index=index, text=text, kind=LineKind.NOISE)


def scan(text: str) -> list[ClassifiedLine]:
    """Classify every line of a receipt, marking the merchant.

    The merchant is the first line that carries no amount, no label and no date — which on
    a printed receipt is the shop's name at the top.
    """
    lines = [classify(line, index) for index, line in enumerate(normalise(text))]

    for line in lines:
        if line.kind is LineKind.NOISE and line.amount is None:
            lines[line.index] = replace(line, kind=LineKind.MERCHANT)
            break

    return lines


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #
def _amount_after_label(remainder: str) -> Decimal | None:
    """The charge on a labelled line, ignoring any rate printed alongside it.

    ``Tax (8.625%)   3.88`` must yield 3.88. Percentages are skipped, and the *first*
    surviving amount wins — a trailing running-balance column would otherwise take over.
    """
    amounts = find_amounts(remainder, skip_percentages=True)
    return amounts[0] if amounts else None


def _payment_brand(text: str) -> str | None:
    lowered = text.lower()
    for brand in _PAYMENT_BRANDS:
        if brand in lowered:
            return brand.upper()
    return None


def _looks_like_date(text: str) -> bool:
    """A line whose content is a timestamp rather than a transaction."""
    if _ISO_DATE.search(text) or _NUMERIC_DATE.search(text):
        return True
    # A bare clock time on its own line, with nothing that looks like money beside it.
    return bool(_CLOCK.search(text)) and not find_amounts(_CLOCK.sub("", text))


def _as_item(text: str) -> tuple[str, Decimal] | None:
    """A purchase line, as ``(description, amount)``, or ``None``."""
    quantity_priced = _ITEM_QUANTITY_PRICED.search(text)
    if quantity_priced:
        price = parse_money(quantity_priced.group("price"))
        if price is not None:
            return quantity_priced.group(0).strip(), int(quantity_priced.group("qty")) * price

    for pattern in (_ITEM_WIDE_GUTTER, _ITEM_TIGHT_GUTTER):
        match = pattern.match(text)
        if not match:
            continue
        amount = parse_money(match.group("amount"))
        if amount is None:
            continue
        description = match.group("description").strip(" .")
        if description and not _is_only_an_amount(description):
            return description, amount
    return None


def _is_only_an_amount(text: str) -> bool:
    """Guards against reading ``12.00  3.00`` as a purchase called '12.00'."""
    stripped = AMOUNT_PATTERN.sub("", text).strip(" .$€£¥₹")
    return not stripped

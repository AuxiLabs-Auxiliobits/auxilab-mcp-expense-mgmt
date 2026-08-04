"""Parsing monetary amounts out of text.

Receipts are printed by thousands of different systems in dozens of locales, so an amount
arrives in more shapes than a single regex should be asked to hold:

===================  ==========  ==================================================
Written              Value       Convention
===================  ==========  ==================================================
``$1,234.56``        1234.56     US/UK — comma groups, dot decimal
``1.234,56 €``       1234.56     German/Spanish/Italian — dot groups, comma decimal
``1 234,56``         1234.56     French — space groups, comma decimal
``1'234.56``         1234.56     Swiss — apostrophe groups
``(12.50)``          -12.50      accounting negative
``12.50-``           -12.50      trailing-sign negative
``8.625%``           rejected    a rate, not an amount
===================  ==========  ==================================================

Separating this out means the ambiguity gets resolved in one place, against a table of
cases, instead of inside whichever regex happened to match first.

**The one genuinely ambiguous case** is a single separator followed by exactly three
digits: ``1,234`` is 1234 to an American and 1.234 to a German. We resolve it the way the
previous implementation did — a comma groups thousands, a dot is a decimal point — so
existing behaviour is preserved. A locale-aware parser is out of scope for a tool with no
locale to read.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

#: Symbols stripped before parsing. Currency *codes* (USD, EUR) are stripped as letters.
CURRENCY_SYMBOLS = "$€£¥₹₩₽¢"

#: Separators that group thousands. Includes the space characters typesetters use.
_GROUPING = " .,'   "

#: A bare number with optional grouping and an optional fractional part. The first branch
#: requires at least one grouping separator followed by exactly three digits, which is what
#: distinguishes "1,234" from "1,23".
_NUMBER = (
    r"\d{1,3}(?:[ .,'   ]\d{3})+(?:[.,]\d{1,2})?"
    r"|\d+(?:[.,]\d+)?"
)

#: A money token: optional sign or bracket, optional symbol, the number, optional trailing
#: sign or bracket. Used to find amounts inside a line.
AMOUNT_PATTERN = re.compile(
    rf"(?P<open>\()?\s*(?P<lead>[-−–])?\s*[{re.escape(CURRENCY_SYMBOLS)}]?\s*"
    rf"(?P<number>{_NUMBER})"
    rf"\s*(?P<trail>[-−–])?\s*(?P<close>\))?"
)

#: A percentage immediately following a number — "8.625%" is a rate, never a charge.
_PERCENT_SUFFIX = re.compile(r"\s*%")


def looks_like_amount(text: str) -> bool:
    """True when ``text`` is entirely a monetary amount."""
    return parse_money(text) is not None


def parse_money(text: str) -> Decimal | None:
    """Parse a monetary amount, or return ``None`` when the text is not one.

    Returning ``None`` rather than zero matters: a caller must be able to tell "no amount
    here" from "an amount of nothing", or a missing figure silently becomes a real one.
    """
    if text is None:
        return None

    cleaned = _strip_decoration(str(text))
    if not cleaned:
        return None

    negative = _is_negative(str(text), cleaned)
    # Strip both ends: accounting layouts put the sign after the number ("12.50-").
    digits = cleaned.strip("+-")

    if not re.fullmatch(rf"(?:{_NUMBER})", digits):
        return None

    try:
        value = Decimal(_to_plain_decimal(digits))
    except (InvalidOperation, ValueError):
        return None

    return -value if negative else value


def find_amounts(line: str, *, skip_percentages: bool = True) -> list[Decimal]:
    """Every monetary amount in ``line``, left to right.

    Percentages are skipped by default, which is what stops ``Tax (8.625%)  3.88`` from
    reporting the rate as the charge.
    """
    found: list[Decimal] = []
    for match in AMOUNT_PATTERN.finditer(line):
        if skip_percentages and _PERCENT_SUFFIX.match(line, match.end()):
            continue
        value = parse_money(match.group(0))
        if value is not None:
            found.append(value)
    return found


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #
def _strip_decoration(text: str) -> str:
    """Remove currency symbols, codes, brackets and stray unicode punctuation."""
    text = unicodedata.normalize("NFKC", text).strip()
    text = text.replace("−", "-").replace("–", "-")  # minus, en dash
    for symbol in CURRENCY_SYMBOLS:
        text = text.replace(symbol, "")
    text = re.sub(r"[A-Za-z]", "", text)  # currency codes: USD, EUR, kr
    text = text.replace("(", "").replace(")", "")
    return text.strip().strip("+")


def _is_negative(original: str, cleaned: str) -> bool:
    """Accounting brackets, a leading minus, or a trailing minus."""
    original = original.strip()
    if original.startswith("(") and original.endswith(")"):
        return True
    return cleaned.startswith("-") or cleaned.endswith("-")


def _to_plain_decimal(digits: str) -> str:
    """Normalise grouped digits into something ``Decimal`` accepts.

    The decimal separator is whichever of ``.`` or ``,`` appears last, unless only one
    kind is present — then the rules in the module docstring apply.
    """
    digits = digits.rstrip("-").strip()
    for space in (" ", " ", " ", " ", "'"):
        digits = digits.replace(space, "")

    last_dot = digits.rfind(".")
    last_comma = digits.rfind(",")

    if last_dot >= 0 and last_comma >= 0:
        # Both present: the rightmost is the decimal point, the other groups thousands.
        if last_comma > last_dot:
            return digits.replace(".", "").replace(",", ".")
        return digits.replace(",", "")

    if last_comma >= 0:
        # A comma groups thousands when it is repeated, or when exactly three digits
        # follow it — "1,234" is 1234. Otherwise it is a decimal comma: "1,5" is 1.5.
        if digits.count(",") > 1 or len(digits) - last_comma - 1 == 3:
            return digits.replace(",", "")
        return digits.replace(",", ".")

    if last_dot >= 0 and digits.count(".") > 1:
        # "1.234.567" can only be grouped thousands.
        return digits.replace(".", "")

    return digits

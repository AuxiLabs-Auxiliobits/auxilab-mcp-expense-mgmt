"""Fixed value sets + input validators shared by DTOs and routers.

- **Expense types** are the canonical engine categories (incl. "Other", which on the client
  reveals a free-text field stored in `line_item.expense_type_other`).
- **Currencies** are the supported transaction currencies the UI prepopulates and the server
  validates against.
- **Receipt files** follow the SCOPING §4.2 allow-list + 25 MB cap.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import PurePosixPath

from expense_core.schemas.enums import Category

# Expense Type value set (the 8 engine categories). "Other" → free-text on the client.
EXPENSE_TYPES: list[str] = [c.value for c in Category]

# Supported transaction currencies (ISO 4217). Extend as finance onboards regions.
SUPPORTED_CURRENCIES: tuple[str, ...] = (
    "USD", "EUR", "GBP", "INR", "CAD", "AUD", "JPY", "SGD", "AED",
)

# Receipt upload constraints (SCOPING §4.2).
ALLOWED_RECEIPT_EXTENSIONS: frozenset[str] = frozenset(
    {".pdf", ".jpeg", ".jpg", ".heic", ".png", ".docx", ".doc"}
)
MAX_RECEIPT_BYTES: int = 25 * 1024 * 1024  # 25 MB

_PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def normalize_currency(code: str) -> str:
    """Upper-case and validate against the supported list; raises ValueError if unsupported."""
    norm = code.strip().upper()
    if norm not in SUPPORTED_CURRENCIES:
        raise ValueError(f"unsupported currency '{code}'; expected one of {list(SUPPORTED_CURRENCIES)}")
    return norm


def validate_period(period: str) -> str:
    """Expense period is 'YYYY-MM' and must fall in the current year (SCOPING change req)."""
    if not _PERIOD_RE.match(period):
        raise ValueError("period must be in 'YYYY-MM' format")
    if int(period[:4]) != date.today().year:
        raise ValueError(f"period must be within the current year ({date.today().year})")
    return period


def receipt_extension(filename: str) -> str:
    """Return the lower-cased extension and assert it is allowed (rejects spoof-free name only;
    MIME/magic-byte checks happen in the ingestion worker)."""
    ext = PurePosixPath(filename).suffix.lower()
    if ext not in ALLOWED_RECEIPT_EXTENSIONS:
        raise ValueError(
            f"unsupported receipt type '{ext or filename}'; allowed: "
            f"{sorted(ALLOWED_RECEIPT_EXTENSIONS)}"
        )
    return ext

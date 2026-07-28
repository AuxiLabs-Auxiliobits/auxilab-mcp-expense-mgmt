"""Fixed value sets + input validators shared by DTOs and routers.

- **Expense types** are the canonical engine categories (incl. "Other", which on the client
  reveals a free-text field stored in `line_item.expense_type_other`).
- **Currencies** are the supported transaction currencies the UI prepopulates and the server
  validates against.
- **Receipt files** follow the SCOPING §4.2 allow-list + 25 MB cap.
"""

from __future__ import annotations

import calendar
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


def period_window(today: date | None = None) -> list[str]:
    """Selectable expense periods: the current month plus the previous 11, newest first.

    e.g. today = 2026-01 → ['2026-01', '2025-12', ..., '2025-02'] (12 entries). Single source
    of truth for the periods API and `validate_period`."""
    today = today or date.today()
    out: list[str] = []
    year, month = today.year, today.month
    for _ in range(12):
        out.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    return out


def period_label(value: str) -> str:
    """'2026-01' → 'Jan 2026'."""
    year, month = int(value[:4]), int(value[5:7])
    return f"{calendar.month_abbr[month]} {year}"


def validate_period(period: str) -> str:
    """Period is 'YYYY-MM' and must fall within the rolling last-12-months window."""
    if not _PERIOD_RE.match(period):
        raise ValueError("period must be in 'YYYY-MM' format")
    if period not in set(period_window()):
        raise ValueError("period must be within the last 12 months")
    return period


def receipt_extension(filename: str) -> str:
    """Return the lower-cased extension and assert it is allowed."""
    ext = PurePosixPath(filename).suffix.lower()
    if ext not in ALLOWED_RECEIPT_EXTENSIONS:
        raise ValueError(
            f"unsupported receipt type '{ext or filename}'; allowed: "
            f"{sorted(ALLOWED_RECEIPT_EXTENSIONS)}"
        )
    return ext


# Leading-byte signatures per type we can fingerprint. Types we don't (heic/webp variants) are
# normalized at storage (convert_heic_to_jpeg), so they pass through and re-check once jpeg.
_MAGIC: dict[str, list[bytes]] = {
    ".pdf": [b"%PDF"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".gif": [b"GIF87a", b"GIF89a"],
}


def verify_receipt_magic(ext: str, data: bytes) -> None:
    """Reject a spoofed extension by confirming the file's leading bytes match the claimed type
    (security: S-M2). A `.pdf`-named HTML/executable is refused before storage. Empty files are
    rejected; un-fingerprinted (but allowed) types pass through."""
    if not data:
        raise ValueError("empty file")
    expected = _MAGIC.get(ext)
    if expected is None:
        return
    head = data[:16]
    if not any(head.startswith(sig) for sig in expected):
        raise ValueError(f"file content does not match its '{ext}' extension")

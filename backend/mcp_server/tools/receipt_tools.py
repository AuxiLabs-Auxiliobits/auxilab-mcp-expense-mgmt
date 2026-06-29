"""Receipt parsing, classification, and duplicate detection MCP tools."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.database.db import get_db, row_to_dict, rows_to_dicts
import os
import pytesseract
tesseract_path = os.getenv("TESSERACT_CMD", "tesseract")
pytesseract.pytesseract.tesseract_cmd = tesseract_path

# ---------------------------------------------------------------------------
# FIX #3 — Expanded to exactly 8 standard categories as per build brief
# ---------------------------------------------------------------------------
CATEGORY_RULES: list[dict[str, Any]] = [
    {
        "key": "meals_entertainment",
        "display": "Meals & Entertainment",
        "confidence": 0.95,
        "keywords": [
            "zomato", "swiggy", "mcdonald", "dominos", "pizza", "kfc", "burger",
            "restaurant", "cafe", "bistro", "diner", "food", "eat", "dining",
            "starbucks", "subway", "hotel dining",
        ],
    },
    {
        "key": "travel_air",
        "display": "Travel - Air",
        "confidence": 0.95,
        "keywords": [
            "indigo", "air india", "spicejet", "vistara", "delta", "united",
            "american airlines", "emirates", "flight", "airways", "airline", "airfare",
        ],
    },
    {
        "key": "travel_ground",
        "display": "Travel - Ground",
        "confidence": 0.95,
        "keywords": [
            "uber", "ola", "lyft", "auto", "taxi", "cab", "metro", "bus",
            "rapido", "rickshaw", "transfer", "shuttle", "train", "railway",
        ],
    },
    {
        "key": "travel_hotel",
        "display": "Travel - Hotel",
        "confidence": 0.95,
        "keywords": [
            "marriott", "hilton", "hyatt", "taj", "oberoi", "oyo", "holiday inn",
            "sheraton", "westin", "hotel", "inn", "lodge", "resort", "accommodation",
        ],
    },
    
    {
        "key": "office_supplies",
        "display": "Office Supplies",
        "confidence": 0.90,
        "keywords": [
            "office", "stationery", "supplies", "staples", "paper", "pen",
            "printer", "ink", "toner", "folder", "notebook",
        ],
    },
    {
        "key": "software_subscriptions",
        "display": "Software/Subscriptions",
        "confidence": 0.92,
        "keywords": [
            "zoom", "slack", "microsoft", "google workspace", "aws", "azure",
            "github", "jira", "notion", "adobe", "saas", "subscription",
            "software", "license", "cloud", "api", "hosting",
        ],
    },
    {
        "key": "client_entertainment",
        "display": "Client Entertainment",
        "confidence": 0.88,
        "keywords": [
            "client dinner", "client lunch", "client meeting", "client entertainment",
            "business dinner", "business lunch", "entertainment", "event", "concert",
            "sports ticket", "golf",
        ],
    },
    {
        "key": "other",
        "display": "Other",
        "confidence": 0.30,
        "keywords": [],  # fallback — matched last
    },
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _amount_to_float(value: str, *, fix_currency_ocr_prefix: bool = False) -> float:
    """Convert an OCR amount string to float, correcting common rupee-symbol noise."""
    cleaned = value.strip()
    if fix_currency_ocr_prefix and re.match(r"^[23]\d,\d{3}(?:\.\d+)?$", cleaned):
        cleaned = cleaned[1:]
    return float(cleaned.replace(",", ""))


def _parse_amount(text: str) -> float | None:
    """Extract total amount from OCR text."""
    patterns = [
        r"total[:\s]*□\s*([\d,]+\.?\d*)",
        r"grand\s+total[:\s]*(?:\$|₹|□)?\s*([\d,]+(?:\.\d+)?)",
        r"net\s+payable[:\s]*(?:\$|₹|□)?\s*([\d,]+(?:\.\d+)?)",
        r"bill\s+amount[:\s]*(?:\$|₹|□)?\s*([\d,]+(?:\.\d+)?)",
        r"total[:\s]*(?:\$|₹|□)?\s*([\d,]+(?:\.\d+)?)",
        r"amount[:\s]*(?:\$|₹|□)?\s*([\d,]+(?:\.\d+)?)",
        r"□\s*([\d,]+\.?\d*)",
        r"(?:\$|₹|□)\s*([\d,]+\.\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _amount_to_float(match.group(1), fix_currency_ocr_prefix=True)
    amounts = re.findall(r"(?:\$|₹|□)?\s*([\d,]+\.\d{2})", text)
    if amounts:
        return _amount_to_float(amounts[-1])
    return None


def _parse_tax(text: str) -> float | None:
    """FIX #2 — Extract tax amount from OCR text."""
    patterns = [
        r"tax[:\s]*(?:\$|₹|□)?\s*([\d,]+(?:\.\d+)?)",
        r"gst[:\s]*(?:\$|₹|□)?\s*([\d,]+(?:\.\d+)?)",
        r"vat[:\s]*(?:\$|₹|□)?\s*([\d,]+(?:\.\d+)?)",
        r"service\s+tax[:\s]*(?:\$|₹|□)?\s*([\d,]+(?:\.\d+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", ""))
    return None


def _parse_payment_method(text: str) -> str | None:
    """FIX #2 — Extract payment method from receipt text."""
    methods = {
        "cash": ["cash"],
        "credit_card": ["credit card", "credit", "visa", "mastercard", "amex", "american express"],
        "debit_card": ["debit card", "debit"],
        "upi": ["upi", "gpay", "phonepe", "paytm", "google pay"],
        "wallet": ["corporate wallet", "wallet"],
        "net_banking": ["net banking", "neft", "imps"],
    }
    text_lower = text.lower()
    for method, keywords in methods.items():
        if any(kw in text_lower for kw in keywords):
            return method
    return None


def _parse_date(text: str) -> str | None:
    """Extract a date from OCR text."""
    patterns = [
        r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
        r"(\d{4}[/\-]\d{1,2}[/\-]\d{1,2})",
        r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _parse_merchant(text: str) -> str:
    """Extract merchant name from first non-empty lines of OCR text."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return "Unknown Merchant"
    skip = {"receipt", "invoice", "thank you", "welcome"}
    for line in lines[:5]:
        if line.lower() not in skip and not re.match(r"^\d", line):
            return line[:80]
    return lines[0][:80]


def _parse_line_items(text: str) -> list[dict[str, Any]]:
    """Extract line items from receipt text."""
    items: list[dict[str, Any]] = []
    for line in text.splitlines():
        match = re.match(r"^(.+?)\s+\$?\s*([\d,]+\.\d{2})\s*$", line.strip())
        if match:
            desc = match.group(1).strip()
            if desc.lower() not in ("total", "subtotal", "tax", "tip", "amount", "gst", "vat"):
                items.append({
                    "description": desc,
                    "amount": float(match.group(2).replace(",", "")),
                })
    return items


def _reconciliation_errors(
    line_items: list[dict[str, Any]],
    total: float | None,
    tax: float | None,
) -> list[str]:
    """
    FIX #2 — Return a list of reconciliation error strings (empty = no errors).
    Checks: line_items + tax == total
    """
    errors: list[str] = []
    if not line_items or total is None:
        return errors

    items_sum = round(sum(float(i["amount"]) for i in line_items), 2)
    tax_amount = round(float(tax), 2) if tax is not None else 0.0
    expected_total = round(items_sum + tax_amount, 2)

    if abs(expected_total - round(float(total), 2)) > 0.01:
        errors.append(
            f"Line items (${items_sum:.2f}) + tax (${tax_amount:.2f}) = "
            f"${expected_total:.2f} but stated total is ${total:.2f}."
        )
    return errors


def _read_embedded_receipt(path: Path) -> dict[str, Any] | None:
    """Read structured receipt data from a PNG text chunk, if present."""
    try:
        from PIL import Image
        with Image.open(path) as img:
            raw = img.info.get("tripsense_receipt")
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# FIX #2 — parse_receipt now returns tax, total, payment_method,
#           reconciliation_errors (list) instead of reconciliation_flag (bool)
# ---------------------------------------------------------------------------

def parse_receipt(image_path: str) -> dict[str, Any]:
    """
    Parse a receipt image and extract structured expense details.

    Args:
        image_path: Path to the receipt image file OR raw receipt text
                    prefixed with 'text:' for direct text input.

    Returns:
        merchant, date, total, tax, line_items, payment_method,
        ocr_confidence, reconciliation_errors (list).
    """
    # Support direct text input for demo/testing: parse_receipt("text: Marriott ...")
    if isinstance(image_path, str) and image_path.startswith("text:"):
        text = image_path[5:].strip()
        return _parse_from_text(text, ocr_confidence=1.0)

    path = Path(image_path)
    if not path.exists():
        return {
            "error": f"Image not found: {image_path}",
            "merchant": None,
            "date": None,
            "total": None,
            "tax": None,
            "line_items": [],
            "payment_method": None,
            "ocr_confidence": 0.0,
            "reconciliation_errors": ["Receipt file not found."],
        }

    embedded = _read_embedded_receipt(path)
    if embedded is not None:
        line_items = embedded.get("line_items", [])
        total = embedded.get("amount") or embedded.get("total")
        tax = embedded.get("tax")
        return {
            "merchant": embedded.get("merchant"),
            "date": embedded.get("date") or datetime.utcnow().strftime("%Y-%m-%d"),
            "total": total,
            "tax": tax,
            "line_items": line_items,
            "payment_method": embedded.get("payment_method"),
            "ocr_confidence": embedded.get("ocr_confidence", 0.95),
            "reconciliation_errors": _reconciliation_errors(line_items, total, tax),
        }

    try:
        import pytesseract
        from PIL import Image as PILImage

        img = PILImage.open(path)
        ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        confidences = [int(c) for c in ocr_data["conf"] if int(c) > 0]
        avg_confidence = round(sum(confidences) / len(confidences) / 100, 3) if confidences else 0.5
        text = pytesseract.image_to_string(img)
    except ImportError:
        text = path.stem.replace("_", " ").replace("-", " ")
        avg_confidence = 0.3
    except Exception as exc:
        return {
            "error": str(exc),
            "merchant": None,
            "date": None,
            "total": None,
            "tax": None,
            "line_items": [],
            "payment_method": None,
            "ocr_confidence": 0.0,
            "reconciliation_errors": [f"OCR error: {exc}"],
        }

    return _parse_from_text(text, ocr_confidence=avg_confidence)


def _parse_from_text(text: str, ocr_confidence: float = 1.0) -> dict[str, Any]:
    """Internal: parse all fields from raw receipt text."""
    merchant = _parse_merchant(text)
    date = _parse_date(text) or datetime.utcnow().strftime("%Y-%m-%d")
    total = _parse_amount(text)
    tax = _parse_tax(text)
    line_items = _parse_line_items(text)
    payment_method = _parse_payment_method(text)

    return {
        "merchant": merchant,
        "date": date,
        "total": total,
        "tax": tax,
        "line_items": line_items,
        "payment_method": payment_method,
        "ocr_confidence": ocr_confidence,
        "reconciliation_errors": _reconciliation_errors(line_items, total, tax),
        "raw_text_preview": text[:500] if text else "",
    }


# ---------------------------------------------------------------------------
# FIX #3 — classify_spend_category now maps to exactly 8 standard categories
# ---------------------------------------------------------------------------

def classify_spend_category(
    merchant_name: str,
    description: str = "",
) -> dict[str, Any]:
    """
    Classify an expense into one of 8 standard categories.

    Categories: Meals & Entertainment, Travel - Air, Travel - Hotel,
    Travel - Ground, Office Supplies, Software/Subscriptions,
    Client Entertainment, Other.

    Args:
        merchant_name: Name of the merchant.
        description: Optional expense description.

    Returns:
        category (key), display_category (label), confidence_score (0.0–1.0),
        matched_signals (keywords that triggered the match).
    """
    combined = f"{merchant_name} {description}".lower()
    matched_signals: list[str] = []

    for rule in CATEGORY_RULES:
        if not rule["keywords"]:
            continue  # skip "Other" fallback in main loop
        for kw in rule["keywords"]:
            if re.search(rf"\b{re.escape(kw)}\b", combined):
                matched_signals.append(kw)
                return {
                    "category": rule["key"],
                    "display_category": rule["display"],
                    "confidence_score": rule["confidence"],
                    "matched_signals": matched_signals,
                }

    return {
        "category": "other",
        "display_category": "Other",
        "confidence_score": 0.30,
        "matched_signals": [],
    }


# ---------------------------------------------------------------------------
# Unchanged — duplicate detection (kept exactly as before)
# ---------------------------------------------------------------------------

def _to_date(value: str | None) -> datetime | None:
    """Parse a date string in ISO or common US formats."""
    if not value:
        return None
    head = value.replace("Z", "").split("T")[0].split()[0]
    try:
        return datetime.fromisoformat(head)
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(head, fmt)
        except ValueError:
            continue
    return None


def _save_submitted_claim(
    conn, claim_id: str, employee_id: str, merchant: str, amount: float, claim_date: str
) -> None:
    """Persist a submitted claim so later duplicate checks can see it."""
    category = classify_spend_category(merchant)["category"]
    conn.execute(
        """
        INSERT INTO expense_claims
            (id, employee_id, merchant, amount, claim_date, category, status)
        VALUES (?, ?, ?, ?, ?, ?, 'submitted')
        """,
        (claim_id, employee_id, merchant, amount, claim_date, category),
    )


def detect_duplicate_claim(
    employee_id: str,
    merchant: str,
    amount: float,
    date: str,
    save: bool = True,
) -> dict[str, Any]:
    """
    Detect potential duplicate expense claims within ±3 days.

    Returns:
        duplicate_risk_score (0.0–1.0), matched_claim_reference if found.
        Risk score: 0.95+ = exact duplicate, 0.85 = near duplicate, 0.0 = clean.
    """
    claim_dt = _to_date(date) or datetime.utcnow()
    claim_date_iso = claim_dt.strftime("%Y-%m-%d")
    claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"

    with get_db() as conn:
        if save:
            _save_submitted_claim(conn, claim_id, employee_id, merchant, amount, claim_date_iso)

        rows = conn.execute(
            """
            SELECT id, merchant, amount, claim_date, category, status
            FROM expense_claims
            WHERE employee_id = ?
              AND LOWER(merchant) = LOWER(?)
              AND ABS(amount - ?) < 0.01
              AND id != ?
            ORDER BY claim_date DESC
            """,
            (employee_id, merchant, amount, claim_id),
        ).fetchall()

        candidates = rows_to_dicts(rows)
        matches = [
            c
            for c in candidates
            if (cd := _to_date(c["claim_date"])) is not None
            and abs((cd - claim_dt).days) <= 3
        ]

        if not matches:
            return {
                "duplicate_risk_score": 0.0,
                "matched_claim_reference": None,
                "submitted_claim_id": claim_id if save else None,
            }

        risk = 0.85 if len(matches) == 1 else min(0.95 + len(matches) * 0.02, 1.0)

        if save:
            conn.execute(
                "UPDATE expense_claims SET duplicate_risk = ? WHERE id = ?",
                (round(risk, 3), claim_id),
            )

    return {
        "duplicate_risk_score": round(risk, 3),
        "matched_claim_reference": matches[0]["id"],
        "matched_claims": matches,
        "submitted_claim_id": claim_id if save else None,
    }

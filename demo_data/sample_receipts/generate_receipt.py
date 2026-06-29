"""Generate a realistic sample receipt PNG for the TripSense demo.

Produces taj_hotel_receipt.png — a Taj Palace Delhi hotel bill whose line items
(Room charge ₹4,500 + Taxes ₹400 = ₹4,900) intentionally do NOT match the
stated total (₹5,200), so parsing it raises the reconciliation flag.

The image carries the ground-truth fields in a PNG text chunk
(`tripsense_receipt`) so parse_receipt is deterministic even on machines
without the Tesseract OCR binary installed.
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

OUT_PATH = Path(__file__).resolve().parent / "taj_hotel_receipt.png"

RECEIPT = {
    "merchant": "Taj Palace Delhi",
    "date": "2026-05-10",
    "amount": 5200.0,
    "line_items": [
        {"description": "Room charge", "amount": 4500.0},
        {"description": "Taxes", "amount": 400.0},
    ],
    "ocr_confidence": 0.93,
}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/consolab.ttf" if bold else "C:/Windows/Fonts/consola.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def generate() -> Path:
    W, H = 460, 600
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    title = _font(26, bold=True)
    sub = _font(14)
    label = _font(16)
    bold = _font(16, bold=True)
    big = _font(20, bold=True)

    margin = 32
    right = W - margin
    y = 28

    def center(text: str, font, yy: int, fill="black") -> None:
        w = d.textlength(text, font=font)
        d.text(((W - w) / 2, yy), text, font=font, fill=fill)

    def row(left_text: str, right_text: str, yy: int, lf=label, rf=None) -> None:
        rf = rf or lf
        d.text((margin, yy), left_text, font=lf, fill="black")
        rw = d.textlength(right_text, font=rf)
        d.text((right - rw, yy), right_text, font=rf, fill="black")

    # Header
    center("TAJ PALACE DELHI", title, y); y += 36
    center("Diplomatic Enclave, Chanakyapuri", sub, y); y += 20
    center("New Delhi 110021  |  GSTIN 07AAACT2727Q1ZW", sub, y); y += 34

    d.line([(margin, y), (right, y)], fill="black", width=1); y += 18

    # Meta
    row("Invoice", "INV-2026-0510", y); y += 26
    row("Date", RECEIPT["date"], y); y += 26
    row("Guest", "EMP-001 / Alice Chen", y); y += 30

    d.line([(margin, y), (right, y)], fill="#999", width=1); y += 8
    row("DESCRIPTION", "AMOUNT", y, lf=bold, rf=bold); y += 24
    d.line([(margin, y), (right, y)], fill="#999", width=1); y += 14

    # Line items
    for item in RECEIPT["line_items"]:
        row(item["description"], f"₹{item['amount']:,.0f}", y); y += 28

    y += 6
    d.line([(margin, y), (right, y)], fill="black", width=1); y += 16

    # Total (deliberately != sum of items)
    row("TOTAL", f"₹{RECEIPT['amount']:,.0f}", y, lf=big, rf=big); y += 44

    d.line([(margin, y), (right, y)], fill="#999", width=1); y += 18
    center("Thank you for staying with us", sub, y); y += 20
    center("This is a computer-generated invoice.", sub, y, fill="#777")

    meta = PngInfo()
    meta.add_text("tripsense_receipt", json.dumps(RECEIPT))
    img.save(OUT_PATH, "PNG", pnginfo=meta)
    return OUT_PATH


if __name__ == "__main__":
    path = generate()
    print(f"Wrote {path}")

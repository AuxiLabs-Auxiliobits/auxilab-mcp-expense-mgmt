#!/usr/bin/env python3
"""Regenerate the sample files in ``demo/``.

    python demo/generate_samples.py

The ``.txt``/``.json`` files are the sources of truth; the ``.pdf`` files are rendered
from them so the demo has realistic documents to open and upload. PDFs are written with
a small built-in writer rather than a reporting library — three sample files aren't worth
a dependency, and this keeps ``requirements.txt`` at four lines.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

SAMPLE_RECEIPT = """NOODLE HOUSE
123 Main St, San Francisco, CA 94105

2026-06-01  12:47

Pad Thai (x2)          18.00
Green Curry            14.50
Diet Coke (x2)          7.00
Sparkling Water         5.50
Subtotal               45.00
Tax (8.625%)            3.88
Total                  48.88

VISA  ****-4321
Thank you for your visit
"""

SAMPLE_POLICY = {
    "currency": "USD",
    "prohibited_categories": ["Client Entertainment"],
    "category_limits": {
        "Meals & Entertainment": 75,
        "Travel - Hotel": 250,
        "Travel - Air": 1200,
        "Travel - Ground": 150,
        "Office Supplies": 300,
        "Software / Subscriptions": 500,
    },
    "receipt_required_over": 25,
    "max_expense_age_days": 90,
    "duplicate_near_match_days": 3,
    "cap_boundary": "inclusive",
}

SAMPLE_REPORT = [
    {"category": "Meals & Entertainment", "amount": "48.88", "is_compliant": True},
    {"category": "Travel - Air", "amount": "320.00", "is_compliant": True},
    {"category": "Travel - Hotel", "amount": "462.00", "is_compliant": False},
    {"category": "Software / Subscriptions", "amount": "100.00", "is_compliant": True},
    {"category": "Office Supplies", "amount": "28.50", "is_compliant": False},
]


# --------------------------------------------------------------------------- #
# Minimal PDF writer
# --------------------------------------------------------------------------- #
def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def write_pdf(path: Path, lines: list[str], *, font_size: int = 10) -> None:
    """Write a single-page PDF containing ``lines`` in Courier.

    Courier is one of the 14 fonts every PDF reader is required to provide, so nothing
    needs embedding and the output stays a few kilobytes.
    """
    leading = font_size + 2
    content = [f"BT /F1 {font_size} Tf {leading} TL 54 738 Td"]
    for line in lines:
        # Non-ASCII would need a font-encoding dictionary; the samples are all ASCII.
        content.append(f"({_escape(line.rstrip())}) Tj T*")
    content.append("ET")
    stream = "\n".join(content).encode("latin-1", "replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    ).encode()

    path.write_bytes(bytes(out))


def _policy_lines() -> list[str]:
    lines = ["ACME CORP - EXPENSE POLICY", "=" * 52, "", "Prohibited categories:"]
    lines += [f"  - {c}" for c in SAMPLE_POLICY["prohibited_categories"]]
    lines += ["", "Per-expense category limits (USD):"]
    lines += [
        f"  {name:<28} {limit:>8,}" for name, limit in SAMPLE_POLICY["category_limits"].items()
    ]
    lines += [
        "",
        f"Receipt required over:     {SAMPLE_POLICY['receipt_required_over']} USD",
        f"Claim window:              {SAMPLE_POLICY['max_expense_age_days']} days",
        f"Duplicate near-match:      {SAMPLE_POLICY['duplicate_near_match_days']} days",
        f"Cap boundary:              {SAMPLE_POLICY['cap_boundary']} "
        f"(an amount equal to the cap is allowed)",
        "",
        "The machine-readable version of this policy is sample_policy.json.",
    ]
    return lines


def _report_lines() -> list[str]:
    lines = ["EXPENSE REPORT - JUNE 2026", "=" * 52, "", "Employee: emp-001", ""]
    lines.append(f"  {'Category':<28}{'Amount':>10}  {'Status':<10}")
    lines.append("  " + "-" * 50)
    total = 0.0
    at_risk = 0.0
    for row in SAMPLE_REPORT:
        amount = float(row["amount"])
        total += amount
        status = "compliant" if row["is_compliant"] else "FLAGGED"
        if not row["is_compliant"]:
            at_risk += amount
        lines.append(f"  {row['category']:<28}{amount:>10,.2f}  {status:<10}")
    lines.append("  " + "-" * 50)
    lines.append(f"  {'TOTAL':<28}{total:>10,.2f}")
    flagged = sum(1 for r in SAMPLE_REPORT if not r["is_compliant"])
    rate = (len(SAMPLE_REPORT) - flagged) / len(SAMPLE_REPORT) * 100
    lines += [
        "",
        f"  Flagged items:   {flagged} of {len(SAMPLE_REPORT)}",
        f"  Amount at risk:  {at_risk:,.2f} USD",
        f"  Compliance rate: {rate:.0f}%",
        "",
        "The machine-readable version of this report is sample_report.json.",
    ]
    return lines


def main() -> int:
    (HERE / "sample_receipt.txt").write_text(SAMPLE_RECEIPT, encoding="utf-8")
    (HERE / "sample_policy.json").write_text(
        json.dumps(SAMPLE_POLICY, indent=2) + "\n", encoding="utf-8"
    )
    (HERE / "sample_report.json").write_text(
        json.dumps(SAMPLE_REPORT, indent=2) + "\n", encoding="utf-8"
    )

    write_pdf(HERE / "sample_receipt.pdf", SAMPLE_RECEIPT.splitlines())
    write_pdf(HERE / "sample_policy.pdf", _policy_lines())
    write_pdf(HERE / "sample_report.pdf", _report_lines())

    for name in sorted(p.name for p in HERE.iterdir() if p.suffix in {".txt", ".json", ".pdf"}):
        print(f"  wrote demo/{name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Intake file-safety + reconciliation gating (SCOPING §6.1).

Covers the malware scan (offline → clean), the receipt-reconciliation gate (tax sanity and
Σ-items math), and HEIC pass-through. The end-to-end green path lives in test_workflow.py.
"""

from __future__ import annotations

from datetime import date

from app.config import settings
from app.models.attachment import ScanStatus
from app.services import malware_scan_service
from app.services.image_conversion import convert_heic_to_jpeg, is_heic
from tests.conftest import auth, login

THIS_MONTH = date.today().replace(day=1).isoformat()
PERIOD = THIS_MONTH[:7]
_counter = iter(range(3000, 3999))


def _submit_one_item(client, token, *, tax_over=False, tax: str = "2.00"):
    # A unique n-based total/datetime keeps the (employee, receipt_datetime, receipt_total)
    # duplicate key collision-free across the shared test DB. `tax_over` makes tax exceed the
    # total (a hard reconciliation error) while keeping the total unique.
    n = next(_counter)
    receipt_total = f"{n}.00"
    amount = receipt_total
    if tax_over:
        tax = f"{n + 50}.00"  # tax > total → reconciliation fail
    sheet = client.post(
        "/sheets",
        json={
            "title": f"Recon {n}",
            "period": PERIOD,
            "line_items": [
                {
                    "category": "Meals & Entertainment",
                    "amount": amount,
                    "currency": "USD",
                    "merchant": "Cafe",
                    "description": "lunch",
                    "expense_date": THIS_MONTH,
                    "receipt_datetime": f"{THIS_MONTH}T1{n % 9}:00:00",
                    "receipt_total": receipt_total,
                    "tax": tax,
                }
            ],
        },
        headers=auth(token),
    ).json()
    li = sheet["line_items"][0]["id"]
    up = client.post(
        f"/sheets/{sheet['id']}/line-items/{li}/receipt",
        files={"file": ("receipt.pdf", b"%PDF-1.4 receipt", "application/pdf")},
        headers=auth(token),
    )
    assert up.status_code == 201, up.text
    return client.post(f"/sheets/{sheet['id']}/submit", headers=auth(token))


# --------------------------------------------------------------------------- #
# HEIC conversion (transcode when libs present; graceful pass-through otherwise)
# --------------------------------------------------------------------------- #
def test_non_heic_passes_through_unchanged():
    name, data, ftype = convert_heic_to_jpeg("receipt.pdf", b"%PDF-1.4", "application/pdf")
    assert (name, data, ftype) == ("receipt.pdf", b"%PDF-1.4", "application/pdf")


def test_heic_detected_and_never_loses_bytes():
    assert is_heic("photo.HEIC")
    # Bytes aren't valid HEIC and pillow-heif may be absent → original is preserved either way
    # (the upload must never fail). If conversion ran, the name/type would flip to JPEG.
    name, data, ftype = convert_heic_to_jpeg("photo.heic", b"not-a-real-heic", "image/heic")
    assert data == b"not-a-real-heic"
    assert (name, ftype) == ("photo.heic", "image/heic")


# --------------------------------------------------------------------------- #
# Malware scan (offline no-op, and fail-closed when the verdict can't be read)
# --------------------------------------------------------------------------- #
def test_offline_blob_scans_clean():
    assert malware_scan_service.scan_blob("file:///tmp/x.pdf", settings) is ScanStatus.CLEAN


def test_unreadable_azure_blob_fails_closed(monkeypatch):
    # Storage configured but the blob can't be read (no Azure SDK / creds in tests) → FAILED,
    # so an unscanned receipt never silently passes intake (SCOPING §6.1, §9.2).
    monkeypatch.setattr(settings, "storage_account_url", "https://acct.blob.core.windows.net")
    assert (
        malware_scan_service.scan_blob("https://acct.blob.core.windows.net/c/x.pdf", settings)
        is ScanStatus.FAILED
    )


# --------------------------------------------------------------------------- #
# Reconciliation gate
# --------------------------------------------------------------------------- #
def test_tax_exceeds_total_returns_to_employee(client):
    emp = login(client, "employee@demo.local")
    res = _submit_one_item(client, emp, tax_over=True)
    assert res.status_code == 200, res.text
    # Tax > total is a hard data error → the sheet is returned at intake, not advanced.
    assert res.json()["status"] == "RETURNED_TO_EMPLOYEE"


def test_clean_amounts_advance(client):
    emp = login(client, "employee@demo.local")
    # Unique n-based total (collision-free); tax within total → reconciliation passes.
    res = _submit_one_item(client, emp, tax="2.00")
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "IN_MANAGER_REVIEW"

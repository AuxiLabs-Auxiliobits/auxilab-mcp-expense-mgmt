"""Receipt visibility for managers and finance (SCOPING §4.2, §6): metadata, preview, and
download — scope-checked against the parent sheet."""

from __future__ import annotations

from datetime import date

from tests.conftest import auth, login

THIS_MONTH = date.today().replace(day=1).isoformat()
_counter = iter(range(30000, 39000))
RECEIPT = b"%PDF-1.4 receipt-bytes"


def _submitted_sheet_with_receipt(client):
    """Employee creates a sheet + line item, uploads a receipt, submits. Returns (sheet, att)."""
    n = next(_counter)
    emp = login(client, "employee@demo.local")
    payload = {
        "title": f"Receipt {n}",
        "period": THIS_MONTH[:7],
        "line_items": [{
            "category": "Meals & Entertainment", "amount": f"{n}.00", "merchant": f"Cafe {n}",
            "description": "lunch", "expense_date": THIS_MONTH,
            "receipt_datetime": f"{THIS_MONTH}T0{n % 9}:00:00", "receipt_total": f"{n}.00",
        }],
    }
    sheet = client.post("/sheets", json=payload, headers=auth(emp)).json()
    li = sheet["line_items"][0]["id"]
    up = client.post(
        f"/sheets/{sheet['id']}/line-items/{li}/receipt",
        files={"file": ("lunch-receipt.pdf", RECEIPT, "application/pdf")},
        headers=auth(emp),
    )
    assert up.status_code == 201, up.text
    att = up.json()
    client.post(f"/sheets/{sheet['id']}/submit", headers=auth(emp))
    return sheet, att


def test_upload_records_filename_and_uploaded_at(client):
    _sheet, att = _submitted_sheet_with_receipt(client)
    assert att["filename"] == "lunch-receipt.pdf"
    assert att["uploaded_at"]


def test_manager_can_list_sheet_receipts(client):
    sheet, att = _submitted_sheet_with_receipt(client)
    mgr = login(client, "manager@demo.local")
    r = client.get(f"/sheets/{sheet['id']}/receipts", headers=auth(mgr))
    assert r.status_code == 200, r.text
    ids = [a["id"] for a in r.json()]
    assert att["id"] in ids
    assert r.json()[0]["filename"] == "lunch-receipt.pdf"


def test_manager_can_get_metadata_and_preview_and_download(client):
    sheet, att = _submitted_sheet_with_receipt(client)
    mgr = login(client, "manager@demo.local")
    # metadata
    meta = client.get(f"/attachments/{att['id']}", headers=auth(mgr))
    assert meta.status_code == 200 and meta.json()["filename"] == "lunch-receipt.pdf"
    # preview (inline)
    prev = client.get(f"/attachments/{att['id']}/content", headers=auth(mgr))
    assert prev.status_code == 200
    assert prev.content == RECEIPT
    assert "inline" in prev.headers["content-disposition"]
    assert prev.headers["content-type"].startswith("application/pdf")
    # download (attachment)
    dl = client.get(f"/attachments/{att['id']}/content?download=true", headers=auth(mgr))
    assert dl.status_code == 200 and dl.content == RECEIPT
    assert "attachment" in dl.headers["content-disposition"]


def test_finance_can_access_receipts(client):
    sheet, att = _submitted_sheet_with_receipt(client)
    fin = login(client, "finance@demo.local")
    assert client.get(f"/sheets/{sheet['id']}/receipts", headers=auth(fin)).status_code == 200
    content = client.get(f"/attachments/{att['id']}/content", headers=auth(fin))
    assert content.status_code == 200 and content.content == RECEIPT


def test_cross_agency_manager_cannot_access_receipt(client):
    """An SKDK manager cannot read a Crispin employee's receipt (agency scope)."""
    sheet, att = _submitted_sheet_with_receipt(client)  # Crispin employee
    skdk_mgr = login(client, "manager.skdk@demo.local")
    assert client.get(f"/attachments/{att['id']}", headers=auth(skdk_mgr)).status_code == 403
    assert client.get(f"/attachments/{att['id']}/content", headers=auth(skdk_mgr)).status_code == 403
    assert client.get(f"/sheets/{sheet['id']}/receipts", headers=auth(skdk_mgr)).status_code == 403


def test_unrelated_employee_cannot_access_receipt(client):
    sheet, att = _submitted_sheet_with_receipt(client)
    other = login(client, "crispin.emp2@demo.local")  # same agency, not the owner
    # Employees are self-scoped → cannot view someone else's sheet/receipt.
    assert client.get(f"/attachments/{att['id']}", headers=auth(other)).status_code == 403


def test_attachment_404(client):
    mgr = login(client, "manager@demo.local")
    assert client.get("/attachments/does-not-exist", headers=auth(mgr)).status_code == 404
    assert client.get("/attachments/does-not-exist/content", headers=auth(mgr)).status_code == 404


def test_receipt_requires_auth(client):
    _sheet, att = _submitted_sheet_with_receipt(client)
    assert client.get(f"/attachments/{att['id']}/content").status_code == 401

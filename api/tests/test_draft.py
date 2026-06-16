"""Draft expense-sheet workflow (change req): empty draft → add items → upload receipts →
submit; plus value sets, currency/expense-type/period validation, and the receipt-mandatory
gate."""

from __future__ import annotations

from datetime import date

from tests.conftest import auth, login

THIS_MONTH = date.today().replace(day=1).isoformat()
PERIOD = THIS_MONTH[:7]
_counter = iter(range(5000, 6000))


def _line(**over):
    n = next(_counter)
    base = {
        "category": "Travel - Ground",
        "amount": f"{n}.00",
        "merchant": "Uber",
        "description": "ride",
        "expense_date": THIS_MONTH,
        "receipt_datetime": f"{THIS_MONTH}T1{n % 9}:00:00",
        "receipt_total": f"{n}.00",
        "tax": "1.50",
    }
    base.update(over)
    return base


def _draft(client, token, **over):
    body = {"title": "My draft", "period": PERIOD, "line_items": []}
    body.update(over)
    r = client.post("/sheets", json=body, headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()


def _receipt(client, token, sheet_id, li_id, name="r.pdf", content_type="application/pdf"):
    return client.post(
        f"/sheets/{sheet_id}/line-items/{li_id}/receipt",
        files={"file": (name, b"%PDF-1.4 x", content_type)},
        headers=auth(token),
    )


def test_value_sets_endpoint(client):
    emp = login(client, "employee@demo.local")
    r = client.get("/meta/value-sets", headers=auth(emp))
    assert r.status_code == 200, r.text
    body = r.json()
    assert "Other" in body["expense_types"]
    assert "USD" in body["currencies"] and "INR" in body["currencies"]


def test_draft_create_add_receipt_submit(client):
    emp = login(client, "employee@demo.local")
    sheet = _draft(client, emp)
    assert sheet["status"] == "DRAFT" and sheet["title"] == "My draft"
    assert sheet["line_items"] == []

    # add a line item incrementally
    added = client.post(f"/sheets/{sheet['id']}/line-items", json=_line(), headers=auth(emp))
    assert added.status_code == 201, added.text
    li_id = added.json()["line_items"][0]["id"]

    # cannot submit without a receipt
    blocked = client.post(f"/sheets/{sheet['id']}/submit", headers=auth(emp))
    assert blocked.status_code == 422
    assert li_id in blocked.json()["detail"]["line_items_without_receipt"]

    # attach receipt → has_receipt true, receipt_count 1
    rec = _receipt(client, emp, sheet["id"], li_id)
    assert rec.status_code == 201, rec.text
    got = client.get(f"/sheets/{sheet['id']}", headers=auth(emp)).json()
    assert got["line_items"][0]["has_receipt"] is True
    assert got["line_items"][0]["receipt_count"] == 1

    # now submit advances
    ok = client.post(f"/sheets/{sheet['id']}/submit", headers=auth(emp))
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "IN_MANAGER_REVIEW"


def test_edit_and_delete_line_item_while_draft(client):
    emp = login(client, "employee@demo.local")
    sheet = _draft(client, emp, line_items=[_line()])
    li_id = sheet["line_items"][0]["id"]

    patched = client.patch(
        f"/sheets/{sheet['id']}/line-items/{li_id}",
        json={"merchant": "Lyft", "tax": "2.00"},
        headers=auth(emp),
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["merchant"] == "Lyft"

    deleted = client.delete(f"/sheets/{sheet['id']}/line-items/{li_id}", headers=auth(emp))
    assert deleted.status_code == 200
    assert deleted.json()["line_items"] == []


def test_withdraw_draft(client):
    emp = login(client, "employee@demo.local")
    sheet = _draft(client, emp)
    assert client.delete(f"/sheets/{sheet['id']}", headers=auth(emp)).status_code == 204
    assert client.get(f"/sheets/{sheet['id']}", headers=auth(emp)).status_code == 404


def test_other_expense_type_requires_free_text(client):
    emp = login(client, "employee@demo.local")
    sheet = _draft(client, emp)
    r = client.post(
        f"/sheets/{sheet['id']}/line-items",
        json=_line(category="Other", expense_type_other=None),
        headers=auth(emp),
    )
    assert r.status_code == 422
    # with the free text it succeeds
    ok = client.post(
        f"/sheets/{sheet['id']}/line-items",
        json=_line(category="Other", expense_type_other="Conference booth"),
        headers=auth(emp),
    )
    assert ok.status_code == 201, ok.text


def test_unsupported_currency_rejected(client):
    emp = login(client, "employee@demo.local")
    sheet = _draft(client, emp)
    r = client.post(
        f"/sheets/{sheet['id']}/line-items", json=_line(currency="XYZ"), headers=auth(emp)
    )
    assert r.status_code == 422


def test_period_must_be_current_year(client):
    emp = login(client, "employee@demo.local")
    r = client.post(
        "/sheets",
        json={"title": "stale", "period": "1999-03", "line_items": []},
        headers=auth(emp),
    )
    assert r.status_code == 422


def test_disallowed_receipt_extension_rejected(client):
    emp = login(client, "employee@demo.local")
    sheet = _draft(client, emp, line_items=[_line()])
    li_id = sheet["line_items"][0]["id"]
    r = _receipt(client, emp, sheet["id"], li_id, name="malware.exe", content_type="application/x-msdownload")
    assert r.status_code == 422

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


def test_periods_endpoint(client):
    emp = login(client, "employee@demo.local")
    r = client.get("/meta/periods", headers=auth(emp))
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["periods"]) == 12  # current month + previous 11
    assert body["default"] == PERIOD  # current month, newest first
    assert body["periods"][0]["value"] == PERIOD
    assert body["periods"][0]["is_current"] is True
    assert {p["value"] for p in body["periods"]} >= {PERIOD}
    # labels look like "Jun 2026"
    assert " " in body["periods"][0]["label"]


def test_title_required_and_max_50(client):
    emp = login(client, "employee@demo.local")
    # blank title → 422
    assert client.post(
        "/sheets", json={"title": "  ", "period": PERIOD, "line_items": []}, headers=auth(emp)
    ).status_code == 422
    # > 50 chars → 422
    assert client.post(
        "/sheets", json={"title": "x" * 51, "period": PERIOD, "line_items": []}, headers=auth(emp)
    ).status_code == 422
    # exactly 50 → ok
    assert client.post(
        "/sheets", json={"title": "y" * 50, "period": PERIOD, "line_items": []}, headers=auth(emp)
    ).status_code == 201


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


def test_withdraw_recalls_submitted_sheet(client):
    emp = login(client, "employee@demo.local")
    sheet = _draft(client, emp, line_items=[_line()])
    li_id = sheet["line_items"][0]["id"]
    assert _receipt(client, emp, sheet["id"], li_id).status_code == 201
    submitted = client.post(f"/sheets/{sheet['id']}/submit", headers=auth(emp))
    assert submitted.status_code == 200 and submitted.json()["status"] == "IN_MANAGER_REVIEW"

    wd = client.post(f"/sheets/{sheet['id']}/withdraw", headers=auth(emp))
    assert wd.status_code == 200, wd.text
    assert wd.json()["status"] == "DRAFT"

    # A plain DRAFT isn't in-flight → can't be withdrawn again.
    assert client.post(f"/sheets/{sheet['id']}/withdraw", headers=auth(emp)).status_code == 409


def test_withdraw_blocked_after_manager_approval(client):
    emp = login(client, "employee@demo.local")
    sheet = _draft(client, emp, line_items=[_line()])
    li_id = sheet["line_items"][0]["id"]
    assert _receipt(client, emp, sheet["id"], li_id).status_code == 201
    assert client.post(f"/sheets/{sheet['id']}/submit", headers=auth(emp)).status_code == 200

    # Manager approves the only line item → sheet advances to finance review.
    mgr = login(client, "manager@demo.local")
    approved = client.post(
        f"/manager/sheets/{sheet['id']}/action",
        json={"line_item_id": li_id, "action": "MANAGER_APPROVED"},
        headers=auth(mgr),
    )
    assert approved.status_code == 200 and approved.json()["status"] == "IN_FINANCE_REVIEW"

    # Now the employee can no longer withdraw it.
    wd = client.post(f"/sheets/{sheet['id']}/withdraw", headers=auth(emp))
    assert wd.status_code == 409, wd.text


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


def test_sheet_out_enrichment_fields(client):
    """Detail payload carries the UI's enrichment: names, totals, gating, timestamps, flags."""
    from decimal import Decimal

    emp = login(client, "employee@demo.local")
    sheet = _draft(client, emp, line_items=[_line(amount="100.00", currency="USD")])
    li_id = sheet["line_items"][0]["id"]

    # display names resolved from the FK ids
    assert isinstance(sheet["employee_name"], str) and sheet["employee_name"]
    assert isinstance(sheet["agency_name"], str) and sheet["agency_name"]

    # totals
    assert Decimal(sheet["total"]) == Decimal("100.00")
    assert sheet["currency"] == "USD"
    assert {k: Decimal(v) for k, v in sheet["totals_by_currency"].items()} == {"USD": Decimal("100.00")}

    # timestamps present for "updated N days ago" + the stepper
    assert sheet["created_at"] and sheet["updated_at"]
    assert sheet["submitted_at"] is None  # not submitted yet

    # gating: a receipt is still missing → cannot submit, with a reason
    assert sheet["missing_receipts"] == 1
    assert sheet["can_submit"] is False
    assert any("receipt" in b.lower() for b in sheet["submit_blockers"])

    # after attaching the receipt the sheet becomes submittable
    assert _receipt(client, emp, sheet["id"], li_id).status_code == 201
    got = client.get(f"/sheets/{sheet['id']}", headers=auth(emp)).json()
    assert got["missing_receipts"] == 0
    assert got["can_submit"] is True
    assert got["submit_blockers"] == []
    # policy flags are computed on the detail route
    assert set(got["policy_flags"]) == {"errors", "warnings"}


def test_empty_draft_blocks_submit_with_reason(client):
    from decimal import Decimal

    emp = login(client, "employee@demo.local")
    sheet = _draft(client, emp)  # no line items
    assert sheet["can_submit"] is False
    assert "Add a line item to submit." in sheet["submit_blockers"]
    assert Decimal(sheet["total"]) == Decimal("0")
    assert sheet["currency"] == "USD"  # default for an empty sheet


def test_decision_trail_endpoint(client):
    emp = login(client, "employee@demo.local")
    sheet = _draft(client, emp)
    r = client.get(f"/sheets/{sheet['id']}/decisions", headers=auth(emp))
    assert r.status_code == 200, r.text
    assert r.json() == []  # no manager/finance decisions on a fresh draft


def test_disallowed_receipt_extension_rejected(client):
    emp = login(client, "employee@demo.local")
    sheet = _draft(client, emp, line_items=[_line()])
    li_id = sheet["line_items"][0]["id"]
    r = _receipt(client, emp, sheet["id"], li_id, name="malware.exe", content_type="application/x-msdownload")
    assert r.status_code == 422

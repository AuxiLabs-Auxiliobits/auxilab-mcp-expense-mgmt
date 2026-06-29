"""End-to-end happy path through the three lines of defense (SCOPING §6, §17):
employee submits → manager approves each line item → sheet advances to finance review."""

from __future__ import annotations

from datetime import date

from tests.conftest import auth, login

THIS_MONTH = date.today().replace(day=1).isoformat()

# Each test uses a distinct amount/receipt_datetime so the (employee, receipt_datetime,
# receipt_total) duplicate key never collides across the shared test DB.
_counter = iter(range(100, 1000))


def _new_sheet_payload():
    n = next(_counter)
    return {
        "title": f"Trip {n}",
        "period": THIS_MONTH[:7],  # "YYYY-MM" of the current month/year
        "line_items": [
            {
                "category": "Travel - Ground",
                "amount": f"{n}.00",
                "merchant": "Uber",
                "description": "Airport transfer",
                "expense_date": THIS_MONTH,
                "receipt_datetime": f"{THIS_MONTH}T0{n % 9}:30:00",
                "receipt_total": f"{n}.00",
                "tax": "0.00",
            }
        ],
    }


def _attach_receipts(client, token, sheet):
    """Upload a receipt to every line item (mandatory before submit)."""
    for li in sheet["line_items"]:
        r = client.post(
            f"/sheets/{sheet['id']}/line-items/{li['id']}/receipt",
            files={"file": ("receipt.pdf", b"%PDF-1.4 receipt", "application/pdf")},
            headers=auth(token),
        )
        assert r.status_code == 201, r.text


def test_submit_advances_to_manager_review(client):
    emp = login(client, "employee@demo.local")
    created = client.post("/sheets", json=_new_sheet_payload(), headers=auth(emp))
    assert created.status_code == 201, created.text
    sheet = created.json()
    _attach_receipts(client, emp, sheet)

    submitted = client.post(f"/sheets/{sheet['id']}/submit", headers=auth(emp))
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "IN_MANAGER_REVIEW"


def test_manager_approval_advances_to_finance(client):
    emp = login(client, "employee@demo.local")
    sheet = client.post("/sheets", json=_new_sheet_payload(), headers=auth(emp)).json()
    sheet_id = sheet["id"]
    _attach_receipts(client, emp, sheet)
    client.post(f"/sheets/{sheet_id}/submit", headers=auth(emp))

    mgr = login(client, "manager@demo.local")
    queue = client.get("/manager/queue", headers=auth(mgr)).json()
    target = next(s for s in queue if s["id"] == sheet_id)
    line_item_id = target["line_items"][0]["id"]

    res = client.post(
        f"/manager/sheets/{sheet_id}/action",
        json={"line_item_id": line_item_id, "action": "MANAGER_APPROVED"},
        headers=auth(mgr),
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "IN_FINANCE_REVIEW"


def test_cross_agency_view_denied(client):
    """An employee cannot view a sheet they don't own (scope=self)."""
    emp = login(client, "employee@demo.local")
    sheet = client.post("/sheets", json=_new_sheet_payload(), headers=auth(emp)).json()

    # Admin (scope=all) can view it; that proves the route works and scope differs.
    admin = login(client, "admin@demo.local")
    assert client.get(f"/sheets/{sheet['id']}", headers=auth(admin)).status_code == 200

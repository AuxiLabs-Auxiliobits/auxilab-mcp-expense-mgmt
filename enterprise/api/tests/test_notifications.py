"""Notifications (emit on workflow transitions) + user preferences round-trip."""

from __future__ import annotations

from datetime import date

from tests.conftest import auth, login

THIS_MONTH = date.today().replace(day=1).isoformat()
PERIOD = THIS_MONTH[:7]
_counter = iter(range(8000, 8999))


def _submit_sheet(client, token):
    n = next(_counter)
    sheet = client.post(
        "/sheets",
        json={
            "title": f"Notif {n}",
            "period": PERIOD,
            "line_items": [
                {
                    "category": "Travel - Ground",
                    "amount": f"{n}.00",
                    "currency": "USD",
                    "merchant": "Uber",
                    "description": "ride",
                    "expense_date": THIS_MONTH,
                    "receipt_datetime": f"{THIS_MONTH}T1{n % 9}:00:00",
                    "receipt_total": f"{n}.00",
                    "tax": "0.00",
                }
            ],
        },
        headers=auth(token),
    ).json()
    li = sheet["line_items"][0]["id"]
    client.post(
        f"/sheets/{sheet['id']}/line-items/{li}/receipt",
        files={"file": ("r.pdf", b"%PDF-1.4 x", "application/pdf")},
        headers=auth(token),
    )
    assert client.post(f"/sheets/{sheet['id']}/submit", headers=auth(token)).status_code == 200
    return sheet, li


def test_notifications_requires_auth(client):
    assert client.get("/notifications").status_code == 401


def test_submit_notifies_manager(client):
    emp = login(client, "employee@demo.local")
    _submit_sheet(client, emp)
    mgr = login(client, "manager@demo.local")
    notifs = client.get("/notifications", headers=auth(mgr)).json()
    assert any("review" in n["title"].lower() for n in notifs)


def test_manager_approval_notifies_employee_then_mark_read(client):
    emp = login(client, "employee@demo.local")
    sheet, li = _submit_sheet(client, emp)
    mgr = login(client, "manager@demo.local")
    client.post(
        f"/manager/sheets/{sheet['id']}/action",
        json={"line_item_id": li, "action": "MANAGER_APPROVED"},
        headers=auth(mgr),
    )
    notifs = client.get("/notifications", headers=auth(emp)).json()
    assert any(n["kind"] == "success" for n in notifs), notifs

    after = client.post("/notifications/read", headers=auth(emp)).json()
    assert after and all(n["read"] for n in after)


def test_preferences_roundtrip(client):
    emp = login(client, "employee@demo.local")
    assert client.get("/me/preferences", headers=auth(emp)).json()["preferences"] == {}

    put = client.put(
        "/me/preferences",
        json={"preferences": {"emailDigest": True, "push": False}},
        headers=auth(emp),
    )
    assert put.status_code == 200
    assert put.json()["preferences"]["emailDigest"] is True

    got = client.get("/me/preferences", headers=auth(emp)).json()["preferences"]
    assert got["push"] is False

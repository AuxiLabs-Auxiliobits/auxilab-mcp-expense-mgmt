"""Reports/summary endpoint (SCOPING §4): RBAC + aggregation shape."""

from __future__ import annotations

from datetime import date

from tests.conftest import auth, login

THIS_MONTH = date.today().replace(day=1).isoformat()
PERIOD = THIS_MONTH[:7]
_counter = iter(range(7000, 8000))


def _submit_one(client, token):
    n = next(_counter)
    sheet = client.post(
        "/sheets",
        json={
            "title": f"Report {n}",
            "period": PERIOD,
            "line_items": [
                {
                    "category": "Meals & Entertainment",
                    "amount": f"{n}.00",
                    "currency": "USD",
                    "merchant": "Cafe",
                    "description": "lunch",
                    "expense_date": THIS_MONTH,
                    "receipt_datetime": f"{THIS_MONTH}T1{n % 9}:00:00",
                    "receipt_total": f"{n}.00",
                    "tax": "1.00",
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
    client.post(f"/sheets/{sheet['id']}/submit", headers=auth(token))
    return sheet


def test_reports_summary_for_finance(client):
    emp = login(client, "employee@demo.local")
    _submit_one(client, emp)

    fin = login(client, "finance@demo.local")
    r = client.get("/reports/summary", headers=auth(fin))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sheet_count"] >= 1
    assert float(body["grand_total"]) > 0
    assert 0 <= body["compliance_rate_pct"] <= 100
    assert isinstance(body["by_category"], list)
    assert isinstance(body["by_status"], dict)
    assert "narrative" in body


def test_reports_summary_period_filter(client):
    fin = login(client, "finance@demo.local")
    r = client.get("/reports/summary", params={"period": "1999-01"}, headers=auth(fin))
    assert r.status_code == 200, r.text
    # No sheets in 1999 → empty aggregation, 100% compliance by convention.
    assert r.json()["sheet_count"] == 0
    assert r.json()["compliance_rate_pct"] == 100.0


def test_reports_summary_denied_for_employee(client):
    emp = login(client, "employee@demo.local")
    assert client.get("/reports/summary", headers=auth(emp)).status_code == 403


def test_reports_summary_manager_scoped_to_agency(client):
    mgr = login(client, "manager@demo.local")
    r = client.get("/reports/summary", headers=auth(mgr))
    assert r.status_code == 200, r.text
    # Manager scope is pinned to their own agency regardless of the agency_id param.
    assert r.json()["agency_id"] is not None

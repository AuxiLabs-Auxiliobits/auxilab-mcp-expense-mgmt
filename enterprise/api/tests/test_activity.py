"""Activity / audit feed: role scoping (employee=self, manager=agency, finance/admin=all),
pagination, and filters (SCOPING §6.5)."""

from __future__ import annotations

from datetime import date

from tests.conftest import auth, login

PERIOD = date.today().replace(day=1).isoformat()[:7]


def _make_draft(client, token, title="Activity test"):
    r = client.post(
        "/sheets", json={"title": title, "period": PERIOD, "line_items": []}, headers=auth(token)
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_activity_requires_auth(client):
    assert client.get("/activity").status_code == 401


def test_employee_sees_only_own_activity(client):
    emp = login(client, "employee@demo.local")
    _make_draft(client, emp)
    me = client.get("/auth/me", headers=auth(emp)).json()

    body = client.get("/activity?page_size=100", headers=auth(emp)).json()
    assert body["total"] >= 1
    assert body["items"], "employee should see their own actions"
    assert all(it["actor_id"] == me["subject_id"] for it in body["items"])
    # summary + actor name are populated for the table
    assert all(it["summary"] for it in body["items"])


def test_manager_sees_agency_activity(client):
    emp = login(client, "employee@demo.local")
    _make_draft(client, emp, title="Manager-visible draft")
    emp_id = client.get("/auth/me", headers=auth(emp)).json()["subject_id"]

    mgr = login(client, "manager@demo.local")
    items = client.get("/activity?page_size=100", headers=auth(mgr)).json()["items"]
    # Manager (same agency) sees the employee's action.
    assert any(it["actor_id"] == emp_id for it in items)


def test_admin_sees_org_wide(client):
    emp = login(client, "employee@demo.local")
    _make_draft(client, emp)
    emp_id = client.get("/auth/me", headers=auth(emp)).json()["subject_id"]

    admin = login(client, "admin@demo.local")
    items = client.get("/activity?page_size=100", headers=auth(admin)).json()["items"]
    assert any(it["actor_id"] == emp_id for it in items)


def test_activity_pagination_and_filter(client):
    emp = login(client, "employee@demo.local")
    _make_draft(client, emp)
    _make_draft(client, emp)

    paged = client.get("/activity?page=1&page_size=1", headers=auth(emp)).json()
    assert len(paged["items"]) == 1
    assert paged["page_size"] == 1 and paged["total"] >= 2

    filtered = client.get("/activity?action=SHEET_DRAFTED&page_size=50", headers=auth(emp)).json()
    assert filtered["items"]
    assert all(it["action"] == "SHEET_DRAFTED" for it in filtered["items"])

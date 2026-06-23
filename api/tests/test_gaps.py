"""Coverage for the frontend-contract endpoints added to close UI gaps (SCOPING §3–§6):
withdraw, manager whole-sheet approve, finance all-sheets + KPIs, spend-by-category,
self audit trail, role assignment, and event-driven notifications.

Happy paths + authorization + error paths for each, plus the notification side effects."""

from __future__ import annotations

from datetime import date

from tests.conftest import auth, login

THIS_MONTH = date.today().replace(day=1).isoformat()
_counter = iter(range(2000, 9000))


def _new_sheet_payload():
    n = next(_counter)
    return {
        "title": f"Gap Trip {n}",
        "period": THIS_MONTH[:7],
        "line_items": [
            {
                "category": "Travel - Ground",
                "amount": f"{n}.00",
                "merchant": f"Uber {n}",
                "description": "Airport transfer",
                "expense_date": THIS_MONTH,
                "receipt_datetime": f"{THIS_MONTH}T0{n % 9}:30:00",
                "receipt_total": f"{n}.00",
                "tax": "0.00",
            }
        ],
    }


def _attach_receipts(client, token, sheet):
    for li in sheet["line_items"]:
        r = client.post(
            f"/sheets/{sheet['id']}/line-items/{li['id']}/receipt",
            files={"file": ("receipt.pdf", b"%PDF-1.4 receipt", "application/pdf")},
            headers=auth(token),
        )
        assert r.status_code == 201, r.text


def _submitted_sheet(client, emp):
    sheet = client.post("/sheets", json=_new_sheet_payload(), headers=auth(emp)).json()
    _attach_receipts(client, emp, sheet)
    res = client.post(f"/sheets/{sheet['id']}/submit", headers=auth(emp))
    assert res.json()["status"] == "IN_MANAGER_REVIEW", res.text
    return sheet["id"]


# --- Gap B: withdraw ------------------------------------------------------- #
def test_withdraw_draft_soft_sets_withdrawn(client):
    emp = login(client, "employee@demo.local")
    sheet = client.post("/sheets", json=_new_sheet_payload(), headers=auth(emp)).json()
    r = client.post(f"/sheets/{sheet['id']}/withdraw", headers=auth(emp))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "WITHDRAWN"
    # Soft: the sheet still exists and is readable.
    assert client.get(f"/sheets/{sheet['id']}", headers=auth(emp)).status_code == 200


def test_withdraw_non_draft_conflicts(client):
    emp = login(client, "employee@demo.local")
    sid = _submitted_sheet(client, emp)  # now IN_MANAGER_REVIEW
    r = client.post(f"/sheets/{sid}/withdraw", headers=auth(emp))
    assert r.status_code == 409, r.text


def test_withdraw_not_owner_forbidden(client):
    emp = login(client, "employee@demo.local")
    sheet = client.post("/sheets", json=_new_sheet_payload(), headers=auth(emp)).json()
    other = login(client, "manager@demo.local")  # has submit capability but isn't the owner
    r = client.post(f"/sheets/{sheet['id']}/withdraw", headers=auth(other))
    assert r.status_code == 403, r.text


# --- Gap D: manager whole-sheet approve ------------------------------------ #
def test_manager_approve_whole_sheet_advances(client):
    emp = login(client, "employee@demo.local")
    sid = _submitted_sheet(client, emp)
    mgr = login(client, "manager@demo.local")
    r = client.post(f"/manager/sheets/{sid}/approve", headers=auth(mgr))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "IN_FINANCE_REVIEW"


def test_manager_approve_requires_manager_role(client):
    emp = login(client, "employee@demo.local")
    sid = _submitted_sheet(client, emp)
    r = client.post(f"/manager/sheets/{sid}/approve", headers=auth(emp))
    assert r.status_code == 403, r.text


def test_manager_approve_wrong_state_conflicts(client):
    emp = login(client, "employee@demo.local")
    sheet = client.post("/sheets", json=_new_sheet_payload(), headers=auth(emp)).json()
    mgr = login(client, "manager@demo.local")
    r = client.post(f"/manager/sheets/{sheet['id']}/approve", headers=auth(mgr))
    assert r.status_code == 409, r.text


# --- Gap A/E: finance all-sheets + KPIs ------------------------------------ #
def test_finance_all_sheets(client):
    emp = login(client, "employee@demo.local")
    sid = _submitted_sheet(client, emp)
    fin = login(client, "finance@demo.local")
    rows = client.get("/finance/sheets", headers=auth(fin))
    assert rows.status_code == 200, rows.text
    assert any(s["id"] == sid for s in rows.json())


def test_finance_all_sheets_forbidden_for_employee(client):
    emp = login(client, "employee@demo.local")
    assert client.get("/finance/sheets", headers=auth(emp)).status_code == 403


def test_finance_kpis_shape(client):
    emp = login(client, "employee@demo.local")
    sid = _submitted_sheet(client, emp)
    mgr = login(client, "manager@demo.local")
    client.post(f"/manager/sheets/{sid}/approve", headers=auth(mgr))  # → IN_FINANCE_REVIEW
    fin = login(client, "finance@demo.local")
    r = client.get("/finance/kpis", headers=auth(fin))
    assert r.status_code == 200, r.text
    body = r.json()
    for key in (
        "auto_approval_rate", "manual_interventions", "policy_citations",
        "policy_compliance_rate", "finance_reached",
    ):
        assert key in body
    assert body["finance_reached"] >= 1


# --- Gap F: spend-by-category ---------------------------------------------- #
def test_spend_by_category(client):
    emp = login(client, "employee@demo.local")
    _submitted_sheet(client, emp)
    fin = login(client, "finance@demo.local")
    r = client.get("/reports/spend-by-category", headers=auth(fin))
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    if len(data) >= 2:  # sorted highest-first
        assert float(data[0]["amount"]) >= float(data[1]["amount"])


# --- Gap C: self audit trail ----------------------------------------------- #
def test_audit_me_returns_only_own_actions(client):
    emp = login(client, "employee@demo.local")
    _submitted_sheet(client, emp)  # generates SHEET_DRAFTED/SUBMITTED for this user
    me = client.get("/auth/me", headers=auth(emp)).json()
    r = client.get("/audit/me", headers=auth(emp))
    assert r.status_code == 200, r.text
    rows = r.json()
    assert rows, "expected at least one audit row for the employee"
    assert all(row["actor_id"] == me["subject_id"] for row in rows)


# --- Gap G: assign role ---------------------------------------------------- #
def test_assign_role_by_email(client):
    admin = login(client, "admin@demo.local")
    # Create a throwaway user, then flip their role by email.
    email = "gap-roletest@demo.local"
    client.post(
        "/admin/users",
        json={"name": "Role Test", "email": email, "role": "employee", "password": "demo"},
        headers=auth(admin),
    )
    r = client.post(
        "/admin/users/assign-role", json={"email": email, "role": "manager"}, headers=auth(admin)
    )
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "manager"


def test_assign_role_unknown_email_404(client):
    admin = login(client, "admin@demo.local")
    r = client.post(
        "/admin/users/assign-role",
        json={"email": "nobody@demo.local", "role": "manager"},
        headers=auth(admin),
    )
    assert r.status_code == 404, r.text


def test_assign_role_requires_admin(client):
    fin = login(client, "finance@demo.local")
    r = client.post(
        "/admin/users/assign-role",
        json={"email": "employee@demo.local", "role": "manager"},
        headers=auth(fin),
    )
    assert r.status_code == 403, r.text


# --- Gap H: notifications -------------------------------------------------- #
def test_submit_notifies_agency_manager(client):
    emp = login(client, "employee@demo.local")
    _submitted_sheet(client, emp)  # → notifies all Crispin managers
    mgr = login(client, "manager@demo.local")
    notes = client.get("/notifications", headers=auth(mgr))
    assert notes.status_code == 200, notes.text
    titles = [n["title"] for n in notes.json()]
    assert "New sheet to review" in titles


def test_return_notifies_employee_and_mark_read(client):
    emp = login(client, "employee@demo.local")
    sid = _submitted_sheet(client, emp)
    mgr = login(client, "manager@demo.local")
    queue = client.get("/manager/queue", headers=auth(mgr)).json()
    li = next(s for s in queue if s["id"] == sid)["line_items"][0]["id"]
    client.post(
        f"/manager/sheets/{sid}/action",
        json={"line_item_id": li, "action": "MANAGER_REJECTED", "reason": "fix it"},
        headers=auth(mgr),
    )
    # Employee gets a "returned" notification.
    notes = client.get("/notifications", headers=auth(emp)).json()
    assert any(n["title"].startswith("Sheet returned") for n in notes)
    assert any(not n["read"] for n in notes)
    # Marking read clears the unread flag.
    after = client.post("/notifications/read", headers=auth(emp)).json()
    assert all(n["read"] for n in after)


def test_notifications_are_recipient_scoped(client):
    """A manager's queue notifications never leak to an unrelated employee."""
    emp = login(client, "employee@demo.local")
    _submitted_sheet(client, emp)
    # The employee should not see the manager-targeted "New sheet to review".
    own = client.get("/notifications", headers=auth(emp)).json()
    assert all(n["title"] != "New sheet to review" for n in own)


def test_cross_agency_isolation_queue_and_notifications(client):
    """An SKDK employee's submission reaches only the SKDK manager — never Crispin's
    queue or notifications (SCOPING §3.3, §19.1)."""
    sk_emp = login(client, "employee.skdk@demo.local")
    sid = _submitted_sheet(client, sk_emp)

    sk_mgr = login(client, "manager.skdk@demo.local")
    cr_mgr = login(client, "manager@demo.local")
    assert any(s["id"] == sid for s in client.get("/manager/queue", headers=auth(sk_mgr)).json())
    assert all(s["id"] != sid for s in client.get("/manager/queue", headers=auth(cr_mgr)).json())

    sk_titles = [n["title"] for n in client.get("/notifications", headers=auth(sk_mgr)).json()]
    assert "New sheet to review" in sk_titles
    # Crispin manager must not be notified about an SKDK sheet.
    cr_notes = client.get("/notifications", headers=auth(cr_mgr)).json()
    assert all(n.get("href") != "/manager" or sid not in (n.get("body") or "") for n in cr_notes)

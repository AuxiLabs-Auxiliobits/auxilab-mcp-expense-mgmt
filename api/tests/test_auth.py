"""Auth + RBAC seam: tokens carry role + agency; the matrix and SoD are enforced."""

from __future__ import annotations

from tests.conftest import auth, login


def test_login_and_me(client):
    token = login(client, "employee@demo.local")
    r = client.get("/auth/me", headers=auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "employee"
    assert body["scope"] == "self"
    assert body["agency_id"]  # bound to an agency


def test_manager_scope_is_agency(client):
    token = login(client, "manager@demo.local")
    body = client.get("/auth/me", headers=auth(token)).json()
    assert body["role"] == "manager"
    assert body["scope"] == "agency"


def test_bad_password_rejected(client):
    r = client.post("/auth/login", json={"email": "employee@demo.local", "password": "nope"})
    assert r.status_code == 401


def test_employee_cannot_access_manager_queue(client):
    token = login(client, "employee@demo.local")
    r = client.get("/manager/queue", headers=auth(token))
    assert r.status_code == 403


def test_finance_cannot_action_line_items(client):
    token = login(client, "finance@demo.local")
    # Finance lacks MANAGER_ACTION_LINE_ITEM capability.
    r = client.get("/manager/queue", headers=auth(token))
    assert r.status_code == 403


def test_admin_can_list_agencies(client):
    token = login(client, "admin@demo.local")
    r = client.get("/admin/agencies", headers=auth(token))
    assert r.status_code == 200
    assert any(a["name"] == "Crispin" for a in r.json())


def test_no_token_rejected(client):
    assert client.get("/auth/me").status_code == 401  # HTTPBearer: no credentials


def test_deactivated_account_token_rejected(client):
    """A still-valid token stops working the moment the account is deactivated (§ session)."""
    admin = login(client, "admin@demo.local")
    # Create a user, log in to get a live token, then deactivate them.
    email = "deact-test@demo.local"
    created = client.post(
        "/admin/users",
        json={"name": "Deact", "email": email, "role": "employee", "password": "Demo123456"},
        headers=auth(admin),
    ).json()
    token = login(client, email, "Demo123456")
    assert client.get("/auth/me", headers=auth(token)).status_code == 200  # works while active

    client.delete(f"/admin/users/{created['id']}", headers=auth(admin))  # soft-delete (is_active=false)
    # The previously-issued token is now rejected on the very next request.
    assert client.get("/auth/me", headers=auth(token)).status_code == 401
    assert client.get("/sheets", headers=auth(token)).status_code == 401

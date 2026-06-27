"""Production-stabilization regression tests.

Covers the new notification per-item endpoints (incl. IDOR) and the security fixes:
AGENT excluded from human finance decisions (S-H4), password policy on admin-created users
(S-H5), and the JWT-secret fail-fast guard outside dev (S-C1).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.config import Settings
from app.principal import Principal
from app.rbac.permissions import Capability, can
from tests.conftest import auth, login

_THIS_MONTH = date.today().replace(day=1).isoformat()
_PERIOD = _THIS_MONTH[:7]
# Dedicated high range + ".55" cents so receipt identity never collides with other tests'
# line items under the unique (employee_id, receipt_datetime, receipt_total) constraint.
_counter = iter(range(90000, 99999))


def _submit_unique(client, token):
    n = next(_counter)
    dt = f"{_THIS_MONTH}T{(n % 12) + 8:02d}:{n % 60:02d}:{n % 59:02d}"
    sheet = client.post(
        "/sheets",
        json={
            "title": f"Stab {n}",
            "period": _PERIOD,
            "line_items": [
                {
                    "category": "Travel - Ground", "amount": f"{n}.00", "currency": "USD",
                    "merchant": "Uber", "description": "ride", "expense_date": _THIS_MONTH,
                    "receipt_datetime": dt, "receipt_total": f"{n}.55", "tax": "0.00",
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


# --- Notifications: per-item mark-read / archive / delete + IDOR ------------ #
def _a_notification(client):
    """Trigger a manager notification (via an employee submit) → (mgr_token, notification_id)."""
    emp = login(client, "employee@demo.local")
    _submit_unique(client, emp)
    mgr = login(client, "manager@demo.local")
    notifs = client.get("/notifications", headers=auth(mgr)).json()
    assert notifs, "expected a manager notification from submit"
    return mgr, notifs[0]["id"]


def test_mark_one_notification_read(client):
    mgr, nid = _a_notification(client)
    r = client.post(f"/notifications/{nid}/read", headers=auth(mgr))
    assert r.status_code == 200 and r.json()["read"] is True


def test_archive_hides_from_default_but_kept_in_archived(client):
    mgr, nid = _a_notification(client)
    assert client.post(f"/notifications/{nid}/archive", headers=auth(mgr)).status_code == 200
    default = client.get("/notifications", headers=auth(mgr)).json()
    assert all(n["id"] != nid for n in default)  # hidden from the default inbox
    archived = client.get("/notifications?include_archived=true", headers=auth(mgr)).json()
    assert any(n["id"] == nid for n in archived)  # still retained in history


def test_delete_notification(client):
    mgr, nid = _a_notification(client)
    assert client.delete(f"/notifications/{nid}", headers=auth(mgr)).status_code == 204
    remaining = client.get("/notifications?include_archived=true", headers=auth(mgr)).json()
    assert all(n["id"] != nid for n in remaining)


def test_notification_idor_non_owner_gets_404(client):
    """A user who is not the recipient cannot read/archive/delete the notification — and gets
    404 (no existence leak), while the real owner's row is untouched."""
    mgr, nid = _a_notification(client)
    other = login(client, "finance@demo.local")
    assert client.post(f"/notifications/{nid}/read", headers=auth(other)).status_code == 404
    assert client.post(f"/notifications/{nid}/archive", headers=auth(other)).status_code == 404
    assert client.delete(f"/notifications/{nid}", headers=auth(other)).status_code == 404
    assert any(n["id"] == nid for n in client.get("/notifications", headers=auth(mgr)).json())


# --- S-H4: AGENT excluded from human finance decisions --------------------- #
def test_agent_lacks_finance_decision_capability():
    agent = Principal.from_claims({"sub": "x", "email": "a@x", "roles": ["agent"], "agency_id": None})
    assert can(agent, Capability.FINANCE_DECISION) is False


def test_agent_cannot_post_human_finance_decision(client):
    agent = login(client, "agent@demo.local")
    r = client.post(
        "/finance/sheets/any-id/decision",
        json={"approve": True, "reason": "x"},
        headers=auth(agent),
    )
    assert r.status_code == 403, r.text


# --- S-H5: admin-created users must meet the password policy --------------- #
def test_create_user_rejects_weak_password(client):
    admin = login(client, "admin@demo.local")
    r = client.post(
        "/admin/users",
        json={"name": "Weak", "email": "weak-stab@demo.local", "role": "employee", "password": "weak"},
        headers=auth(admin),
    )
    assert r.status_code == 422, r.text


def test_create_user_accepts_strong_password(client):
    admin = login(client, "admin@demo.local")
    r = client.post(
        "/admin/users",
        json={
            "name": "Strong", "email": "strong-stab@demo.local",
            "role": "employee", "password": "Demo123456",
        },
        headers=auth(admin),
    )
    assert r.status_code == 201, r.text


# --- S-C1: JWT secret guard fails fast outside dev ------------------------- #
def test_default_jwt_secret_rejected_in_prod():
    with pytest.raises(Exception):
        Settings(environment="prod", auth_provider="db", jwt_secret="dev-only-change-me")


def test_strong_jwt_secret_ok_in_prod():
    s = Settings(environment="prod", auth_provider="db", jwt_secret="x" * 40)
    assert s.environment == "prod"

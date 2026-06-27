"""Notification center API: per-item read/archive/delete, archived filtering, recipient RBAC."""

from __future__ import annotations

from sqlmodel import Session

from app.db import engine
from app.models.notification import Notification
from tests.conftest import auth, login


def _subject_id(client, token: str) -> str:
    return client.get("/auth/me", headers=auth(token)).json()["subject_id"]


def _seed(recipient_id: str, title: str = "Expense returned") -> str:
    with Session(engine) as s:
        n = Notification(
            recipient_id=recipient_id, kind="warning", icon="undo",
            title=title, body="Please fix and resubmit.", href="/employee/sheets/abc",
            entity="expense_sheet:abc",
        )
        s.add(n)
        s.commit()
        s.refresh(n)
        return n.id


def test_list_read_archive_delete_flow(client):
    token = login(client, "employee@demo.local")
    uid = _subject_id(client, token)
    nid = _seed(uid)

    # appears, unread
    rows = client.get("/notifications", headers=auth(token)).json()
    assert any(r["id"] == nid and r["read"] is False for r in rows)

    # mark one read
    r = client.post(f"/notifications/{nid}/read", headers=auth(token))
    assert r.status_code == 200 and r.json()["read"] is True

    # archive → hidden by default, visible with include_archived
    client.post(f"/notifications/{nid}/archive", headers=auth(token))
    default = client.get("/notifications", headers=auth(token)).json()
    assert all(r["id"] != nid for r in default)
    witharch = client.get("/notifications?include_archived=true", headers=auth(token)).json()
    assert any(r["id"] == nid and r["archived"] is True for r in witharch)

    # delete
    assert client.delete(f"/notifications/{nid}", headers=auth(token)).status_code == 200
    after = client.get("/notifications?include_archived=true", headers=auth(token)).json()
    assert all(r["id"] != nid for r in after)


def test_recipient_rbac(client):
    """A user can never read/mutate another user's notification (404, not 403 — no existence leak)."""
    emp = login(client, "employee@demo.local")
    mgr = login(client, "manager@demo.local")
    emp_id = _subject_id(client, emp)
    nid = _seed(emp_id, "Private note")

    # manager cannot mark-read, archive, or delete the employee's notification
    assert client.post(f"/notifications/{nid}/read", headers=auth(mgr)).status_code == 404
    assert client.post(f"/notifications/{nid}/archive", headers=auth(mgr)).status_code == 404
    assert client.delete(f"/notifications/{nid}", headers=auth(mgr)).status_code == 404
    # and never sees it in their own list
    assert all(r["id"] != nid for r in client.get("/notifications", headers=auth(mgr)).json())

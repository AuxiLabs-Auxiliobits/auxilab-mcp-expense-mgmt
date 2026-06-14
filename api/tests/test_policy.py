"""Agency policy-document upload/publish (SCOPING §7).

Covers: Finance-only RBAC (Employee/Manager 403), the maker-checker SoD (the publisher must
differ from the uploader), version bumping, listing, and the AGENT index callback. Runs
fully offline — uploads land in the local fallback dir and the ingestion enqueue is a no-op.
"""

from __future__ import annotations

import time

import jwt

from tests.conftest import auth, login


def _agent_token() -> str:
    # Mirrors the AGENT service principal the ingestion worker uses (HS256 dev secret).
    now = int(time.time())
    claims = {"sub": "llm-approver", "roles": ["agent"], "agency_id": None,
              "iat": now, "exp": now + 3600}
    return jwt.encode(claims, "dev-only-change-me", algorithm="HS256")


def _agency_id(client, admin_token: str) -> str:
    return client.get("/admin/agencies", headers=auth(admin_token)).json()[0]["id"]


def _upload(client, token, agency_id, name="wifi.txt", body=b"Wi-Fi capped at $100."):
    return client.post(
        f"/finance/policies/{agency_id}",
        files={"file": (name, body, "text/plain")},
        headers=auth(token),
    )


def test_employee_cannot_upload_policy(client):
    emp = login(client, "employee@demo.local")
    admin = login(client, "admin@demo.local")
    agency_id = _agency_id(client, admin)
    assert _upload(client, emp, agency_id).status_code == 403


def test_manager_cannot_upload_policy(client):
    mgr = login(client, "manager@demo.local")
    admin = login(client, "admin@demo.local")
    agency_id = _agency_id(client, admin)
    assert _upload(client, mgr, agency_id).status_code == 403


def test_finance_upload_creates_versioned_draft(client):
    fin = login(client, "finance@demo.local")
    admin = login(client, "admin@demo.local")
    agency_id = _agency_id(client, admin)

    r1 = _upload(client, fin, agency_id)
    assert r1.status_code == 201, r1.text
    p1 = r1.json()
    assert p1["version"] == 1
    assert p1["status"] == "draft"
    assert p1["doc_blob_uri"]

    r2 = _upload(client, fin, agency_id)
    assert r2.json()["version"] == 2  # versions bump per agency


def test_maker_checker_same_user_cannot_publish(client):
    fin = login(client, "finance@demo.local")
    admin = login(client, "admin@demo.local")
    agency_id = _agency_id(client, admin)

    policy = _upload(client, fin, agency_id).json()
    # Same Finance user who uploaded tries to publish → SoD violation.
    res = client.post(
        f"/finance/policies/{agency_id}/{policy['id']}/publish", headers=auth(fin)
    )
    assert res.status_code == 409, res.text


def test_different_checker_can_publish_and_agent_marks_indexed(client):
    fin = login(client, "finance@demo.local")
    admin = login(client, "admin@demo.local")  # Admin also has the capability → acts as checker
    agency_id = _agency_id(client, admin)

    policy = _upload(client, fin, agency_id).json()
    published = client.post(
        f"/finance/policies/{agency_id}/{policy['id']}/publish", headers=auth(admin)
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"

    # Ingestion worker reports success → indexed.
    cb = client.post(
        f"/finance/policies/{policy['id']}/indexed",
        json={"indexed": True, "chunks": 3},
        headers=auth(_agent_token()),
    )
    assert cb.status_code == 200, cb.text
    assert cb.json()["status"] == "indexed"


def test_list_policies_finance_only(client):
    fin = login(client, "finance@demo.local")
    admin = login(client, "admin@demo.local")
    emp = login(client, "employee@demo.local")
    agency_id = _agency_id(client, admin)
    _upload(client, fin, agency_id)

    assert client.get(f"/finance/policies/{agency_id}", headers=auth(fin)).status_code == 200
    assert client.get(f"/finance/policies/{agency_id}", headers=auth(emp)).status_code == 403

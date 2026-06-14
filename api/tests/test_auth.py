"""Proves the issuer-agnostic seam: a DbAuthProvider-minted token round-trips into the
same Principal the rest of the app consumes, and RBAC guards reject the wrong role."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _login(client, email, password="demo") -> str:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_login_and_me(client):
    token = _login(client, "employee@demo.local")
    r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "employee"
    assert body["scope"] == "self"  # derived from role, not stored


def test_bad_password_rejected(client):
    r = client.post("/auth/login", json={"email": "employee@demo.local", "password": "wrong"})
    assert r.status_code == 401


def test_rbac_guard_blocks_employee(client):
    token = _login(client, "employee@demo.local")
    r = client.get("/finance/probe", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_rbac_guard_allows_finance(client):
    token = _login(client, "finance@demo.local")
    r = client.get("/finance/probe", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["as"] == "finance"


def test_no_token_is_401(client):
    assert client.get("/me").status_code == 403  # HTTPBearer auto_error → 403 w/o creds

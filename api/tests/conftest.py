"""Test fixtures. Forces an isolated SQLite file and dev seeding BEFORE the app imports,
so each run starts from the seeded demo agencies/users."""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("APP_ENVIRONMENT", "dev")
os.environ.setdefault("APP_SEED_DEMO_DATA", "true")
# Pin local-password mode for the suite regardless of the dev .env (which may be entra/hybrid).
# OIDC/hybrid behaviour is covered by tests that construct those providers explicitly.
os.environ.setdefault("APP_AUTH_PROVIDER", "db")
# Isolate tests from any live Azure endpoints configured in api/.env — scan/advisory,
# storage, and messaging must run on their offline fallbacks deterministically (env vars
# override the .env file, and the Azure SDKs aren't installed in the test venv).
os.environ["APP_DOC_INTEL_ENDPOINT"] = ""
os.environ["APP_FOUNDRY_ENDPOINT"] = ""
os.environ["APP_SEARCH_ENDPOINT"] = ""
os.environ["APP_STORAGE_ACCOUNT_URL"] = ""
os.environ["APP_SERVICEBUS_NAMESPACE"] = ""
_db = os.path.join(tempfile.gettempdir(), "expense_api_test.db")
if os.path.exists(_db):
    os.remove(_db)
os.environ["APP_DATABASE_URL"] = f"sqlite:///{_db}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def login(client, email: str, password: str = "demo") -> str:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

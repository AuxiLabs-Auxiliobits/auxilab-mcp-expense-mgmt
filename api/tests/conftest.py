"""Test fixtures. Forces an isolated SQLite file and dev seeding BEFORE the app imports,
so each run starts from the seeded demo agencies/users."""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("APP_ENVIRONMENT", "dev")
os.environ.setdefault("APP_SEED_DEMO_DATA", "true")
# Background AI events write concurrently and contend on the shared SQLite test file; disable the
# wiring here and exercise the event handler directly in test_ai_platform instead.
os.environ.setdefault("APP_AI_BACKGROUND_EVENTS", "false")
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

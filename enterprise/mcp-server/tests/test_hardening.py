"""Tests for the enterprise hardening: config validation, retry policy, correlation ids,
token safety, and the receipts/users/health tools."""

from __future__ import annotations

import json

import httpx
import pytest

from expense_mcp import auth, client
from expense_mcp.client import ApiError
from expense_mcp.config import Config, ConfigError


# ── Config validation ────────────────────────────────────────────────────────
def test_config_rejects_bad_url(monkeypatch):
    monkeypatch.setenv("EXPENSE_API_URL", "not-a-url")
    with pytest.raises(ConfigError):
        Config.from_env()


def test_config_rejects_nonpositive_timeout(monkeypatch):
    monkeypatch.setenv("EXPENSE_API_URL", "http://localhost:8000")
    monkeypatch.setenv("EXPENSE_API_TIMEOUT", "0")
    with pytest.raises(ConfigError):
        Config.from_env()


def test_config_defaults(monkeypatch):
    for k in ("EXPENSE_API_URL", "EXPENSE_API_TIMEOUT", "EXPENSE_API_MAX_RETRIES", "EXPENSE_API_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    cfg = Config.from_env()
    assert cfg.api_url == "http://localhost:8000"
    assert cfg.timeout == 30.0 and cfg.max_retries == 2


# ── Retry policy + correlation id ─────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr("expense_mcp.client.time.sleep", lambda *_: None)


def _mock(handler):
    client.set_client(httpx.Client(base_url="http://test", transport=httpx.MockTransport(handler)))


def teardown_function():
    client.set_client(None)
    auth.clear_token()


def test_get_retries_transient_5xx_then_succeeds():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, json={"detail": "starting"})
        return httpx.Response(200, json={"ok": True})

    _mock(handler)
    assert client.get("/x") == {"ok": True}
    assert calls["n"] == 3  # 2 retries then success


def test_post_is_not_retried():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(503, json={"detail": "down"})

    _mock(handler)
    with pytest.raises(ApiError) as e:
        client.post("/x", json={})
    assert e.value.status == 503
    assert calls["n"] == 1  # POST never retried (no silent double-action)


def test_request_sends_correlation_id_and_token_not_logged(caplog):
    seen = {}

    def handler(req):
        seen["cid"] = req.headers.get("x-request-id")
        seen["auth"] = req.headers.get("authorization")
        return httpx.Response(200, json={})

    _mock(handler)
    auth.set_token("secret-token")
    with caplog.at_level("INFO"):
        client.get("/x")
    assert seen["cid"] and len(seen["cid"]) == 12
    assert seen["auth"] == "Bearer secret-token"
    # The token must never appear in logs.
    assert "secret-token" not in caplog.text
    assert "cid=" in caplog.text


# ── Tools: login error, receipts, users, health ──────────────────────────────
def test_login_missing_token_raises():
    from expense_mcp.tools import auth_tools
    _mock(lambda req: httpx.Response(200, json={"no_token": True}))
    with pytest.raises(ApiError):
        auth_tools.login("e@x", "pw")


def test_receipts_upload_and_download(tmp_path):
    from expense_mcp.tools import receipts
    src = tmp_path / "r.pdf"
    src.write_bytes(b"%PDF-1.4 hi")
    seen = {}

    def handler(req):
        if req.url.path.endswith("/receipt"):
            seen["upload_ct"] = req.headers.get("content-type", "")
            return httpx.Response(201, json={"id": "att1", "filename": "r.pdf"})
        if req.url.path.endswith("/content"):
            return httpx.Response(200, content=b"BYTES", headers={"content-type": "application/pdf"})
        return httpx.Response(404, json={})

    _mock(handler)
    auth.set_token("t")
    up = receipts.upload_receipt("s1", "li1", str(src))
    assert up["id"] == "att1" and "multipart/form-data" in seen["upload_ct"]
    dest = tmp_path / "out.pdf"
    dl = receipts.download_receipt("att1", str(dest))
    assert dest.read_bytes() == b"BYTES" and dl["bytes"] == 5


def test_users_tools_hit_endpoints():
    from expense_mcp.tools import users
    paths = []
    _mock(lambda req: (paths.append(req.url.path) or httpx.Response(200, json=[])))
    auth.set_token("t")
    users.list_users(is_active=True)
    users.get_user("u1")
    users.my_activity()
    assert paths == ["/admin/users", "/admin/users/u1", "/audit/me"]


def test_server_health_reports_reachability():
    from expense_mcp.tools import system
    _mock(lambda req: httpx.Response(200, json={"status": "ok"}))
    out = system.server_health()
    assert out["api_reachable"] is True
    assert out["server"] == "auxilab-mcp-expense-mgmt"
    assert "token" not in json.dumps(out).lower()  # never leaks the token

    _mock(lambda req: httpx.Response(500, json={"detail": "boom"}))
    out2 = system.server_health()
    assert out2["api_reachable"] is False

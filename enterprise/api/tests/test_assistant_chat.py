"""In-app AI Assistant bridge (`/assistant/chat`).

These are true integration tests: the bridge drives the real `expense_mcp` MCP tools, whose HTTP
calls are routed back into this same TestClient app (via ASGITransport) against the seeded test
DB. So we exercise the full path — NL → router → MCP tool → API → RBAC — with no live server and
no mocks of business logic. Confirms routing, explainability, guided flows, and role enforcement.
"""

from __future__ import annotations

import pytest

from expense_mcp import auth as mcp_auth
from expense_mcp import client as mcp_client
from tests.conftest import auth, login


@pytest.fixture(autouse=True)
def _route_mcp_into_test_app(client):
    """Make the MCP tools' HTTP calls hit this test app + seeded DB (not localhost:8000).

    The TestClient is itself a sync httpx client that drives the ASGI app, so we hand it to the
    MCP client layer — the bridge's tool calls then resolve in-process against the seeded DB.
    """
    mcp_client.set_client(client)
    yield
    mcp_client.close()  # reset to a fresh pooled client for other tests
    mcp_auth.clear_token()


def chat(client, token, message, context=None):
    r = client.post("/assistant/chat", json={"message": message, "context": context}, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def test_read_intent_runs_mcp_tool_with_explainability(client):
    token = login(client, "finance@demo.local")
    out = chat(client, token, "show me the spend dashboard")
    assert "get_dashboard_metrics" in out["tools_used"]      # action went through MCP
    assert "Spend overview" in out["reply"]
    assert out["actions"]                                    # explainability present
    assert out["confidence"] == "high"


def test_policy_intent_is_cited(client):
    token = login(client, "employee@demo.local")
    out = chat(client, token, "what is the per-meal limit?")
    assert out["tools_used"] == ["ask_policy"]
    assert out["reply"]
    assert any("policy" in a.lower() for a in out["actions"])


def test_role_enforced_employee_cannot_see_approvals(client):
    token = login(client, "employee@demo.local")
    out = chat(client, token, "show pending approvals")
    # The API returns 403; the bridge surfaces a friendly message and ran no tool successfully.
    assert "don't have access" in out["reply"].lower()
    assert out["confidence"] == "low"


def test_manager_sees_pending_queue(client):
    token = login(client, "manager@demo.local")
    out = chat(client, token, "show pending approvals")
    assert out["tools_used"] == ["get_pending_approvals"]


def test_whoami(client):
    token = login(client, "employee@demo.local")
    out = chat(client, token, "who am i?")
    assert out["tools_used"] == ["whoami"]
    assert "Employee" in out["reply"]


def test_fallback_is_low_confidence_and_suggests(client):
    token = login(client, "employee@demo.local")
    out = chat(client, token, "tell me a joke")
    assert out["tools_used"] == []
    assert out["confidence"] == "low"
    assert out["suggestions"]


def test_no_internal_ids_leak_in_listings(client):
    token = login(client, "finance@demo.local")
    out = chat(client, token, "list all users")
    # Numbered, human listing — no raw UUIDs in the reply.
    import re
    assert not re.search(r"[0-9a-f]{8}-?[0-9a-f]{4}", out["reply"])


def test_guided_create_slot_filling_then_creates(client):
    token = login(client, "employee@demo.local")
    t1 = chat(client, token, "create a new expense sheet")
    assert t1["needs"] == ["title"] and t1["context"]["pending"]["action"] == "create"

    t2 = chat(client, token, "Berlin Offsite", t1["context"])
    assert t2["needs"] == ["period"]                         # title captured, asks period

    t3 = chat(client, token, "2026-06", t2["context"])
    assert "create_expense" in t3["tools_used"]
    assert "Berlin Offsite" in t3["reply"]                   # original-case title preserved


def _build_submittable_sheet(client, etoken) -> None:
    """Employee builds + submits a sheet (so it lands in the manager's queue)."""
    sid = client.post("/sheets", json={"title": "Bridge Confirm Test", "period": "2026-06"},
                      headers=auth(etoken)).json()["id"]
    client.post(f"/sheets/{sid}/line-items", headers=auth(etoken), json={
        "amount": "40.00", "merchant": "Cafe", "expense_date": "2026-06-10",
        "category": "Meals & Entertainment", "receipt_total": "40.00",
        "receipt_datetime": "2026-06-10T13:00:00"})
    li = client.get(f"/sheets/{sid}", headers=auth(etoken)).json()["line_items"][0]["id"]
    client.post(f"/sheets/{sid}/line-items/{li}/receipt", headers=auth(etoken),
                files={"file": ("r.pdf", b"%PDF-1.4 receipt", "application/pdf")})
    client.post(f"/sheets/{sid}/submit", headers=auth(etoken))


def test_destructive_action_requires_confirmation(client):
    """Manager 'approve N' must confirm before the tool runs (human-in-the-loop)."""
    _build_submittable_sheet(client, login(client, "employee@demo.local"))
    mtoken = login(client, "manager@demo.local")
    listing = chat(client, mtoken, "show pending approvals")
    assert listing["context"]["last_list"], "expected a pending sheet to review"
    ref = listing["context"]["last_list"][0]["ref"]

    out = chat(client, mtoken, f"approve {ref}", listing["context"])
    # It asks to confirm and has NOT yet called approve_sheet.
    assert out["pending"] and out["pending"]["action"] == "approve"
    assert "approve_sheet" not in out["tools_used"]
    # Declining cancels without changing anything.
    cancelled = chat(client, mtoken, "no", out["context"])
    assert "cancelled" in cancelled["reply"].lower()

    # Re-issuing and confirming actually runs the MCP tool.
    again = chat(client, mtoken, f"approve {ref}", listing["context"])
    done = chat(client, mtoken, "yes", again["context"])
    assert "approve_sheet" in done["tools_used"]
    assert "approved" in done["reply"].lower()


def test_suggestions_are_screen_aware(client):
    token = login(client, "manager@demo.local")
    r = client.post("/assistant/suggestions", json={"screen": "manager"}, headers=auth(token))
    assert r.status_code == 200
    sugg = r.json()["suggestions"]
    assert sugg and any("approval" in s.lower() for s in sugg)

"""Business-tool tests — the authenticated adapters over the FastAPI backend.

No live API: an httpx.MockTransport stands in for the backend so we can assert each tool calls
the right endpoint with the bearer token, parses the response, paginates/filters, and maps
4xx to a friendly ApiError. Authorization itself lives in the API (exercised by the api suite);
here we verify the adapter forwards the token and surfaces 401/403 cleanly.
"""

from __future__ import annotations

import json

import httpx
import pytest

from expense_mcp import auth, client
from expense_mcp.client import ApiError
from expense_mcp.tools import approvals, auth_tools, dashboard, expenses, finance


@pytest.fixture
def api(monkeypatch):
    """Install a mock backend; returns the list of (method, path, body, auth_header) seen."""
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = None
        if request.content:
            try:
                body = json.loads(request.content)
            except ValueError:
                body = request.content
        calls.append({
            "method": request.method,
            "path": request.url.path,
            "query": dict(request.url.params),
            "body": body,
            "auth": request.headers.get("authorization"),
        })
        m, p = request.method, request.url.path
        if m == "POST" and p == "/auth/login":
            return httpx.Response(200, json={"access_token": "jwt-123"})
        if p == "/auth/me":
            return httpx.Response(200, json={"name": "Mona", "email": "m@x", "role": "manager", "agency_name": "Crispin"})
        if p == "/sheets":
            return httpx.Response(200, json=_SHEETS)
        if p == "/finance/sheets":
            return httpx.Response(200, json=_SHEETS)
        if p == "/manager/queue":
            return httpx.Response(200, json=[_SHEETS[0]])
        if p.endswith("/action"):
            return httpx.Response(200, json={"id": "s1", "status": "RETURNED_TO_EMPLOYEE", "_action": body})
        if p == "/reports/summary":
            return httpx.Response(200, json={"grand_total": "330.00", "compliance_rate_pct": 100.0})
        if p == "/finance/queue":
            return httpx.Response(200, json=[])
        if p == "/forbidden":
            return httpx.Response(403, json={"detail": "nope"})
        return httpx.Response(404, json={"detail": "not found"})

    client.set_client(httpx.Client(base_url="http://test", transport=httpx.MockTransport(handler)))
    auth.set_token("seed-token")
    yield calls
    client.set_client(None)
    auth.clear_token()


_SHEETS = [
    {"id": "s1", "title": "Trip A", "status": "IN_MANAGER_REVIEW", "total": "200.00",
     "line_items": [{"category": "Travel - Air", "amount": "200.00"}]},
    {"id": "s2", "title": "Lunch", "status": "DRAFT", "total": "40.00",
     "line_items": [{"category": "Meals & Entertainment", "amount": "40.00"}]},
]


def test_login_sets_token_and_returns_profile(api):
    auth.clear_token()
    out = auth_tools.login("manager@demo.local", "demo")
    assert out["role"] == "manager" and out["agency"] == "Crispin"
    assert auth.get_token() == "jwt-123"  # token captured for the session
    # the /auth/me call carried the new bearer token
    me_call = [c for c in api if c["path"] == "/auth/me"][-1]
    assert me_call["auth"] == "Bearer jwt-123"


def test_list_my_expenses_hits_endpoint_with_auth(api):
    rows = expenses.list_my_expenses()
    assert len(rows) == 2
    call = api[-1]
    assert call["method"] == "GET" and call["path"] == "/sheets"
    assert call["auth"] == "Bearer seed-token"


def test_approve_line_item_posts_correct_action(api):
    approvals.approve_line_item("s1", "li1", reason="ok")
    call = api[-1]
    assert call["method"] == "POST" and call["path"] == "/manager/sheets/s1/action"
    assert call["body"] == {"line_item_id": "li1", "action": "MANAGER_APPROVED", "reason": "ok"}


def test_return_to_employee_uses_info_requested(api):
    approvals.return_to_employee("s1", "li1", reason="add receipt")
    assert api[-1]["body"]["action"] == "INFO_REQUESTED"


def test_search_expenses_filters_and_paginates(api):
    res = expenses.search_expenses(scope="all", status="IN_MANAGER_REVIEW", limit=1, offset=0)
    assert res["count"] == 1  # only the IN_MANAGER_REVIEW sheet matches
    assert res["returned"] == 1
    assert res["results"][0]["id"] == "s1"
    assert res["total_amount"] == 200.0


def test_dashboard_metrics_passes_filters(api):
    dashboard.get_dashboard_metrics(period="2026-06")
    call = api[-1]
    assert call["path"] == "/reports/summary" and call["query"].get("period") == "2026-06"


def test_permission_error_maps_to_friendly_apierror(api):
    with pytest.raises(ApiError) as e:
        client.get("/forbidden")
    assert e.value.status == 403
    assert "permission" in e.value.message.lower()


def test_unauthenticated_maps_to_friendly_apierror(monkeypatch):
    def handler(request):
        return httpx.Response(401, json={"detail": "invalid token"})
    client.set_client(httpx.Client(base_url="http://test", transport=httpx.MockTransport(handler)))
    auth.set_token("x")
    try:
        with pytest.raises(ApiError) as e:
            finance.get_finance_queue()
        assert e.value.status == 401
    finally:
        client.set_client(None)
        auth.clear_token()


def test_tools_and_resources_registered():
    # Importing server registers every tool/resource/prompt on the shared instance.
    from expense_mcp import server  # noqa: F401
    assert server.mcp.name == "auxilab-mcp-expense-mgmt"

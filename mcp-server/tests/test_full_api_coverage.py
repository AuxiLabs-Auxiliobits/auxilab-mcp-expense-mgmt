"""Coverage tests for the tools added to cover the full backend API surface.

Asserts the new tools are registered and that each one calls the correct (method, path) on the
backend — using a MockTransport so no live server is needed. Authorization stays in the API; here
we only verify the adapter targets the right endpoint with the right verb."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from expense_mcp import auth, client
from expense_mcp.instance import mcp
from expense_mcp.tools import admin, ai_insights, expenses, finance, meta, notifications


def _capture():
    """Mock client that records (method, path) and returns a benign JSON body."""
    seen: list[tuple[str, str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append((req.method, req.url.path))
        if req.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json={"ok": True})

    client.set_client(httpx.Client(base_url="http://test", transport=httpx.MockTransport(handler)))
    return seen


def teardown_function():
    client.set_client(None)
    auth.clear_token()


NEW_TOOLS = {
    "list_agencies", "get_agency", "create_agency", "update_agency", "delete_agency",
    "create_user", "update_user", "deactivate_user", "assign_role",
    "get_value_sets", "get_periods", "list_notifications", "mark_notifications_read",
    "get_ai_recommendation", "get_ai_workspace", "get_ai_analytics", "submit_ai_feedback",
    "get_finance_audit", "list_agency_policies", "publish_agency_policy",
    "get_decisions", "discard_draft", "update_line_item", "remove_line_item",
}


def test_all_new_tools_are_registered():
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    missing = NEW_TOOLS - names
    assert not missing, f"unregistered new tools: {missing}"


@pytest.mark.parametrize(
    "fn, args, method, path",
    [
        (admin.list_agencies, (), "GET", "/admin/agencies"),
        (admin.get_agency, ("a1",), "GET", "/admin/agencies/a1"),
        (admin.create_agency, ("Acme",), "POST", "/admin/agencies"),
        (admin.update_agency, ("a1",), "PATCH", "/admin/agencies/a1"),
        (admin.delete_agency, ("a1",), "DELETE", "/admin/agencies/a1"),
        (admin.create_user, ("N", "e@x.io", "employee", "a1", "pw"), "POST", "/admin/users"),
        (admin.update_user, ("u1",), "PATCH", "/admin/users/u1"),
        (admin.deactivate_user, ("u1",), "DELETE", "/admin/users/u1"),
        (admin.assign_role, ("e@x.io", "manager"), "POST", "/admin/users/assign-role"),
        (meta.get_value_sets, (), "GET", "/meta/value-sets"),
        (meta.get_periods, (), "GET", "/meta/periods"),
        (notifications.list_notifications, (), "GET", "/notifications"),
        (notifications.mark_notifications_read, (), "POST", "/notifications/read"),
        (finance.get_finance_audit, (), "GET", "/finance/audit"),
        (finance.list_agency_policies, ("a1",), "GET", "/finance/policies/a1"),
        (finance.publish_agency_policy, ("a1", "p1"), "POST", "/finance/policies/a1/p1/publish"),
        (ai_insights.get_ai_workspace, (), "GET", "/ai/workspace"),
        (ai_insights.get_ai_analytics, (), "GET", "/ai/analytics"),
        (ai_insights.get_ai_recommendation, ("s1",), "GET", "/ai/sheets/s1/recommendation"),
        (ai_insights.submit_ai_feedback, ("r1",), "POST", "/ai/recommendations/r1/feedback"),
        (expenses.get_decisions, ("s1",), "GET", "/sheets/s1/decisions"),
        (expenses.discard_draft, ("s1",), "DELETE", "/sheets/s1"),
        (expenses.update_line_item, ("s1", "li1"), "PATCH", "/sheets/s1/line-items/li1"),
        (expenses.remove_line_item, ("s1", "li1"), "DELETE", "/sheets/s1/line-items/li1"),
    ],
)
def test_new_tool_hits_correct_endpoint(fn, args, method, path):
    seen = _capture()
    auth.set_token("t")
    fn(*args)
    assert (method, path) in seen, f"{fn.__name__} -> {seen}, expected {(method, path)}"

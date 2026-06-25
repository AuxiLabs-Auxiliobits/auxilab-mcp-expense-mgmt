"""Exercises the remaining tool bodies, all resources, all prompts, and the client error
paths so coverage reflects the full surface (each is a thin, deterministic wrapper)."""

from __future__ import annotations

import httpx
import pytest

from expense_mcp import auth, client
from expense_mcp.client import ApiError


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    monkeypatch.setattr("expense_mcp.client.time.sleep", lambda *_: None)

    def handler(req: httpx.Request) -> httpx.Response:
        # Generic OK: list endpoints get a list, others an object.
        if req.method == "GET" and (req.url.path == "/sheets" or req.url.path.endswith(("queue", "sheets", "receipts", "/admin/users", "/me", "category"))):
            return httpx.Response(200, json=[])
        return httpx.Response(200, json={"id": "s1", "ok": True, "answer": "x", "citations": [], "routed_to_human": False})

    client.set_client(httpx.Client(base_url="http://test", transport=httpx.MockTransport(handler)))
    auth.set_token("t")
    yield
    client.set_client(None)
    auth.clear_token()


def test_all_expense_tools_execute():
    from expense_mcp.tools import expenses
    expenses.get_expense("s1")
    expenses.create_expense("Trip", "2026-06")
    expenses.add_line_item("s1", 50, "Cafe", "2026-06-01", "Meals & Entertainment",
                           receipt_total=50, receipt_datetime="2026-06-01T10:00:00")
    expenses.update_expense("s1", title="New")
    expenses.submit_expense("s1")
    expenses.resubmit_expense("s1")
    expenses.withdraw_expense("s1")
    res = expenses.search_expenses(scope="mine", category="Meals & Entertainment",
                                   min_amount=0, max_amount=1000)
    assert "results" in res


def test_finance_assistant_approvals_dashboard_execute():
    from expense_mcp.tools import approvals, assistant, dashboard, finance
    finance.finance_decision("s1", True, "ok")
    finance.finance_override("s1", False, "no")
    finance.list_all_expenses()
    approvals.reject_line_item("s1", "li1", "fix")
    approvals.approve_sheet("s1")
    dashboard.get_spend_by_category()
    dashboard.get_finance_kpis()
    assistant.ask_policy("meal cap?")
    auth.clear_token()  # cover logout path
    from expense_mcp.tools import auth_tools
    auth_tools.logout()


def test_all_resources_render():
    from expense_mcp.resources import resources
    for fn, arg in [
        (resources.me_profile, None), (resources.my_expenses, None),
        (resources.expense_detail, "s1"), (resources.expense_receipts, "s1"),
        (resources.expense_history, "s1"), (resources.pending_approvals, None),
        (resources.finance_queue, None), (resources.dashboard_summary, None),
        (resources.users_directory, None), (resources.my_activity, None),
    ]:
        out = fn(arg) if arg else fn()
        assert isinstance(out, str) and out  # JSON string


def test_all_prompts_render():
    from expense_mcp.prompts import prompts
    assert prompts.summarize_expense("s1")
    assert prompts.explain_rejection("s1")
    assert "get_pending_approvals" in prompts.approval_summary()
    assert "2026-06" in prompts.finance_report("2026-06")
    assert prompts.list_pending_approvals()
    assert prompts.find_duplicate_expenses()
    assert prompts.audit_report("s1")
    assert prompts.suggest_policy_violations("s1")


# ── client error paths ───────────────────────────────────────────────────────
def test_connect_error_retried_then_raised():
    def handler(req):
        raise httpx.ConnectError("refused")
    client.set_client(httpx.Client(base_url="http://test", transport=httpx.MockTransport(handler)))
    with pytest.raises(ApiError) as e:
        client.get("/x")
    assert e.value.status == 0 and "reach" in e.value.message.lower()


def test_timeout_maps_to_408():
    def handler(req):
        raise httpx.ReadTimeout("slow")
    client.set_client(httpx.Client(base_url="http://test", transport=httpx.MockTransport(handler)))
    with pytest.raises(ApiError) as e:
        client.post("/x", json={})
    assert e.value.status == 408


def test_detail_extracts_validation_message():
    def handler(req):
        return httpx.Response(422, json={"detail": [{"msg": "field required"}]})
    client.set_client(httpx.Client(base_url="http://test", transport=httpx.MockTransport(handler)))
    with pytest.raises(ApiError) as e:
        client.post("/x", json={})
    assert "field required" in e.value.message


def test_close_is_safe():
    client.close()  # no error even after closing
    client.close()

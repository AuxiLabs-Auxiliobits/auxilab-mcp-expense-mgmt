"""Read-only MCP resources — addressable snapshots an AI can load as context. Each resolves
through the authenticated API client, so visibility matches the caller's role/agency."""

from __future__ import annotations

import json
from typing import Any

from expense_mcp import client
from expense_mcp.instance import mcp


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


@mcp.resource("me://profile")
def me_profile() -> str:
    """The current authenticated user (id, email, role, agency)."""
    return _json(client.get("/auth/me"))


@mcp.resource("expense://mine")
def my_expenses() -> str:
    """The caller's own expense sheets."""
    return _json(client.get("/sheets"))


@mcp.resource("expense://{sheet_id}")
def expense_detail(sheet_id: str) -> str:
    """One expense sheet with line items, totals, and status."""
    return _json(client.get(f"/sheets/{sheet_id}"))


@mcp.resource("expense://{sheet_id}/receipts")
def expense_receipts(sheet_id: str) -> str:
    """All receipts attached to a sheet (metadata)."""
    return _json(client.get(f"/sheets/{sheet_id}/receipts"))


@mcp.resource("expense://{sheet_id}/history")
def expense_history(sheet_id: str) -> str:
    """A sheet's approval/decision history (manager → finance → AI actions)."""
    return _json(client.get(f"/sheets/{sheet_id}/decisions"))


@mcp.resource("approvals://pending")
def pending_approvals() -> str:
    """Sheets awaiting manager review in the caller's agency."""
    return _json(client.get("/manager/queue"))


@mcp.resource("finance://queue")
def finance_queue() -> str:
    """Sheets routed to finance for manual review."""
    return _json(client.get("/finance/queue"))


@mcp.resource("dashboard://summary")
def dashboard_summary() -> str:
    """Dashboard summary: KPIs, spend-by-category, compliance (scoped to the caller)."""
    return _json(client.get("/reports/summary"))


@mcp.resource("users://directory")
def users_directory() -> str:
    """User directory (Admin only)."""
    return _json(client.get("/admin/users"))


@mcp.resource("activity://mine")
def my_activity() -> str:
    """The caller's own activity/audit trail."""
    return _json(client.get("/audit/me", params={"limit": 100}))

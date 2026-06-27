"""Expense Management MCP server — quickstart style.

Built by following the official MCP tutorial step-for-step:
https://modelcontextprotocol.io/docs/develop/build-server

Like the doc's weather server (which wraps the NWS API), this server is a thin
wrapper over the Expense Management FastAPI backend. The API enforces auth, RBAC,
agency-scope and audit — this MCP server adds no business logic of its own.

Run it:  uv run expense.py     (serves MCP over stdio)
"""

from __future__ import annotations

import os
import sys
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# ── Initialize FastMCP server ──────────────────────────────────────────────────
mcp = FastMCP("expense")

# ── Constants ──────────────────────────────────────────────────────────────────
EXPENSE_API_BASE = os.environ.get("EXPENSE_API_URL", "http://localhost:8000")

# Session bearer token: seeded from the environment, or set by the `login` tool.
# (In a stdio server we must NEVER print the token to stdout — it would corrupt the
# JSON-RPC stream. We only ever log to stderr.)
_token: str | None = os.environ.get("EXPENSE_API_TOKEN") or None


# ── Helper functions ───────────────────────────────────────────────────────────
async def make_api_request(method: str, path: str, json: dict | None = None) -> Any | None:
    """Make a request to the Expense API with proper error handling.

    Returns the parsed JSON body, or None on any failure (mirrors the doc's
    make_nws_request helper).
    """
    headers = {"Accept": "application/json"}
    if _token:
        headers["Authorization"] = f"Bearer {_token}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.request(
                method, f"{EXPENSE_API_BASE}{path}", headers=headers, json=json, timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:  # noqa: BLE001 — degrade gracefully like the doc's helper
            print(f"Expense API request failed: {e}", file=sys.stderr)  # stderr only!
            return None


def format_sheet(sheet: dict) -> str:
    """Format one expense sheet into a readable block."""
    return f"""
Title: {sheet.get("title", "Untitled")}
Status: {sheet.get("status", "unknown")}
Period: {sheet.get("period", "—")}
Total: {sheet.get("currency", "USD")} {sheet.get("total", "0")}
ID: {sheet.get("id", "—")}
"""


# ── Tools ──────────────────────────────────────────────────────────────────────
@mcp.tool()
async def login(email: str, password: str) -> str:
    """Sign in to the Expense API and start a session.

    Subsequent tool calls act as this user; the API enforces their role/permissions.

    Args:
        email: the user's email (e.g. employee@demo.local)
        password: the user's password (demo accounts use "demo")
    """
    global _token
    data = await make_api_request("POST", "/auth/login", json={"email": email, "password": password})
    if not data or "access_token" not in data:
        return "Login failed — check the email/password and that the API is running."
    _token = data["access_token"]
    me = await make_api_request("GET", "/auth/me") or {}
    return (
        f"Signed in as {me.get('name', email)} "
        f"({me.get('role', '?')}, {me.get('agency_name', '—')})."
    )


@mcp.tool()
async def list_my_expenses() -> str:
    """List the signed-in user's own expense sheets."""
    sheets = await make_api_request("GET", "/sheets")
    if sheets is None:
        return "Unable to fetch expenses — are you logged in and is the API running?"
    if not sheets:
        return "You have no expense sheets yet."
    return "\n---\n".join(format_sheet(s) for s in sheets)


@mcp.tool()
async def get_expense(sheet_id: str) -> str:
    """Get one expense sheet with its line items and status.

    Args:
        sheet_id: the expense sheet id
    """
    sheet = await make_api_request("GET", f"/sheets/{sheet_id}")
    if not sheet:
        return f"Could not find expense sheet {sheet_id}."
    lines = sheet.get("line_items", []) or []
    items = (
        "\n".join(
            f"  - {li.get('merchant', '?')} · {li.get('category', '?')} · "
            f"{li.get('currency', 'USD')} {li.get('amount', '0')} ({li.get('status', '?')})"
            for li in lines
        )
        or "  (no line items)"
    )
    return format_sheet(sheet) + f"\nLine items:\n{items}"


@mcp.tool()
async def get_pending_approvals() -> str:
    """List expense sheets awaiting your review (managers only)."""
    sheets = await make_api_request("GET", "/manager/queue")
    if sheets is None:
        return "Unable to fetch the approval queue — this needs a manager login."
    if not sheets:
        return "No sheets are waiting for your approval."
    return "\n---\n".join(format_sheet(s) for s in sheets)


# ── Running the server ─────────────────────────────────────────────────────────
def main() -> None:
    # Initialize and run the server over stdio (the transport MCP hosts launch).
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

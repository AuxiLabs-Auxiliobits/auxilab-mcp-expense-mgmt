"""Finance tools — manual-review queue + human decisions/overrides. Finance/Admin only
(enforced by the API); SoD prevents deciding on one's own sheet."""

from __future__ import annotations

from typing import Any

from expense_mcp import client
from expense_mcp.annotations import DESTRUCTIVE, READ
from expense_mcp.instance import mcp


@mcp.tool(annotations=READ)
def get_finance_queue() -> list[dict[str, Any]]:
    """List sheets the AI approver routed to a human for manual finance review."""
    return client.get("/finance/queue")


@mcp.tool(annotations=READ)
def list_all_expenses() -> list[dict[str, Any]]:
    """List every expense sheet org-wide (Finance/Admin); managers are scoped to their agency."""
    return client.get("/finance/sheets")


@mcp.tool(annotations=DESTRUCTIVE)
def finance_decision(sheet_id: str, approve: bool, reason: str) -> dict[str, Any]:
    """Resolve a routed (manual-review) sheet: approve or reject with a logged reason."""
    return client.post(f"/finance/sheets/{sheet_id}/decision", json={"approve": approve, "reason": reason})


@mcp.tool(annotations=DESTRUCTIVE)
def finance_override(sheet_id: str, approve: bool, reason: str) -> dict[str, Any]:
    """Override the AI approver's decision on a sheet (reason required, audited)."""
    return client.post(f"/finance/sheets/{sheet_id}/override", json={"approve": approve, "reason": reason})

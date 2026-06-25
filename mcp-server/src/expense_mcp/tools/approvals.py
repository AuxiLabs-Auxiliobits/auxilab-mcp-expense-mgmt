"""Manager approval tools. Agency-scope + segregation-of-duties are enforced by the API
(a manager can only action their own agency's sheets and never their own line items)."""

from __future__ import annotations

from typing import Any

from expense_mcp import client
from expense_mcp.annotations import DESTRUCTIVE, READ
from expense_mcp.instance import mcp


@mcp.tool(annotations=READ)
def get_pending_approvals() -> list[dict[str, Any]]:
    """List sheets awaiting manager review in the manager's own agency."""
    return client.get("/manager/queue")


@mcp.tool(annotations=DESTRUCTIVE)
def approve_line_item(sheet_id: str, line_item_id: str, reason: str | None = None) -> dict[str, Any]:
    """Approve a single line item. When every item is approved the sheet advances to finance."""
    return client.post(
        f"/manager/sheets/{sheet_id}/action",
        json={"line_item_id": line_item_id, "action": "MANAGER_APPROVED", "reason": reason},
    )


@mcp.tool(annotations=DESTRUCTIVE)
def reject_line_item(sheet_id: str, line_item_id: str, reason: str) -> dict[str, Any]:
    """Reject a line item (a reason is required). This returns the whole sheet to the employee."""
    return client.post(
        f"/manager/sheets/{sheet_id}/action",
        json={"line_item_id": line_item_id, "action": "MANAGER_REJECTED", "reason": reason},
    )


@mcp.tool(annotations=DESTRUCTIVE)
def return_to_employee(sheet_id: str, line_item_id: str, reason: str) -> dict[str, Any]:
    """Request more info on a line item — returns the sheet to the employee to fix and resubmit
    (the manager 'return' action)."""
    return client.post(
        f"/manager/sheets/{sheet_id}/action",
        json={"line_item_id": line_item_id, "action": "INFO_REQUESTED", "reason": reason},
    )


@mcp.tool(annotations=DESTRUCTIVE)
def approve_sheet(sheet_id: str) -> dict[str, Any]:
    """Approve a whole sheet (all not-yet-rejected items) and advance it to finance review."""
    return client.post(f"/manager/sheets/{sheet_id}/approve")

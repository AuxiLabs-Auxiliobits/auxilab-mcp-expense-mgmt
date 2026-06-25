"""Finance tools — manual-review queue + human decisions/overrides. Finance/Admin only
(enforced by the API); SoD prevents deciding on one's own sheet."""

from __future__ import annotations

from typing import Any

from expense_mcp import client
from expense_mcp.annotations import DESTRUCTIVE, READ, WRITE
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


# --- finance audit + agency policy documents ---------------------------------------------- #
@mcp.tool(annotations=READ)
def get_finance_audit(limit: int = 50) -> list[dict[str, Any]]:
    """The org-wide immutable audit log (most recent first). Finance/Admin only."""
    return client.get("/finance/audit", params={"limit": limit})


@mcp.tool(annotations=READ)
def list_agency_policies(agency_id: str) -> list[dict[str, Any]]:
    """List the policy-document versions for an agency (Finance/Admin)."""
    return client.get(f"/finance/policies/{agency_id}")


@mcp.tool(annotations=WRITE)
def upload_agency_policy(agency_id: str, file_path: str) -> dict[str, Any]:
    """Upload a new policy document version for an agency from a local file (Finance/Admin)."""
    import mimetypes
    import os

    from expense_mcp.client import ApiError

    if not os.path.isfile(file_path):
        raise ApiError(f"File not found: {file_path}")
    name = os.path.basename(file_path)
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    with open(file_path, "rb") as f:
        files = {"file": (name, f.read(), ctype)}
    return client.post(f"/finance/policies/{agency_id}", files=files)


@mcp.tool(annotations=WRITE)
def publish_agency_policy(agency_id: str, policy_id: str) -> dict[str, Any]:
    """Publish a policy-document version so it becomes the active policy (Finance/Admin)."""
    return client.post(f"/finance/policies/{agency_id}/{policy_id}/publish")

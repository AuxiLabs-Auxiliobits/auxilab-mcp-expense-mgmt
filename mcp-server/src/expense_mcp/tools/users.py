"""User-directory + audit tools. User management is Admin-only (enforced by the API);
`my_activity` is available to any authenticated user."""

from __future__ import annotations

from typing import Any

from expense_mcp import client
from expense_mcp.instance import mcp


@mcp.tool()
def list_users(is_active: bool | None = None) -> list[dict[str, Any]]:
    """List users (Admin only), optionally filtered by active state."""
    params = {"is_active": str(is_active).lower()} if is_active is not None else None
    return client.get("/admin/users", params=params)


@mcp.tool()
def get_user(user_id: str) -> dict[str, Any]:
    """Get one user's details (Admin only)."""
    return client.get(f"/admin/users/{user_id}")


@mcp.tool()
def my_activity(limit: int = 50) -> list[dict[str, Any]]:
    """The current user's own activity/audit trail (most recent first)."""
    return client.get("/audit/me", params={"limit": limit})

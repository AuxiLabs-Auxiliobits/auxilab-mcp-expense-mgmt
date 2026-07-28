"""Notification tools — read and clear the signed-in user's notifications (role-scoped by the API)."""

from __future__ import annotations

from typing import Any

from expense_mcp import client
from expense_mcp.annotations import READ, WRITE
from expense_mcp.instance import mcp


@mcp.tool(annotations=READ)
def list_notifications() -> list[dict[str, Any]]:
    """The current user's notifications, newest first (title, body, href, read, kind)."""
    return client.get("/notifications")


@mcp.tool(annotations=WRITE)
def mark_notifications_read() -> list[dict[str, Any]]:
    """Mark all of the current user's notifications as read."""
    return client.post("/notifications/read")

"""Reference-data tools — expense categories, currencies, and selectable periods. Useful for an
AI agent to validate inputs before building a sheet."""

from __future__ import annotations

from typing import Any

from expense_mcp import client
from expense_mcp.annotations import READ
from expense_mcp.instance import mcp


@mcp.tool(annotations=READ)
def get_value_sets() -> dict[str, Any]:
    """The allowed expense categories (types) and supported currencies."""
    return client.get("/meta/value-sets")


@mcp.tool(annotations=READ)
def get_periods() -> dict[str, Any]:
    """The selectable expense periods (rolling 12 months, 'YYYY-MM')."""
    return client.get("/meta/periods")

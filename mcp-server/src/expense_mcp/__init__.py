"""expense_mcp — stateless MCP server over expense_core (SCOPING §4, §11).

Wraps the five core-engine tools as MCP tools using the official Python MCP SDK
(`mcp`, FastMCP). The server holds no state: each tool calls into expense_core and
returns the engine's Pydantic result as JSON. RBAC, auth, and persistence live in the
API layer, never here (SCOPING §2 — "MCP tools stay stateless").

Published on PyPI as `auxilab-mcp-expense-mgmt`.
"""

from expense_mcp.server import mcp

__all__ = ["mcp"]

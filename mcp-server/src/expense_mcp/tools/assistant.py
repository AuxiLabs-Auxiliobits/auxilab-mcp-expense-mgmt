"""Policy-assistant tool — agency RAG over the policy document via the backend (Azure Foundry
when configured, offline composer otherwise). Cited, agency-scoped, routes to a human when
uncovered."""

from __future__ import annotations

from typing import Any

from expense_mcp import client
from expense_mcp.instance import mcp


@mcp.tool()
def ask_policy(query: str) -> dict[str, Any]:
    """Ask a natural-language question about the caller's agency expense policy. Returns a
    grounded `{answer, citations[], routed_to_human}` (cites the governing clauses)."""
    return client.post("/assistant/policy", json={"query": query})

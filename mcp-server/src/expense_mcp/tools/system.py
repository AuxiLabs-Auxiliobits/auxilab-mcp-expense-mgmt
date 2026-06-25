"""System / observability tools — readiness and server info for monitoring an MCP deployment.
Never exposes the bearer token (reports only whether one is present)."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

from expense_mcp import auth, client
from expense_mcp.annotations import READ
from expense_mcp.client import ApiError
from expense_mcp.config import config
from expense_mcp.instance import mcp


def _server_version() -> str:
    try:
        return version("auxilab-mcp-expense-mgmt")
    except PackageNotFoundError:
        return "unknown"


@mcp.tool(annotations=READ)
def server_health() -> dict[str, Any]:
    """Readiness check: server version, configured API URL, whether a session token is set, and
    whether the backend is reachable (pings the public health probe). Token value is never
    returned."""
    reachable, detail = True, "ok"
    try:
        client.get("/healthz")
    except ApiError as e:
        reachable, detail = False, e.message
    return {
        "server": "auxilab-mcp-expense-mgmt",
        "version": _server_version(),
        "api_url": config.api_url,
        "authenticated": auth.is_authenticated(),
        "api_reachable": reachable,
        "detail": detail,
    }

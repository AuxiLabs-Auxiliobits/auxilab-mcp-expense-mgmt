"""Bearer-token session for the business tools.

The token is resolved per call: a runtime token set by the `login` tool takes precedence,
otherwise the `EXPENSE_API_TOKEN` bootstrap token from config. Every backend call carries it,
so the API's existing JWT validation + RBAC + agency-scope + audit apply unchanged — the MCP
server never re-implements authorization.
"""

from __future__ import annotations

from expense_mcp.config import config

_runtime_token: str | None = None


def set_token(token: str | None) -> None:
    global _runtime_token
    _runtime_token = token


def clear_token() -> None:
    set_token(None)


def get_token() -> str | None:
    return _runtime_token or config.bootstrap_token


def is_authenticated() -> bool:
    return get_token() is not None

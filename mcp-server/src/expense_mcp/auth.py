"""Bearer-token session for the business tools.

The token is resolved per call from a `ContextVar` (set by the `login` tool, or by an embedding
host per request), falling back to the `EXPENSE_API_TOKEN` bootstrap token. Using a ContextVar
(not a plain global) keeps the token **isolated per request/async context** so an embedding host
— e.g. the in-app assistant bridge — can serve concurrent users without cross-talk. Every backend
call carries it, so the API's JWT validation + RBAC + agency-scope + audit apply unchanged; the
MCP server never re-implements authorization.
"""

from __future__ import annotations

import contextvars

from expense_mcp.config import config

_token_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "expense_mcp_token", default=None
)


def set_token(token: str | None) -> None:
    _token_var.set(token)


def clear_token() -> None:
    _token_var.set(None)


def get_token() -> str | None:
    return _token_var.get() or config.bootstrap_token


def is_authenticated() -> bool:
    return get_token() is not None

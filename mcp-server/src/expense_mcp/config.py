"""MCP server configuration (env-driven).

The business tools are a thin, authenticated adapter over the FastAPI backend, so the only
config they need is where that API lives, a request timeout, and an optional bootstrap token.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    api_url: str = os.getenv("EXPENSE_API_URL", "http://localhost:8000").rstrip("/")
    timeout: float = float(os.getenv("EXPENSE_API_TIMEOUT", "30"))
    # Optional bootstrap bearer token: every tool acts as this user (RBAC enforced by the
    # API). A `login` tool can also set it at runtime. Prefer setting this in the MCP client
    # config (e.g. Claude Desktop env) over committing it anywhere.
    bootstrap_token: str | None = os.getenv("EXPENSE_API_TOKEN") or None


config = Config()

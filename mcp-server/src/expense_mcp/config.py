"""MCP server configuration (env-driven), validated at load so misconfiguration fails fast
with a clear message instead of surfacing as opaque runtime errors.

The business tools are a thin, authenticated adapter over the FastAPI backend, so the only
config they need is where that API lives, a request timeout, and an optional bootstrap token.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


class ConfigError(RuntimeError):
    """Raised when the environment is misconfigured (clear, actionable message)."""


@dataclass(frozen=True)
class Config:
    api_url: str
    timeout: float
    max_retries: int
    # Optional bootstrap bearer token: every tool acts as this user (RBAC enforced by the
    # API). A `login` tool can also set it at runtime. Prefer the MCP host config "env".
    bootstrap_token: str | None

    @classmethod
    def from_env(cls) -> "Config":
        api_url = os.getenv("EXPENSE_API_URL", "http://localhost:8000").rstrip("/")
        parsed = urlparse(api_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ConfigError(
                f"EXPENSE_API_URL must be an http(s) URL, got {api_url!r}."
            )
        timeout = _positive_float("EXPENSE_API_TIMEOUT", 30.0)
        max_retries = int(_positive_float("EXPENSE_API_MAX_RETRIES", 2.0))
        token = os.getenv("EXPENSE_API_TOKEN") or None
        return cls(api_url=api_url, timeout=timeout, max_retries=max_retries, bootstrap_token=token)


def _positive_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except ValueError as e:
        raise ConfigError(f"{name} must be a number, got {raw!r}.") from e
    if value <= 0:
        raise ConfigError(f"{name} must be positive, got {value}.")
    return value


config = Config.from_env()

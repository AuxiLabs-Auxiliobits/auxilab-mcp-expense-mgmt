"""HTTP client for the FastAPI backend.

A single place that attaches the bearer token, applies a timeout, and maps backend responses
to either parsed JSON or a typed `ApiError` carrying a *user-friendly* message (never a stack
trace). All business tools go through here, so authorization, validation, and audit stay in
the API — this layer adds zero business logic.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from expense_mcp.auth import get_token
from expense_mcp.config import config

log = logging.getLogger("expense_mcp.client")

# Injectable so tests can supply an httpx.MockTransport-backed client.
_client: httpx.Client | None = None


class ApiError(Exception):
    """Backend call failed. `.message` is safe to surface to the AI/user."""

    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def set_client(client: httpx.Client | None) -> None:
    """Override the underlying client (tests)."""
    global _client
    _client = client


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(base_url=config.api_url, timeout=config.timeout)
    return _client


def _headers() -> dict[str, str]:
    token = get_token()
    return {"Authorization": f"Bearer {token}"} if token else {}


def _detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        return resp.text[:200] or resp.reason_phrase
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail and isinstance(detail[0], dict):
        return str(detail[0].get("msg", "invalid input"))
    if isinstance(detail, dict):
        return str(detail.get("error", detail))
    return resp.reason_phrase or "request failed"


def request(
    method: str,
    path: str,
    *,
    json: Any | None = None,
    params: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    raw: bool = False,
) -> Any:
    """Call the API and return parsed JSON (or raw (bytes, headers) when `raw`)."""
    try:
        resp = _get_client().request(
            method, path, json=json, params=params, files=files, headers=_headers()
        )
    except httpx.TimeoutException as e:
        raise ApiError("The Expense API took too long to respond. Please try again.", 408) from e
    except httpx.RequestError as e:
        raise ApiError(
            f"Could not reach the Expense API at {config.api_url}. Is it running?", 0
        ) from e

    log.info("%s %s -> %s", method, path, resp.status_code)

    if resp.status_code == 401:
        raise ApiError("Not authenticated. Set EXPENSE_API_TOKEN or call the `login` tool.", 401)
    if resp.status_code == 403:
        raise ApiError("You don't have permission to perform that action.", 403)
    if resp.status_code == 404:
        raise ApiError("Not found.", 404)
    if resp.status_code >= 400:
        raise ApiError(f"Request failed: {_detail(resp)}", resp.status_code)

    if raw:
        return resp.content, resp.headers
    if resp.status_code == 204 or not resp.content:
        return None
    return resp.json()


def get(path: str, **kw: Any) -> Any:
    return request("GET", path, **kw)


def post(path: str, **kw: Any) -> Any:
    return request("POST", path, **kw)


def patch(path: str, **kw: Any) -> Any:
    return request("PATCH", path, **kw)


def delete(path: str, **kw: Any) -> Any:
    return request("DELETE", path, **kw)

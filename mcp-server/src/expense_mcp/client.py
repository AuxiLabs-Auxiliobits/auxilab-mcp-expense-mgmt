"""HTTP client for the FastAPI backend.

A single pooled `httpx.Client` (connection reuse + keep-alive) that attaches the bearer token,
applies a timeout, retries transient failures on idempotent requests, tags each call with a
correlation id, and maps responses to either parsed JSON or a typed `ApiError` carrying a
*user-friendly* message — never a token, never a stack trace. All business tools go through
here, so authorization, validation, and audit stay in the API; this layer adds no business
logic.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

import httpx

from expense_mcp.auth import get_token
from expense_mcp.config import config

log = logging.getLogger("expense_mcp.client")

_IDEMPOTENT = {"GET", "HEAD", "OPTIONS"}
_RETRY_STATUS = {502, 503, 504}

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
    if _client is not None and client is None:
        try:
            _client.close()
        except Exception:  # noqa: BLE001
            pass
    _client = client


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            base_url=config.api_url,
            timeout=config.timeout,
            # Bounded, reused pool — keep-alive avoids a TCP/TLS handshake per tool call.
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _client


def close() -> None:
    """Close the pooled client (graceful shutdown)."""
    set_client(None)


def _headers(correlation_id: str) -> dict[str, str]:
    headers = {"X-Request-Id": correlation_id}
    token = get_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"  # never logged
    return headers


def _detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        return (resp.text[:200] or resp.reason_phrase) if resp.text else resp.reason_phrase
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
    """Call the API and return parsed JSON (or raw (bytes, headers) when `raw`).

    Transient failures (connection errors, timeouts, 502/503/504) are retried with a short
    backoff for idempotent methods only — never for POST/PATCH/DELETE, so an action is never
    silently repeated.
    """
    cid = uuid.uuid4().hex[:12]
    retryable = method.upper() in _IDEMPOTENT
    attempts = config.max_retries + 1 if retryable else 1
    last_exc: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            resp = _get_client().request(
                method, path, json=json, params=params, files=files, headers=_headers(cid)
            )
        except httpx.TimeoutException as e:
            last_exc = ApiError("The Expense API took too long to respond. Please try again.", 408)
            log.warning("cid=%s %s %s timeout (attempt %d/%d)", cid, method, path, attempt, attempts)
            if attempt < attempts:
                time.sleep(0.25 * attempt)
                continue
            raise last_exc from e
        except httpx.RequestError as e:
            last_exc = ApiError(
                f"Could not reach the Expense API at {config.api_url}. Is it running?", 0
            )
            log.warning("cid=%s %s %s connect error (attempt %d/%d)", cid, method, path, attempt, attempts)
            if attempt < attempts:
                time.sleep(0.25 * attempt)
                continue
            raise last_exc from e

        if resp.status_code in _RETRY_STATUS and attempt < attempts:
            log.warning("cid=%s %s %s -> %s (retrying)", cid, method, path, resp.status_code)
            time.sleep(0.25 * attempt)
            continue

        log.info("cid=%s %s %s -> %s", cid, method, path, resp.status_code)
        return _handle(resp, raw)

    raise last_exc or ApiError("Request failed.", 0)


def _handle(resp: httpx.Response, raw: bool) -> Any:
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

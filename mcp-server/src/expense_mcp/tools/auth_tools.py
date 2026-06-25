"""Authentication tools. `login` exchanges credentials for a bearer token held for the
session; all other tools then act as that user with the API enforcing their permissions."""

from __future__ import annotations

from typing import Any

from expense_mcp import auth, client
from expense_mcp.instance import mcp


@mcp.tool()
def login(email: str, password: str) -> dict[str, Any]:
    """Authenticate to the Expense API and start a session. Subsequent tool calls act as this
    user (the API enforces their role/permissions). Returns the signed-in profile."""
    token = client.post("/auth/login", json={"email": email, "password": password})["access_token"]
    auth.set_token(token)
    me = client.get("/auth/me")
    return {"ok": True, "name": me.get("name"), "email": me.get("email"),
            "role": me.get("role"), "agency": me.get("agency_name")}


@mcp.tool()
def whoami() -> dict[str, Any]:
    """Return the current authenticated user (id, email, role, agency). Use to confirm the
    session and the permissions tools will run under."""
    return client.get("/auth/me")


@mcp.tool()
def logout() -> dict[str, Any]:
    """End the current session (clears the in-memory token)."""
    auth.clear_token()
    return {"ok": True}

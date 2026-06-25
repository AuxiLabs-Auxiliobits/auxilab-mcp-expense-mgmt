"""Admin tools — agency and user management. Admin-only; the API enforces the MANAGE_AGENCY /
MANAGE_USERS capabilities, so a non-admin caller gets a friendly permission error."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from expense_mcp import client
from expense_mcp.annotations import DESTRUCTIVE, READ, WRITE
from expense_mcp.instance import mcp

_ROLES = "employee | manager | finance | admin"


# --- agencies ----------------------------------------------------------------------------- #
@mcp.tool(annotations=READ)
def list_agencies() -> list[dict[str, Any]]:
    """List all agencies with their user counts (admin only)."""
    return client.get("/admin/agencies")


@mcp.tool(annotations=READ)
def get_agency(agency_id: str) -> dict[str, Any]:
    """Get one agency by id (admin only)."""
    return client.get(f"/admin/agencies/{agency_id}")


@mcp.tool(annotations=WRITE)
def create_agency(name: str) -> dict[str, Any]:
    """Create a new agency (admin only)."""
    return client.post("/admin/agencies", json={"name": name})


@mcp.tool(annotations=WRITE)
def update_agency(agency_id: str, name: str | None = None, status: str | None = None) -> dict[str, Any]:
    """Rename an agency or change its status (admin only). Only provided fields change."""
    body = {k: v for k, v in {"name": name, "status": status}.items() if v is not None}
    return client.patch(f"/admin/agencies/{agency_id}", json=body)


@mcp.tool(annotations=DESTRUCTIVE)
def delete_agency(agency_id: str) -> dict[str, Any] | None:
    """Soft-delete (deactivate) an agency (admin only)."""
    return client.delete(f"/admin/agencies/{agency_id}")


# --- users -------------------------------------------------------------------------------- #
@mcp.tool(annotations=WRITE)
def create_user(
    name: str,
    email: str,
    role: Annotated[str, Field(description=_ROLES)],
    agency_id: str,
    password: str,
) -> dict[str, Any]:
    """Create a user in an agency with a role (admin only)."""
    return client.post("/admin/users", json={
        "name": name, "email": email, "role": role, "agency_id": agency_id, "password": password,
    })


@mcp.tool(annotations=WRITE)
def update_user(
    user_id: str,
    name: str | None = None,
    email: str | None = None,
    role: Annotated[str | None, Field(description=_ROLES)] = None,
    agency_id: str | None = None,
    is_active: bool | None = None,
    password: str | None = None,
) -> dict[str, Any]:
    """Update a user (admin only). Only provided fields change."""
    body = {k: v for k, v in {
        "name": name, "email": email, "role": role, "agency_id": agency_id,
        "is_active": is_active, "password": password,
    }.items() if v is not None}
    return client.patch(f"/admin/users/{user_id}", json=body)


@mcp.tool(annotations=DESTRUCTIVE)
def deactivate_user(user_id: str) -> dict[str, Any] | None:
    """Deactivate a user — they can no longer sign in (admin only)."""
    return client.delete(f"/admin/users/{user_id}")


@mcp.tool(annotations=WRITE)
def assign_role(email: str, role: Annotated[str, Field(description=_ROLES)]) -> dict[str, Any]:
    """Assign/change a user's role by email (admin only)."""
    return client.post("/admin/users/assign-role", json={"email": email, "role": role})

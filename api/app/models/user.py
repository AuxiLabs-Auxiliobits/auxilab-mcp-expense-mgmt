"""User (SCOPING §12.1). Bound to exactly one agency. `entra_object_id` is the
migration hook for the eventual Entra cutover (ADR-001)."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.base import new_id, utcnow
from app.principal import Role


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=new_id, primary_key=True)
    name: str
    email: str = Field(index=True, unique=True)
    role: Role
    agency_id: str | None = Field(default=None, foreign_key="agencies.id", index=True)

    # DbAuthProvider fields (retired once federated to Entra).
    password_hash: str | None = None
    is_active: bool = True

    # Entra migration hook — backfilled at cutover by matching email.
    entra_object_id: str | None = Field(default=None, index=True)

    created_at: datetime = Field(default_factory=utcnow)

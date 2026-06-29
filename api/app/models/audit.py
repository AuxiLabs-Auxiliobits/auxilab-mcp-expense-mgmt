"""AuditLog (SCOPING §3.3, §9, §12.1). Append-only — every authorization decision, state
transition, and permission-relevant action. Never updated or deleted in application code."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON
from sqlmodel import Field, SQLModel

from app.models.base import new_id, utcnow


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"

    id: str = Field(default_factory=new_id, primary_key=True)
    actor_id: str | None = None
    actor_role: str | None = None
    agency_id: str | None = None
    action: str = Field(index=True)
    entity: str | None = None  # e.g. "expense_sheet:<id>"
    before: dict | None = Field(default=None, sa_type=JSON)
    after: dict | None = Field(default=None, sa_type=JSON)
    timestamp: datetime = Field(default_factory=utcnow, index=True)

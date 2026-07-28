"""Agency (SCOPING §12.1). Soft-deleted, never hard-deleted while sheets reference it
(SCOPING §8 referential integrity)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel

from app.models.base import new_id, utcnow


class AgencyStatus(StrEnum):
    ACTIVE = "active"
    SOFT_DELETED = "soft_deleted"


class Agency(SQLModel, table=True):
    __tablename__ = "agencies"

    id: str = Field(default_factory=new_id, primary_key=True)
    name: str = Field(index=True, unique=True)
    status: AgencyStatus = Field(default=AgencyStatus.ACTIVE)
    created_by: str | None = None
    created_at: datetime = Field(default_factory=utcnow)

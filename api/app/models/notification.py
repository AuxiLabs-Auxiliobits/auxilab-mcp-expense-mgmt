"""Notification (SCOPING §6.4). Per-recipient, in-app notifications emitted on workflow
transitions (submitted, returned, approved, finance decision). Read state is per row."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.base import new_id, utcnow


class Notification(SQLModel, table=True):
    __tablename__ = "notifications"

    id: str = Field(default_factory=new_id, primary_key=True)
    recipient_id: str = Field(foreign_key="users.id", index=True)
    kind: str = "info"  # info | success | warning | error
    title: str
    body: str = ""
    href: str | None = None  # deep link, e.g. "/employee/sheets/<id>"
    read: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)

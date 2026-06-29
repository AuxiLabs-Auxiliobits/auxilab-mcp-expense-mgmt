"""Notification (SCOPING §3.4, §6.5). Per-recipient, event-driven in-app notifications
generated at workflow transitions (sheet submitted, returned, decided). Append-only except
for the `read` flag, which the recipient may flip via POST /notifications/read."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.base import new_id, utcnow


class Notification(SQLModel, table=True):
    __tablename__ = "notifications"

    id: str = Field(default_factory=new_id, primary_key=True)
    # The user who should see this. Indexed — every read is recipient-scoped.
    recipient_id: str = Field(foreign_key="users.id", index=True)
    agency_id: str | None = Field(default=None, index=True)

    kind: str = Field(default="info")  # success | warning | error | info (UI severity)
    icon: str = "notifications"  # Material icon name the bell menu renders
    title: str = ""
    body: str = ""
    href: str | None = None  # deep-link the UI navigates to on click

    # Loose reference to the originating entity (e.g. "expense_sheet:<id>") for traceability.
    entity: str | None = None

    read: bool = Field(default=False, index=True)
    # Archived notifications are hidden from the default inbox but kept for history.
    archived: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)

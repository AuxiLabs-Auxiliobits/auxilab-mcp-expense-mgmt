"""ExpenseSheet (SCOPING §5, §12.1). `id` is stable across resubmissions; `version`
increments each resubmission and full per-version history is retained."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.base import new_id, utcnow
from expense_core.schemas.enums import FinanceDecision, SheetStatus


class ExpenseSheet(SQLModel, table=True):
    __tablename__ = "expense_sheets"

    id: str = Field(default_factory=new_id, primary_key=True)
    employee_id: str = Field(foreign_key="users.id", index=True)
    agency_id: str = Field(foreign_key="agencies.id", index=True)

    title: str | None = None  # employee-supplied sheet title (change req)
    version: int = Field(default=1)  # increments on resubmission (SCOPING §5.1)
    status: SheetStatus = Field(default=SheetStatus.DRAFT, index=True)
    period: str | None = None  # "YYYY-MM" (month + year of the current year)

    submitted_at: datetime | None = None
    # The manager who last advanced/returned the sheet out of manager review (SCOPING §6.2).
    # Powers the manager's "Reviewed" history without scanning the audit log.
    manager_decided_by: str | None = Field(default=None, index=True)
    finance_decision: FinanceDecision | None = None
    finance_decided_by: str | None = None
    policy_version_used: str | None = None  # pinned at submission (SCOPING §7)

    # Optimistic-locking guard against concurrent edits (SCOPING §8).
    row_version: int = Field(default=1)

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

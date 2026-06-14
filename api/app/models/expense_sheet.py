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

    version: int = Field(default=1)  # increments on resubmission (SCOPING §5.1)
    status: SheetStatus = Field(default=SheetStatus.DRAFT, index=True)
    period: str | None = None  # e.g. "2026-06"

    submitted_at: datetime | None = None
    finance_decision: FinanceDecision | None = None
    finance_decided_by: str | None = None
    policy_version_used: str | None = None  # pinned at submission (SCOPING §7)

    # Optimistic-locking guard against concurrent edits (SCOPING §8).
    row_version: int = Field(default=1)

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

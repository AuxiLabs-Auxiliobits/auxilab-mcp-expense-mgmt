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

    # LLM finance-approver outcome surfaced to the Finance review UI (SCOPING §6.3). Recorded
    # by apply_llm_decision when the approver decides; `route_reason*` are only set when the
    # sheet is routed to a human (FINANCE_MANUAL_REVIEW).
    llm_confidence: float | None = None
    route_reason: str | None = None  # LOW_CONFIDENCE | AMBIGUOUS_CLAUSE | MISSING_POLICY | NUMERIC_DISAGREEMENT
    route_reason_detail: str | None = None

    # Employee's note added before resubmitting a returned sheet. Shown to the manager
    # when they review the resubmission so they know what was changed/explained.
    employee_note: str | None = None

    # Optimistic-locking guard against concurrent edits (SCOPING §8).
    row_version: int = Field(default=1)

    # SLA / aging escalation (SCOPING §6.4, §8). The highest level already alerted on for the
    # sheet's *current* wait, and when. The escalation job treats a prior alert as stale once
    # `updated_at` moves past `last_escalated_at` (i.e. the sheet changed stage), so aging
    # restarts per stage without every transition having to reset these.
    last_escalation_level: int = Field(default=0)
    last_escalated_at: datetime | None = None

    # Soft-archive: Finance/Manager can park any sheet out of the active queues.
    # The original status is preserved so the audit trail stays intact.
    is_archived: bool = Field(default=False)

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

"""Decision (SCOPING §12.1). One row per finance/approval decision, including LLM runs —
records model + policy version + cited clauses for full replayability (SCOPING §6.3, §9.2)."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.base import new_id, utcnow
from app.principal import Role


class Decision(SQLModel, table=True):
    __tablename__ = "decisions"

    id: str = Field(default_factory=new_id, primary_key=True)
    sheet_id: str = Field(foreign_key="expense_sheets.id", index=True)
    actor_id: str
    actor_role: Role
    action: str  # e.g. "APPROVED", "REJECTED_WITH_COMMENTS", "ROUTED_TO_HUMAN", "OVERRIDE"
    reason: str | None = None

    # Populated for LLM approver runs (reproducibility/audit).
    llm_model_version: str | None = None
    policy_version: str | None = None
    cited_clauses: str | None = None  # JSON-encoded list of clause refs

    timestamp: datetime = Field(default_factory=utcnow)

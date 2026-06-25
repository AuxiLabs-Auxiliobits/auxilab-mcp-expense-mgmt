"""Agentic layer tables (advisory only).

`AiRecommendation` is a per-sheet advisory analysis produced by the deterministic recommendation
engine (core-engine tools + risk heuristics). It NEVER changes sheet state — it records what the
AI *suggests*, with full explainability. `AiFeedback` captures human reaction (helpful / accepted
/ dismissed) for analytics. Both are append-only-ish: regenerating supersedes the prior row.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON
from sqlmodel import Field, SQLModel

from app.models.base import new_id, utcnow


class AiRecommendation(SQLModel, table=True):
    __tablename__ = "ai_recommendation"

    id: str = Field(default_factory=new_id, primary_key=True)
    sheet_id: str = Field(index=True)
    agency_id: str | None = None
    employee_id: str | None = None
    sheet_status: str | None = None  # status at generation time

    # --- the recommendation (advisory) ---
    summary: str = ""
    risk_score: float = 0.0  # 0..100
    risk_band: str = "low"  # low | medium | high
    policy_compliant: bool = True
    duplicate_likelihood: float = 0.0  # 0..1
    duplicate_band: str = "none"  # none | low | medium | high
    missing_info: list = Field(default_factory=list, sa_type=JSON)
    recommended_action: str = "review"  # advisory label, never executed
    confidence: str = "medium"  # low | medium | high

    # --- explainability (Phase 6) ---
    rationale: dict = Field(default_factory=dict, sa_type=JSON)  # why / data_analyzed / policies

    superseded: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)


class AiFeedback(SQLModel, table=True):
    __tablename__ = "ai_feedback"

    id: str = Field(default_factory=new_id, primary_key=True)
    recommendation_id: str = Field(index=True)
    sheet_id: str | None = None
    user_id: str = Field(index=True)
    helpful: bool | None = None  # thumbs up / down
    decision: str | None = None  # accepted | ignored | dismissed
    reason: str | None = None  # optional free text
    created_at: datetime = Field(default_factory=utcnow, index=True)

"""Pydantic v2 I/O contracts for the five tools (SCOPING §4).

Money is modelled as Decimal to avoid float drift in reconciliation/cap math.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from expense_core.schemas.enums import (
    Category,
    DuplicateRisk,
    PolicyCheckStatus,
    RecommendedAction,
)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --------------------------------------------------------------------------- #
# Shared input: a single expense line item (what the user/agent submits).
# --------------------------------------------------------------------------- #
class LineItemInput(_Model):
    employee_id: str
    category: Category | None = None
    amount: Decimal = Field(gt=Decimal("0"))
    currency: str = "USD"
    merchant: str
    description: str = ""
    expense_date: date
    receipt_datetime: datetime | None = None
    receipt_total: Decimal | None = None
    has_receipt: bool = False


# --------------------------------------------------------------------------- #
# 1) Policy Checker — pure rules, deterministic intake (Line 1).
# --------------------------------------------------------------------------- #
class PolicyViolation(_Model):
    code: str  # machine-readable, e.g. "RECEIPT_REQUIRED", "OVER_MEAL_LIMIT"
    message: str
    field: str | None = None


class PolicyResult(_Model):
    status: PolicyCheckStatus
    violations: list[PolicyViolation] = Field(default_factory=list)
    recommended_action: RecommendedAction


# --------------------------------------------------------------------------- #
# 2) Receipt Parser — LLM extract + deterministic reconciliation math.
# --------------------------------------------------------------------------- #
class ParsedLineItem(_Model):
    description: str
    amount: Decimal


class ReceiptParseResult(_Model):
    merchant: str
    receipt_datetime: datetime | None
    total: Decimal
    tax: Decimal
    line_items: list[ParsedLineItem] = Field(default_factory=list)
    payment_method: str | None = None
    reconciles: bool  # Σ line items + tax == total
    delta: Decimal  # total − (Σ items + tax); 0 when reconciles


# --------------------------------------------------------------------------- #
# 3) Category Classifier — LLM + keyword fallback.
# --------------------------------------------------------------------------- #
class CategoryResult(_Model):
    category: Category
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


# --------------------------------------------------------------------------- #
# 4) Duplicate Detector — pure rules.
# --------------------------------------------------------------------------- #
class DuplicateMatch(_Model):
    line_item_id: str
    reason: str  # "EXACT_KEY" | "NEAR_MATCH_WINDOW" | "INTRA_SHEET"
    receipt_datetime: datetime | None
    total: Decimal


class DuplicateResult(_Model):
    risk_score: float = Field(ge=0.0, le=1.0)
    risk: DuplicateRisk
    matches: list[DuplicateMatch] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# 5) Report Summariser — aggregation + LLM narrative.
# --------------------------------------------------------------------------- #
class ReportSummary(_Model):
    total_by_category: dict[Category, Decimal]
    violation_count: int
    total_at_risk: Decimal
    compliance_rate_pct: float = Field(ge=0.0, le=100.0)
    narrative: str

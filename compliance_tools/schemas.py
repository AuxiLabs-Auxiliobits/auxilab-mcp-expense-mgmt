"""Typed I/O contracts for the five compliance tools.

Money is modelled as ``Decimal`` throughout — never ``float`` — so reconciliation and
cap arithmetic stay exact. Every model forbids unknown fields and is frozen, which makes
tool results safe to cache, hash, and pass between threads.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Category(StrEnum):
    """The eight expense categories the classifier may return."""

    MEALS_ENTERTAINMENT = "Meals & Entertainment"
    TRAVEL_AIR = "Travel - Air"
    TRAVEL_HOTEL = "Travel - Hotel"
    TRAVEL_GROUND = "Travel - Ground"
    OFFICE_SUPPLIES = "Office Supplies"
    SOFTWARE_SUBSCRIPTIONS = "Software / Subscriptions"
    CLIENT_ENTERTAINMENT = "Client Entertainment"
    OTHER = "Other"


class PolicyCheckStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"  # non-blocking issues (e.g. classifier disagreement)


class RecommendedAction(StrEnum):
    ACCEPT = "accept"
    RETURN_TO_EMPLOYEE = "return_to_employee"
    REQUEST_RECEIPT = "request_receipt"


class DuplicateRisk(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"  # exact (employee, receipt_datetime, total) match → block


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --------------------------------------------------------------------------- #
# Shared input: a single expense line item.
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
# 1) Policy Checker
# --------------------------------------------------------------------------- #
class PolicyViolation(_Model):
    code: str  # machine-readable, e.g. "PROHIBITED_CATEGORY"
    message: str
    field: str | None = None


class PolicyResult(_Model):
    status: PolicyCheckStatus
    violations: list[PolicyViolation] = Field(default_factory=list)
    recommended_action: RecommendedAction


# --------------------------------------------------------------------------- #
# 2) Receipt Parser
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
    delta: Decimal  # total − (Σ items + tax); 0 when it reconciles


# --------------------------------------------------------------------------- #
# 3) Category Classifier
# --------------------------------------------------------------------------- #
class CategoryResult(_Model):
    category: Category
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


# --------------------------------------------------------------------------- #
# 4) Duplicate Detector
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


class HistoricalLineItem(_Model):
    """A previously recorded line item to compare a candidate against."""

    line_item_id: str
    employee_id: str
    receipt_datetime: datetime | None
    total: Decimal
    same_sheet: bool = False


class CandidateLineItem(_Model):
    """The line item being screened for duplicates."""

    employee_id: str
    receipt_datetime: datetime | None
    total: Decimal


# --------------------------------------------------------------------------- #
# 5) Report Summariser
# --------------------------------------------------------------------------- #
class SummaryLineItem(_Model):
    category: Category
    amount: Decimal
    is_compliant: bool


class ReportSummary(_Model):
    total_by_category: dict[Category, Decimal]
    violation_count: int
    total_at_risk: Decimal
    compliance_rate_pct: float = Field(ge=0.0, le=100.0)
    narrative: str

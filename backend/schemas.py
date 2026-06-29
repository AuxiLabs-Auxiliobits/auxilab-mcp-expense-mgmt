"""
ExpenseOps Pydantic Schemas
=============================
Pydantic v2 models used for request/response validation across the API.
Every model that reads from an ORM object has ``model_config = ConfigDict(from_attributes=True)``.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Employee
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class EmployeeRead(BaseModel):
    """Read-only representation of an employee."""
    employee_id: str
    name: str
    role: str
    department: str

    model_config = ConfigDict(from_attributes=True)

class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6, description="Password must be at least 6 characters")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Expense Claim
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ExpenseClaimCreate(BaseModel):
    """Payload for creating a new expense claim."""
    employee_id: str = Field(..., description="FK to employees table")
    amount: float = Field(..., gt=0, description="Expense amount (positive)")
    currency: str = Field(default="USD", max_length=3)
    category: str = Field(..., description="Expense category code")
    merchant_name: str = Field(..., max_length=255)
    transaction_date: date
    receipt_path: Optional[str] = None
    user_remarks: Optional[str] = None


class ExpenseClaimRead(BaseModel):
    """Full claim returned by GET endpoints."""
    claim_id: str
    employee_id: str
    employee_name: Optional[str] = None
    amount: float
    currency: str
    category: str
    merchant_name: str
    transaction_date: date
    submission_timestamp: Optional[datetime] = None
    status: str
    risk_score: float
    receipt_path: Optional[str] = None
    system_notes: Optional[str] = None
    ai_summary: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class PaginatedExpenses(BaseModel):
    items: list[ExpenseClaimRead]
    total: int
    page: int
    size: int


class ExpenseClaimUpdate(BaseModel):
    """Payload for updating/reviewing a claim."""
    status: Optional[str] = Field(
        None, description="New status: APPROVED, REJECTED, EXCEPTION_HOLD"
    )
    system_notes: Optional[str] = Field(
        None, description="Reviewer notes appended to system_notes"
    )
    risk_score: Optional[float] = None
    amount: Optional[float] = Field(
        None, gt=0, description="Updated expense amount"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Policy Rule
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PolicyRuleRead(BaseModel):
    """Read representation of a policy rule."""
    rule_id: str
    category: str
    max_amount: float
    allowed_roles: Any  # JSON-decoded list
    location_restrictions: Any
    requires_receipt: bool
    precedence: int

    model_config = ConfigDict(from_attributes=True)


class PolicyRuleCreate(BaseModel):
    """Payload for creating a new policy rule."""
    rule_id: str
    category: str
    max_amount: float
    allowed_roles: list[str] = Field(default_factory=list)
    location_restrictions: list[str] = Field(default_factory=list)
    requires_receipt: bool = True
    precedence: int = 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Engine Result Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PolicyCheckResult(BaseModel):
    """Output of the PolicyEngine."""
    status: str = Field(
        ..., description="PASS if compliant, EXCEPTION if any rule was violated"
    )
    failed_rules: list[str] = Field(
        default_factory=list,
        description="List of rule IDs that were violated",
    )
    risk_score: float = Field(
        default=0.0, description="Contribution to overall risk from policy check"
    )
    requires_manual_review: bool = False
    recommended_action: str = Field(
        default="auto_approve",
        description="Suggested next step: auto_approve | hold_for_review | reject",
    )


class RiskScoreResult(BaseModel):
    """Output of the RiskEngine."""
    score: float = Field(..., ge=0, le=100)
    level: str = Field(
        ..., description="LOW (0-35), MEDIUM (35-70), HIGH (70-100)"
    )
    factors: dict[str, Any] = Field(
        default_factory=dict,
        description="Breakdown of each risk factor and its weighted contribution",
    )
    recommended_action: str = Field(
        default="auto_approve",
        description="auto_approve | flag_for_review | escalate",
    )


class DuplicateCheckResult(BaseModel):
    """Output of the DuplicateEngine."""
    is_duplicate: bool = False
    matched_claims: list[str] = Field(
        default_factory=list,
        description="Claim IDs of matched duplicates",
    )
    similarity_score: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Highest similarity score among matches (0-1)",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AI / OCR Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class OCRExtractedReceipt(BaseModel):
    """Structured fields extracted from a receipt image or OCR text."""
    merchant: Optional[str] = None
    total_amount: Optional[float] = None
    tax: Optional[float] = None
    date: Optional[str] = None
    category: Optional[str] = None
    currency: Optional[str] = "USD"
    original_amount: Optional[float] = None
    original_currency: Optional[str] = None
    exchange_rate: Optional[float] = None
    receipt_path: Optional[str] = None
    line_items: list[str] = Field(default_factory=list)


class CategoryResult(BaseModel):
    """Result of AI-based expense categorization."""
    category_code: str = Field(..., description="e.g. MEALS, TRAVEL_AIR")
    category_name: str = Field(..., description="Human-readable category name")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Model confidence 0-1"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Dashboard & Summary Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ComplianceSummary(BaseModel):
    """Finance-ready compliance narrative and stats."""
    total_claims: int
    total_amount: float
    compliance_rate: float = Field(
        ..., description="% of claims that passed all policy checks"
    )
    violations_count: int
    duplicate_count: int
    high_risk_count: int
    narrative: str = Field(
        ..., description="Human-readable summary paragraph for finance team"
    )


class ChartData(BaseModel):
    """Chart data returned by the dashboard charts endpoint."""
    spend_by_category: dict[str, float] = Field(default_factory=dict)
    risk_distribution: list[dict[str, Any]] = Field(default_factory=list)
    monthly_trend: list[dict[str, Any]] = Field(default_factory=list)
    approval_status: dict[str, int] = Field(default_factory=dict)
    violations_by_employee: dict[str, int] = Field(default_factory=dict)


class DashboardMetrics(BaseModel):
    """Top-level KPIs for the dashboard."""
    total_expenses: int
    total_amount: float
    compliance_rate: float
    auto_pass_rate: float
    pending_count: int
    high_risk_count: int
    duplicate_count: int
    avg_risk_score: float

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Auth & User Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Token(BaseModel):
    access_token: str
    token_type: str

class OTPRequest(BaseModel):
    email: str

class UserSignup(BaseModel):
    name: str = Field(..., min_length=1)
    email: str
    password: str = Field(..., min_length=6, description="Minimum 6 characters")
    role: str
    department: str
    manager_id: Optional[str] = None
    otp_code: str
    master_key: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class ManagerRead(BaseModel):
    employee_id: str
    name: str
    role: str
    department: str
    model_config = ConfigDict(from_attributes=True)

class PasswordResetConfirm(BaseModel):
    email: str
    otp_code: str
    new_password: str = Field(..., min_length=6, description="Minimum 6 characters")

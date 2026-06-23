"""API request/response DTOs (SCOPING §9.1 — Pydantic is the authoritative server schema;
the frontend mirrors these with Zod)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.principal import Role
from app.value_sets import normalize_currency, validate_period
from expense_core.schemas.enums import Category, FinanceDecision, LineItemStatus, SheetStatus


# --- Auth ------------------------------------------------------------------ #
class LoginRequest(BaseModel):
    email: str
    password: str

    model_config = {
        "json_schema_extra": {"example": {"email": "employee@demo.local", "password": "demo"}}
    }


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    """The caller's identity for the UI: includes the display `name` and `agency_name`
    resolved from the DB (the bare Principal/token carries only ids)."""

    subject_id: str
    email: str
    role: str
    agency_id: str | None = None
    agency_name: str | None = None
    name: str | None = None
    scope: str


# --- Line items / sheets --------------------------------------------------- #
class LineItemCreate(BaseModel):
    category: Category | None = None  # the selected Expense Type
    expense_type_other: str | None = None  # required free text when category == "Other"
    amount: Decimal = Field(gt=Decimal("0"))
    currency: str = "USD"
    merchant: str
    description: str = ""
    expense_date: date
    receipt_datetime: datetime | None = None
    receipt_total: Decimal | None = None
    tax: Decimal | None = Field(default=None, ge=Decimal("0"))  # Tax / VAT
    # has_receipt is server-derived from attachments — not accepted from the client.

    @field_validator("currency")
    @classmethod
    def _currency(cls, v: str) -> str:
        return normalize_currency(v)

    @model_validator(mode="after")
    def _other_needs_text(self) -> "LineItemCreate":
        if self.category is Category.OTHER and not (self.expense_type_other or "").strip():
            raise ValueError("expense_type_other is required when category is 'Other'")
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "category": "Meals & Entertainment",
                "amount": "82.50",
                "currency": "USD",
                "merchant": "Olive Garden",
                "description": "Client dinner",
                "expense_date": "2026-06-10",
                "receipt_datetime": "2026-06-10T20:14:00",
                "receipt_total": "82.50",
                "tax": "6.50",
            }
        }
    }


class LineItemUpdate(BaseModel):
    """Partial update of a draft line item — only provided fields change."""

    category: Category | None = None
    expense_type_other: str | None = None
    amount: Decimal | None = Field(default=None, gt=Decimal("0"))
    currency: str | None = None
    merchant: str | None = None
    description: str | None = None
    expense_date: date | None = None
    receipt_datetime: datetime | None = None
    receipt_total: Decimal | None = None
    tax: Decimal | None = Field(default=None, ge=Decimal("0"))

    @field_validator("currency")
    @classmethod
    def _currency(cls, v: str | None) -> str | None:
        return normalize_currency(v) if v is not None else None


class SheetCreate(BaseModel):
    # Required — the sheet must be named (max 50 chars).
    title: str = Field(min_length=1, max_length=50)
    # Required — the form always picks a month/year (drives the submission cutoff); validated
    # against the rolling last-12-months window.
    period: str = Field(..., description="Calendar month 'YYYY-MM' within the last 12 months.")
    # Optional: create an empty draft (the two-step "Create draft & add items" flow) and add
    # line items incrementally, or pass them inline. A receipt is still required per item at submit.
    line_items: list[LineItemCreate] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title must not be blank")
        if len(v) > 50:
            raise ValueError("title must be at most 50 characters")
        return v

    @field_validator("period")
    @classmethod
    def _period(cls, v: str) -> str:
        return validate_period(v)

    model_config = {
        "json_schema_extra": {
            "example": {"title": "June client travel", "period": "2026-06", "line_items": []}
        }
    }


class SheetUpdate(BaseModel):
    """Edit a draft sheet's title/period (only while in DRAFT)."""

    title: str | None = Field(default=None, min_length=1, max_length=50)
    period: str | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("title must not be blank")
        if len(v) > 50:
            raise ValueError("title must be at most 50 characters")
        return v

    @field_validator("period")
    @classmethod
    def _period(cls, v: str | None) -> str | None:
        return validate_period(v) if v is not None else None


class AttachmentOut(BaseModel):
    id: str
    line_item_id: str
    file_type: str
    size: int
    blob_uri: str
    scan_status: str

    model_config = {"from_attributes": True}


class LineItemOut(BaseModel):
    id: str
    category: Category | None
    expense_type_other: str | None = None
    amount: Decimal
    currency: str
    merchant: str
    description: str
    expense_date: date
    receipt_datetime: datetime | None = None
    receipt_total: Decimal | None = None
    tax: Decimal | None = None
    has_receipt: bool = False
    receipt_count: int = 0  # set by the serializer from attachments
    manager_status: LineItemStatus
    policy_status: LineItemStatus | None

    model_config = {"from_attributes": True}


class PolicyFlags(BaseModel):
    """Draft-time policy preview counts for the sheet summary panel. These come from a
    non-mutating dry run of the baseline policy checker; the authoritative intake (which also
    persists ClaimChecks and runs duplicate detection) still runs at submission (SCOPING §6.1)."""

    errors: int = 0  # blocking violations (policy status FAIL)
    warnings: int = 0  # non-blocking issues (policy status WARN)


class SheetOut(BaseModel):
    id: str
    title: str | None = None
    employee_id: str
    employee_name: str | None = None  # resolved from employee_id for display
    agency_id: str
    agency_name: str | None = None  # resolved from agency_id for display
    version: int
    status: SheetStatus
    period: str | None
    finance_decision: FinanceDecision | None
    line_items: list[LineItemOut] = Field(default_factory=list)

    # Computed totals. `total` is the plain sum of line-item amounts; it is only meaningful
    # when the sheet uses a single currency. `currency` is that sole currency, "USD" for an
    # empty sheet, or None when items mix currencies — in which case read totals_by_currency.
    total: Decimal = Decimal("0")
    currency: str | None = None
    totals_by_currency: dict[str, Decimal] = Field(default_factory=dict)

    # Summary-panel metrics.
    missing_receipts: int = 0  # line items with no receipt attached
    policy_flags: PolicyFlags = Field(default_factory=PolicyFlags)

    # Submit gating for the "Submit for Review" button (mirrors the server submit pre-checks).
    can_submit: bool = False
    submit_blockers: list[str] = Field(default_factory=list)

    # Timestamps (from the model) for "updated N days ago" and the workflow stepper.
    created_at: datetime | None = None
    updated_at: datetime | None = None
    submitted_at: datetime | None = None

    model_config = {"from_attributes": True}


class DecisionOut(BaseModel):
    """One entry in a sheet's decision trail (manager/finance/LLM actions, SCOPING §12.1)."""

    id: str
    actor_id: str
    actor_role: Role
    action: str
    reason: str | None = None
    llm_model_version: str | None = None
    policy_version: str | None = None
    cited_clauses: list[str] = Field(default_factory=list)  # decoded from the stored JSON
    timestamp: datetime


class ValueSetsOut(BaseModel):
    """Dropdown value sets for the expense-sheet form (expense types + currencies)."""

    expense_types: list[str]
    currencies: list[str]


class PeriodOption(BaseModel):
    value: str  # 'YYYY-MM'
    label: str  # 'Jan 2026'
    is_current: bool


class PeriodsOut(BaseModel):
    """Selectable expense periods for the form (rolling last 12 months, newest first)."""

    default: str  # the current month ('YYYY-MM') — preselect this
    periods: list[PeriodOption]


# --- Reports (finance/manager dashboard, SCOPING §4 report summariser) ------ #
class CategoryTotal(BaseModel):
    category: str
    total: Decimal


class ReportSummaryOut(BaseModel):
    """KPI tiles + spend-by-category + compliance for the dashboard.

    Numbers are computed deterministically (engine report summariser); the narrative is
    templated offline / LLM-written when a gateway is wired. Scope follows the caller's role
    (manager → own agency; finance/admin → all, optionally filtered by `agency_id`)."""

    period: str | None
    agency_id: str | None  # the scope actually applied (None = all agencies)
    sheet_count: int
    line_item_count: int
    grand_total: Decimal
    total_at_risk: Decimal
    violation_count: int
    compliance_rate_pct: float
    by_category: list[CategoryTotal]
    by_status: dict[str, int]
    narrative: str


# --- Manager / finance actions --------------------------------------------- #
class ManagerActionRequest(BaseModel):
    line_item_id: str
    action: LineItemStatus  # MANAGER_APPROVED | MANAGER_REJECTED | INFO_REQUESTED
    reason: str | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "line_item_id": "<paste a line_item id from GET /manager/queue>",
                "action": "MANAGER_APPROVED",
                "reason": "Within meal cap; receipt matches.",
            }
        }
    }


class FinanceHumanDecisionRequest(BaseModel):
    approve: bool
    reason: str

    model_config = {
        "json_schema_extra": {
            "example": {"approve": True, "reason": "Justified client-entertainment over-limit."}
        }
    }


class LlmDecisionRequest(BaseModel):
    """Posted by the LLM approver worker (SCOPING §6.3)."""

    decision: FinanceDecision
    model_version: str
    policy_version: str
    cited_clauses: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)

    model_config = {
        "json_schema_extra": {
            "example": {
                "decision": "APPROVED",
                "model_version": "gpt-4o@2026-05",
                "policy_version": "crispin-v3",
                "cited_clauses": ["§4.2 meal cap", "§7 receipt threshold"],
                "confidence": 0.92,
            }
        }
    }


# --- Admin ----------------------------------------------------------------- #
class AgencyCreate(BaseModel):
    name: str

    model_config = {"json_schema_extra": {"example": {"name": "Northwind"}}}


class AgencyUpdate(BaseModel):
    """Partial update — only provided fields change."""

    name: str | None = None
    status: str | None = None  # active | soft_deleted


class UserCreate(BaseModel):
    name: str
    email: str
    role: str
    agency_id: str | None = None
    password: str | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "New Hire",
                "email": "newhire@demo.local",
                "role": "employee",
                "agency_id": "<paste an agency id from GET /admin/agencies>",
                "password": "demo",
            }
        }
    }


class UserUpdate(BaseModel):
    """Partial update — only provided fields change. `password` re-hashes; omit to keep."""

    name: str | None = None
    email: str | None = None
    role: str | None = None
    agency_id: str | None = None
    is_active: bool | None = None
    password: str | None = None


class UserOut(BaseModel):
    """User as returned by the API — never exposes `password_hash`."""

    id: str
    name: str
    email: str
    role: str
    agency_id: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Agency policy documents (RAG, SCOPING §7) ----------------------------- #
class PolicyOut(BaseModel):
    """An agency policy-document version as returned by the API."""

    id: str
    agency_id: str
    version: int
    doc_blob_uri: str | None
    effective_date: date | None
    indexed_at: datetime | None
    created_by: str | None  # maker (Finance who uploaded)
    published_by: str | None  # checker (different Finance/Admin who published)
    created_at: datetime
    status: str = "draft"  # derived (set by the router): draft | published | indexed

    model_config = {"from_attributes": True}


class PolicyIndexedCallback(BaseModel):
    """Posted by the ingestion worker once AI Search upsert completes (or fails)."""

    indexed: bool
    chunks: int = 0
    detail: str | None = None


# --- Agency read DTO (adds the live user_count the admin table shows) ------ #
class AgencyOut(BaseModel):
    id: str
    name: str
    status: str
    created_by: str | None = None
    created_at: datetime
    user_count: int = 0

    model_config = {"from_attributes": True}


# --- Role assignment (admin quick-assign by email) ------------------------- #
class AssignRoleRequest(BaseModel):
    email: str
    role: str

    model_config = {
        "json_schema_extra": {"example": {"email": "manager@demo.local", "role": "manager"}}
    }


# --- Reports: spend-by-category + finance KPIs ----------------------------- #
class SpendByCategoryOut(BaseModel):
    """One bar in the spend-by-category chart."""

    category: str
    amount: Decimal


class FinanceKpisOut(BaseModel):
    """Real, deterministically-computed finance KPIs (SCOPING §4). AI-quality metrics that
    require ground-truth labels (accuracy, false-positive rate, SLA) are intentionally omitted
    here — the client fills those from its baseline until a metrics pipeline emits them."""

    auto_approval_rate: float  # % of finance-reached sheets the LLM auto-approved
    manual_interventions: int  # sheets currently routed to a human
    policy_citations: int  # decisions that cited at least one policy clause
    policy_compliance_rate: float  # % of line items with no rejection / policy failure
    finance_reached: int  # denominator: sheets that reached a finance outcome


# --- Notifications --------------------------------------------------------- #
class NotificationOut(BaseModel):
    id: str
    kind: str
    icon: str
    title: str
    body: str
    href: str | None
    read: bool
    timestamp: datetime

    model_config = {"from_attributes": True}

"""API request/response DTOs (SCOPING §9.1 — Pydantic is the authoritative server schema;
the frontend mirrors these with Zod)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from expense_core.schemas.enums import Category, FinanceDecision, LineItemStatus, SheetStatus


# --- Auth ------------------------------------------------------------------ #
class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Line items / sheets --------------------------------------------------- #
class LineItemCreate(BaseModel):
    category: Category | None = None
    amount: Decimal = Field(gt=Decimal("0"))
    currency: str = "USD"
    merchant: str
    description: str = ""
    expense_date: date
    receipt_datetime: datetime | None = None
    receipt_total: Decimal | None = None
    has_receipt: bool = False


class SheetCreate(BaseModel):
    period: str | None = None
    line_items: list[LineItemCreate] = Field(min_length=1)


class LineItemOut(BaseModel):
    id: str
    category: Category | None
    amount: Decimal
    currency: str
    merchant: str
    description: str
    expense_date: date
    manager_status: LineItemStatus
    policy_status: LineItemStatus | None

    model_config = {"from_attributes": True}


class SheetOut(BaseModel):
    id: str
    employee_id: str
    agency_id: str
    version: int
    status: SheetStatus
    period: str | None
    finance_decision: FinanceDecision | None
    line_items: list[LineItemOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# --- Manager / finance actions --------------------------------------------- #
class ManagerActionRequest(BaseModel):
    line_item_id: str
    action: LineItemStatus  # MANAGER_APPROVED | MANAGER_REJECTED | INFO_REQUESTED
    reason: str | None = None


class FinanceHumanDecisionRequest(BaseModel):
    approve: bool
    reason: str


class LlmDecisionRequest(BaseModel):
    """Posted by the LLM approver worker (SCOPING §6.3)."""

    decision: FinanceDecision
    model_version: str
    policy_version: str
    cited_clauses: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


# --- Admin ----------------------------------------------------------------- #
class AgencyCreate(BaseModel):
    name: str


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

"""LineItem (SCOPING §5, §12.1). Each carries its own manager verdict and policy verdict.

DB unique constraint on (employee_id, receipt_datetime, receipt_total) enforces the
duplicate key (SCOPING §6.1, §12.1) in addition to the detector tool.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.base import new_id
from expense_core.schemas.enums import Category, LineItemStatus


class LineItem(SQLModel, table=True):
    __tablename__ = "line_items"
    __table_args__ = (
        UniqueConstraint(
            "employee_id", "receipt_datetime", "receipt_total", name="uq_line_item_dedupe_key"
        ),
    )

    id: str = Field(default_factory=new_id, primary_key=True)
    sheet_id: str = Field(foreign_key="expense_sheets.id", index=True)
    employee_id: str = Field(foreign_key="users.id", index=True)

    category: Category | None = None  # the selected Expense Type (value set incl. "Other")
    expense_type_other: str | None = None  # free text when category == OTHER
    amount: Decimal = Field(sa_type=Numeric(12, 2))
    currency: str = "USD"
    expense_date: date
    merchant: str
    description: str = ""

    receipt_datetime: datetime | None = None
    receipt_total: Decimal | None = Field(default=None, sa_type=Numeric(12, 2))
    tax: Decimal | None = Field(default=None, sa_type=Numeric(12, 2))  # Tax / VAT
    # Server-derived from attachment presence; a receipt is mandatory at submission.
    has_receipt: bool = False

    # Receipt scan vs entered-amount: flag for Finance when they don't reconcile or the
    # receipt couldn't be read confidently (not shown to the employee; SCOPING §6.3).
    needs_human_review: bool = False
    review_reason: str | None = None

    # Manager verdict (Line 2).
    manager_status: LineItemStatus = Field(default=LineItemStatus.PENDING_MANAGER)
    manager_actor_id: str | None = None
    manager_reason: str | None = None

    # Finance/LLM verdict (Line 3).
    policy_status: LineItemStatus | None = None
    policy_clause_ref: str | None = None

"""ClaimCheck (SCOPING §12.1). The intake (Line 1) tool outputs persisted per line item:
policy / category / duplicate / receipt results, for audit and replay."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON
from sqlmodel import Field, SQLModel

from app.models.base import new_id, utcnow


class ClaimCheck(SQLModel, table=True):
    __tablename__ = "claim_checks"

    id: str = Field(default_factory=new_id, primary_key=True)
    line_item_id: str = Field(foreign_key="line_items.id", index=True)
    sheet_version: int = Field(default=1)

    policy_result: dict | None = Field(default=None, sa_type=JSON)
    category_result: dict | None = Field(default=None, sa_type=JSON)
    duplicate_result: dict | None = Field(default=None, sa_type=JSON)
    receipt_result: dict | None = Field(default=None, sa_type=JSON)

    created_at: datetime = Field(default_factory=utcnow)

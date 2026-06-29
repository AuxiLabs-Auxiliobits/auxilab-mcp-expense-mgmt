"""AgencyPolicy (SCOPING §7, §12.1). RAG-indexed, version-pinned agency finance policy
documents. Maker-checker: Finance edits content, re-index on publish."""

from __future__ import annotations

from datetime import date, datetime

from sqlmodel import Field, SQLModel

from app.models.base import new_id, utcnow


class AgencyPolicy(SQLModel, table=True):
    __tablename__ = "agency_policies"

    id: str = Field(default_factory=new_id, primary_key=True)
    agency_id: str = Field(foreign_key="agencies.id", index=True)
    version: int = Field(default=1)
    doc_blob_uri: str | None = None
    effective_date: date | None = None
    indexed_at: datetime | None = None  # set when AI Search upsert completes
    created_by: str | None = None  # maker (Finance)
    published_by: str | None = None  # checker (Finance/Admin)
    created_at: datetime = Field(default_factory=utcnow)

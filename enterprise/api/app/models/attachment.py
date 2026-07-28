"""Attachment (SCOPING §5, §12.1). One or more per line item; stored in Blob, scanned
and OCR'd before processing (SCOPING §6.1)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel

from app.models.base import new_id, utcnow


class ScanStatus(StrEnum):
    PENDING = "pending"
    CLEAN = "clean"
    INFECTED = "infected"
    FAILED = "failed"


class OcrStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class Attachment(SQLModel, table=True):
    __tablename__ = "attachments"

    id: str = Field(default_factory=new_id, primary_key=True)
    line_item_id: str = Field(foreign_key="line_items.id", index=True)
    blob_uri: str
    filename: str | None = None  # original upload name (for display + download Content-Disposition)
    file_type: str
    size: int
    scan_status: ScanStatus = Field(default=ScanStatus.PENDING)
    ocr_status: OcrStatus = Field(default=OcrStatus.PENDING)
    uploaded_at: datetime = Field(default_factory=utcnow)

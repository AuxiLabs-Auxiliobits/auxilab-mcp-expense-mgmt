"""Receipt library (unassigned uploads).

A receipt the employee uploaded on the "My Receipts" page but has not yet attached to a
line item. Unlike `Attachment` (which requires a `line_item_id`), these stand alone: the
bytes are stored in Blob immediately and the row is owner- and agency-scoped, so the pool
survives refreshes and is the same on every device. "Attaching" one moves it into a real
`Attachment` (via the existing attach path) and deletes the library row.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.attachment import OcrStatus, ScanStatus
from app.models.base import new_id, utcnow


class ReceiptUpload(SQLModel, table=True):
    __tablename__ = "receipt_uploads"

    id: str = Field(default_factory=new_id, primary_key=True)
    owner_id: str = Field(foreign_key="users.id", index=True)  # the uploading employee
    agency_id: str | None = Field(default=None, index=True)  # scope (taken from the token)
    blob_uri: str
    filename: str | None = None  # original upload name (display + download Content-Disposition)
    file_type: str
    size: int
    scan_status: ScanStatus = Field(default=ScanStatus.PENDING)
    ocr_status: OcrStatus = Field(default=OcrStatus.PENDING)
    uploaded_at: datetime = Field(default_factory=utcnow, index=True)

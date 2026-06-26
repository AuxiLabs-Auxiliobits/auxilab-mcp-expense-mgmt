"""Receipt library (unassigned uploads) — service layer.

The employee uploads receipts on the "My Receipts" page before they belong to any sheet;
the bytes go to Blob immediately and a `ReceiptUpload` row holds the metadata, owner- and
agency-scoped. When adding a line item, the employee picks one and it is "attached": the
bytes flow through the SAME `sheet_service.attach_receipt` path (so the resulting
`Attachment` is identical to a direct upload — validation, blob naming, audit, scan-
readiness) and the library row is removed.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models.attachment import Attachment
from app.models.expense_sheet import ExpenseSheet
from app.models.line_item import LineItem
from app.models.receipt_upload import ReceiptUpload
from app.principal import Principal
from app.services import audit_service, sheet_service
from app.storage import delete_receipt_blob, read_receipt_blob, upload_receipt_blob
from app.value_sets import MAX_RECEIPT_BYTES, receipt_extension


def list_for(session: Session, actor: Principal) -> list[ReceiptUpload]:
    """The caller's own unassigned receipts, newest first."""
    return list(
        session.exec(
            select(ReceiptUpload)
            .where(ReceiptUpload.owner_id == actor.subject_id)
            .order_by(ReceiptUpload.uploaded_at.desc())  # type: ignore[attr-defined]
        ).all()
    )


def get_owned_or_404(session: Session, actor: Principal, receipt_id: str) -> ReceiptUpload:
    """Fetch a library receipt the caller owns, else 404 (never reveal another user's rows)."""
    row = session.get(ReceiptUpload, receipt_id)
    if row is None or row.owner_id != actor.subject_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="receipt not found")
    return row


def create(
    session: Session, actor: Principal, *, filename: str, data: bytes, file_type: str
) -> ReceiptUpload:
    """Store an unassigned receipt: validate, upload the bytes to Blob, persist the row."""
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="empty file")
    if len(data) > MAX_RECEIPT_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file exceeds 25 MB")
    try:
        receipt_extension(filename)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e

    row = ReceiptUpload(
        owner_id=actor.subject_id,
        agency_id=actor.agency_id,
        blob_uri="",
        filename=filename,
        file_type=file_type,
        size=len(data),
    )
    session.add(row)
    session.flush()  # assign row.id for a collision-safe blob name
    row.blob_uri = upload_receipt_blob(actor.subject_id, f"lib-{row.id}-{filename}", data)
    session.add(row)
    audit_service.record(
        session, actor=actor, action="RECEIPT_UPLOADED", entity=f"receipt_upload:{row.id}",
        after={"file_type": file_type, "size": len(data)},
    )
    session.commit()
    session.refresh(row)
    return row


def delete(session: Session, actor: Principal, receipt_id: str) -> None:
    """Remove an unassigned receipt the caller owns (and its blob, best-effort)."""
    row = get_owned_or_404(session, actor, receipt_id)
    delete_receipt_blob(row.blob_uri)
    audit_service.record(
        session, actor=actor, action="RECEIPT_DELETED", entity=f"receipt_upload:{row.id}",
    )
    session.delete(row)
    session.commit()


def attach_to_line_item(
    session: Session,
    actor: Principal,
    *,
    sheet: ExpenseSheet,
    item: LineItem,
    receipt_id: str,
) -> Attachment:
    """Move a library receipt onto a line item. Reuses the canonical attach path so the
    resulting Attachment is indistinguishable from a direct upload, then drops the library
    row. Ownership / draft-editable checks are enforced by `attach_receipt`."""
    row = get_owned_or_404(session, actor, receipt_id)
    data = read_receipt_blob(row.blob_uri)
    att = sheet_service.attach_receipt(
        session, sheet, item, actor,
        filename=row.filename or "receipt",
        data=data,
        file_type=row.file_type,
    )
    # The bytes now live under the new attachment's blob; drop the library copy.
    delete_receipt_blob(row.blob_uri)
    session.delete(row)
    session.commit()
    return att

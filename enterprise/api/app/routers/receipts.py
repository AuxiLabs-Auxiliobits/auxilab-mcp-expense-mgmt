"""Receipt library routes (My Receipts). A per-employee, agency-scoped pool of receipts that
have been uploaded but not yet attached to a line item. Bytes are persisted on upload so the
pool survives refreshes and is the same on every device; attaching one happens via
`POST /sheets/{id}/line-items/{li}/receipt/from-library` (see routers/sheets.py)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlmodel import Session

from app.auth.dependencies import current_principal, require
from app.db import get_session
from app.principal import Principal
from app.rbac.permissions import Capability
from app.schemas.dto import ReceiptUploadOut
from app.services import receipt_library_service
from app.storage import read_receipt_blob

router = APIRouter(
    prefix="/receipts",
    tags=["sheets"],
    responses={401: {"description": "Missing or invalid bearer token"}},
)


def _to_out(row) -> ReceiptUploadOut:
    return ReceiptUploadOut(
        id=row.id,
        filename=row.filename,
        file_type=row.file_type,
        size=row.size,
        scan_status=str(row.scan_status),
        ocr_status=str(row.ocr_status),
        uploaded_at=row.uploaded_at,
        download_url=f"/receipts/{row.id}/file",
    )


@router.get("", response_model=list[ReceiptUploadOut], summary="List my unassigned receipts")
async def list_my_receipts(
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> list[ReceiptUploadOut]:
    return [_to_out(r) for r in receipt_library_service.list_for(session, principal)]


@router.post(
    "",
    response_model=ReceiptUploadOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a receipt to my library (unassigned)",
)
async def upload_to_library(
    file: UploadFile = File(...),
    principal: Principal = Depends(require(Capability.SUBMIT_OWN_SHEET)),
    session: Session = Depends(get_session),
) -> ReceiptUploadOut:
    """Store a receipt without attaching it to a line item yet. Allowed types/size mirror the
    line-item upload (.pdf/.jpeg/.jpg/.heic/.png/.docx/.doc, max 25 MB)."""
    data = await file.read()
    row = receipt_library_service.create(
        session, principal,
        filename=file.filename or "receipt",
        data=data,
        file_type=file.content_type or "application/octet-stream",
    )
    return _to_out(row)


@router.delete(
    "/{receipt_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an unassigned receipt from my library",
    responses={404: {"description": "Receipt not found"}},
)
async def delete_my_receipt(
    receipt_id: str,
    principal: Principal = Depends(require(Capability.SUBMIT_OWN_SHEET)),
    session: Session = Depends(get_session),
) -> None:
    receipt_library_service.delete(session, principal, receipt_id)


@router.get(
    "/{receipt_id}/file",
    summary="Download/preview an unassigned receipt's bytes",
    responses={404: {"description": "Receipt not found"}},
)
async def download_my_receipt(
    receipt_id: str,
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> Response:
    """Stream a library receipt back for inline preview/download (owner-scoped)."""
    row = receipt_library_service.get_owned_or_404(session, principal, receipt_id)
    try:
        data = read_receipt_blob(row.blob_uri)
    except Exception as exc:  # noqa: BLE001
        from fastapi import HTTPException  # noqa: PLC0415

        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"receipt unavailable: {exc}") from exc
    return Response(content=data, media_type=row.file_type or "application/octet-stream")

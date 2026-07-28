"""Receipt attachment routes (SCOPING §4.2, §6). Authorized users — the owning employee,
a manager in the sheet's agency, and Finance/Admin (org-wide) — can read receipt metadata,
preview the file inline, and download it. Scope is enforced against the parent sheet, so a
manager can only see receipts for sheets in their own agency (SCOPING §3.3, §19.1)."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session

from app.auth.dependencies import current_principal
from app.db import get_session
from app.models.attachment import Attachment
from app.models.expense_sheet import ExpenseSheet
from app.models.line_item import LineItem
from app.principal import Principal
from app.rbac import scope as rbac_scope
from app.schemas.dto import AttachmentOut
from app.storage import read_blob

router = APIRouter(
    prefix="/attachments",
    tags=["attachments"],
    responses={
        401: {"description": "Missing or invalid bearer token"},
        403: {"description": "Receipt is outside your scope"},
        404: {"description": "Attachment not found"},
    },
)


def _load_authorized(session: Session, attachment_id: str, principal: Principal) -> Attachment:
    """Fetch an attachment and assert the caller may view its parent sheet."""
    att = session.get(Attachment, attachment_id)
    if att is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="attachment not found")
    item = session.get(LineItem, att.line_item_id)
    sheet = session.get(ExpenseSheet, item.sheet_id) if item else None
    if item is None or sheet is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="attachment has no parent sheet")
    rbac_scope.assert_can_view_sheet(principal, sheet)  # employee=own, manager=agency, finance/admin=all
    return att


@router.get(
    "/{attachment_id}",
    response_model=AttachmentOut,
    summary="Receipt metadata (scope-checked)",
)
async def get_attachment(
    attachment_id: str,
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> Attachment:
    return _load_authorized(session, attachment_id, principal)


@router.get(
    "/{attachment_id}/content",
    summary="Stream the receipt file (preview inline or download), scope-checked",
    responses={200: {"content": {"application/octet-stream": {}}, "description": "Receipt bytes"}},
)
async def get_attachment_content(
    attachment_id: str,
    download: bool = False,
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> Response:
    """Return the raw receipt bytes with the right content-type. `?download=true` forces a
    download (Content-Disposition: attachment); otherwise it's served inline for preview."""
    att = _load_authorized(session, attachment_id, principal)
    try:
        data = read_blob(att.blob_uri)
    except FileNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="receipt file is missing") from e

    name = att.filename or f"receipt-{att.id}"
    disposition = "attachment" if download else "inline"
    # RFC 5987 filename* handles non-ASCII names safely.
    headers = {"Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(name)}"}
    return Response(content=data, media_type=att.file_type or "application/octet-stream", headers=headers)

"""Employee-facing expense-sheet routes (SCOPING §3.1, §5, §6). Create a draft with line
items, view own/permitted sheets, submit and resubmit."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlmodel import Session, select

from app.auth.dependencies import current_principal, require
from app.db import get_session
from app.deps import get_policy
from app.models.attachment import Attachment
from app.models.expense_sheet import ExpenseSheet
from app.principal import Principal
from app.rbac import scope as rbac_scope
from app.rbac.permissions import Capability
from app.schemas.dto import (
    AttachmentOut,
    LineItemCreate,
    LineItemOut,
    LineItemUpdate,
    SheetCreate,
    SheetOut,
    SheetUpdate,
)
from app.serializers import sheet_to_out as _to_out
from app.services import sheet_service
from expense_core.policy import BaselinePolicy

router = APIRouter(
    prefix="/sheets",
    tags=["sheets"],
    responses={
        401: {"description": "Missing or invalid bearer token"},
        403: {"description": "Insufficient role/scope for this sheet"},
    },
)


@router.post(
    "",
    response_model=SheetOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a draft expense sheet",
)
async def create_sheet(
    body: SheetCreate,
    principal: Principal = Depends(require(Capability.SUBMIT_OWN_SHEET)),
    session: Session = Depends(get_session),
) -> SheetOut:
    """Create a DRAFT sheet (the Expense Draft API). Pass `title` + `period`; line items can
    be added inline or incrementally via `POST /sheets/{id}/line-items`. A receipt must be
    attached to every line item before submission."""
    sheet = sheet_service.create_draft(session, principal, body)
    return _to_out(session, sheet)


@router.get("", response_model=list[SheetOut], summary="List my own sheets")
async def list_my_sheets(
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> list[SheetOut]:
    rows = session.exec(
        select(ExpenseSheet).where(ExpenseSheet.employee_id == principal.subject_id)
    ).all()
    return [_to_out(session, s) for s in rows]


@router.get(
    "/{sheet_id}",
    response_model=SheetOut,
    summary="Get one sheet (scope-checked)",
    responses={404: {"description": "Sheet not found"}},
)
async def get_sheet(
    sheet_id: str,
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> SheetOut:
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    rbac_scope.assert_can_view_sheet(principal, sheet)
    return _to_out(session, sheet)


@router.post(
    "/{sheet_id}/submit",
    response_model=SheetOut,
    summary="Submit or resubmit a sheet",
    responses={404: {"description": "Sheet not found"}},
)
async def submit_sheet(
    sheet_id: str,
    principal: Principal = Depends(require(Capability.SUBMIT_OWN_SHEET)),
    session: Session = Depends(get_session),
    policy: BaselinePolicy = Depends(get_policy),
) -> SheetOut:
    """Submit or resubmit. Resubmission keeps the same ID and bumps version (SCOPING §5.1)."""
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    sheet_service._assert_owner(principal, sheet)
    sheet = sheet_service.submit_sheet(session, sheet, principal, policy)
    return _to_out(session, sheet)


# --------------------------------------------------------------------------- #
# Draft editing — owner only, while DRAFT (change req: editable until submission)
# --------------------------------------------------------------------------- #
@router.patch("/{sheet_id}", response_model=SheetOut, summary="Edit a draft sheet (title/period)")
async def update_sheet(
    sheet_id: str,
    body: SheetUpdate,
    principal: Principal = Depends(require(Capability.SUBMIT_OWN_SHEET)),
    session: Session = Depends(get_session),
) -> SheetOut:
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    sheet = sheet_service.update_sheet(session, sheet, principal, body)
    return _to_out(session, sheet)


@router.delete("/{sheet_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Withdraw a draft sheet")
async def withdraw_sheet(
    sheet_id: str,
    principal: Principal = Depends(require(Capability.SUBMIT_OWN_SHEET)),
    session: Session = Depends(get_session),
) -> None:
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    sheet_service.delete_draft(session, sheet, principal)


@router.post(
    "/{sheet_id}/line-items",
    response_model=SheetOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a line item to a draft",
)
async def add_line_item(
    sheet_id: str,
    body: LineItemCreate,
    principal: Principal = Depends(require(Capability.SUBMIT_OWN_SHEET)),
    session: Session = Depends(get_session),
) -> SheetOut:
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    sheet_service.add_line_item(session, sheet, principal, body)
    return _to_out(session, sheet)


@router.patch(
    "/{sheet_id}/line-items/{line_item_id}",
    response_model=LineItemOut,
    summary="Edit a draft line item",
)
async def update_line_item(
    sheet_id: str,
    line_item_id: str,
    body: LineItemUpdate,
    principal: Principal = Depends(require(Capability.SUBMIT_OWN_SHEET)),
    session: Session = Depends(get_session),
) -> LineItemOut:
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    item = sheet_service.get_line_item_or_404(session, sheet, line_item_id)
    item = sheet_service.update_line_item(session, sheet, item, principal, body)
    out = LineItemOut.model_validate(item)
    out.receipt_count = sheet_service._attachment_count(session, item.id)
    return out


@router.delete(
    "/{sheet_id}/line-items/{line_item_id}",
    response_model=SheetOut,
    summary="Remove a draft line item",
)
async def delete_line_item(
    sheet_id: str,
    line_item_id: str,
    principal: Principal = Depends(require(Capability.SUBMIT_OWN_SHEET)),
    session: Session = Depends(get_session),
) -> SheetOut:
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    item = sheet_service.get_line_item_or_404(session, sheet, line_item_id)
    sheet_service.delete_line_item(session, sheet, item, principal)
    return _to_out(session, sheet)


@router.get(
    "/{sheet_id}/line-items/{line_item_id}/receipts",
    response_model=list[AttachmentOut],
    summary="List receipts attached to a line item",
)
async def list_receipts(
    sheet_id: str,
    line_item_id: str,
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> list[AttachmentOut]:
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    rbac_scope.assert_can_view_sheet(principal, sheet)
    item = sheet_service.get_line_item_or_404(session, sheet, line_item_id)
    rows = session.exec(
        select(Attachment).where(Attachment.line_item_id == item.id)
    ).all()
    return [AttachmentOut.model_validate(a) for a in rows]


@router.post(
    "/{sheet_id}/line-items/{line_item_id}/receipt",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload + attach a receipt to a line item (mandatory)",
)
async def upload_receipt(
    sheet_id: str,
    line_item_id: str,
    file: UploadFile = File(...),
    principal: Principal = Depends(require(Capability.SUBMIT_OWN_SHEET)),
    session: Session = Depends(get_session),
) -> AttachmentOut:
    """Store the receipt under `receipts/{employee_id}/` and attach it to the line item.
    Allowed: .pdf/.jpeg/.jpg/.heic/.png/.docx/.doc, max 25 MB (SCOPING §4.2)."""
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    item = sheet_service.get_line_item_or_404(session, sheet, line_item_id)
    data = await file.read()
    att = sheet_service.attach_receipt(
        session, sheet, item, principal,
        filename=file.filename or "receipt",
        data=data,
        file_type=file.content_type or "application/octet-stream",
    )
    return AttachmentOut.model_validate(att)

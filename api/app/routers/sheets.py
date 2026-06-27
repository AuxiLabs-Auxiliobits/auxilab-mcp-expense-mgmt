"""Employee-facing expense-sheet routes (SCOPING §3.1, §5, §6). Create a draft with line
items, view own/permitted sheets, submit and resubmit."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlmodel import Session, select

from app.auth.dependencies import current_principal, require
from app.db import get_session
from app.deps import get_policy
from app.models.attachment import Attachment
from app.models.decision import Decision
from app.models.expense_sheet import ExpenseSheet
from app.models.line_item import LineItem
from app.principal import Principal
from app.rbac import scope as rbac_scope
from app.rbac.permissions import Capability
from app.config import settings
from app.schemas.dto import (
    AttachmentOut,
    DecisionOut,
    LineItemCreate,
    LineItemOut,
    LineItemUpdate,
    ReceiptAttachFromLibrary,
    ReceiptScanOut,
    SheetCreate,
    SheetOut,
    SheetUpdate,
)
from app.serializers import decision_to_out
from app.serializers import sheet_to_out as _to_out
from app.services import receipt_library_service, receipt_scan_service, sheet_service
from app.storage import read_receipt_blob
from app.services.state_machine import RESUBMITTABLE
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
    policy: BaselinePolicy = Depends(get_policy),
) -> SheetOut:
    """Create a DRAFT sheet (the Expense Draft API). Pass `title` + `period`; line items can
    be added inline or incrementally via `POST /sheets/{id}/line-items`. A receipt must be
    attached to every line item before submission."""
    sheet = sheet_service.create_draft(session, principal, body)
    return _to_out(session, sheet, policy=policy)


@router.get("", response_model=list[SheetOut], summary="List my own sheets")
async def list_my_sheets(
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> list[SheetOut]:
    # Policy flags are intentionally NOT computed here: running the checker per line item for
    # every sheet would make the list O(sheets × items). They are computed lazily on the
    # detail route (GET /sheets/{id}); in the list `policy_flags` stays at its zero default.
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
    policy: BaselinePolicy = Depends(get_policy),
) -> SheetOut:
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    rbac_scope.assert_can_view_sheet(principal, sheet)
    return _to_out(session, sheet, policy=policy)


@router.get(
    "/{sheet_id}/decisions",
    response_model=list[DecisionOut],
    summary="Decision trail for a sheet (manager/finance/LLM actions)",
    responses={404: {"description": "Sheet not found"}},
)
async def sheet_decisions(
    sheet_id: str,
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> list[DecisionOut]:
    """The append-only decision trail for the sheet, oldest first — powers the Decision Trail
    panel. Scope-checked like the sheet itself."""
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    rbac_scope.assert_can_view_sheet(principal, sheet)
    rows = session.exec(
        select(Decision).where(Decision.sheet_id == sheet.id).order_by(Decision.timestamp)
    ).all()
    return [decision_to_out(d) for d in rows]


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
    return _to_out(session, sheet, policy=policy)


@router.post(
    "/{sheet_id}/resubmit",
    response_model=SheetOut,
    summary="Resubmit a returned/rejected sheet",
    responses={
        404: {"description": "Sheet not found"},
        409: {"description": "Sheet is not in a resubmittable state"},
    },
)
async def resubmit_sheet(
    sheet_id: str,
    principal: Principal = Depends(require(Capability.SUBMIT_OWN_SHEET)),
    session: Session = Depends(get_session),
    policy: BaselinePolicy = Depends(get_policy),
) -> SheetOut:
    """Resubmit a sheet that was returned to the employee or rejected. Keeps the same ID,
    bumps the version, and resets all prior manager/finance verdicts before re-running intake
    (SCOPING §5.1). Use POST /sheets/{id}/submit for a first-time DRAFT submission."""
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    sheet_service._assert_owner(principal, sheet)
    if sheet.status not in RESUBMITTABLE:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"sheet in status {sheet.status} cannot be resubmitted "
            "(only returned or rejected sheets); use /submit for a draft",
        )
    sheet = sheet_service.submit_sheet(session, sheet, principal, policy)
    return _to_out(session, sheet, policy=policy)


# --------------------------------------------------------------------------- #
# Draft editing — owner only, while DRAFT (change req: editable until submission)
# --------------------------------------------------------------------------- #
@router.patch("/{sheet_id}", response_model=SheetOut, summary="Edit a draft sheet (title/period)")
async def update_sheet(
    sheet_id: str,
    body: SheetUpdate,
    principal: Principal = Depends(require(Capability.SUBMIT_OWN_SHEET)),
    session: Session = Depends(get_session),
    policy: BaselinePolicy = Depends(get_policy),
) -> SheetOut:
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    sheet = sheet_service.update_sheet(session, sheet, principal, body)
    return _to_out(session, sheet, policy=policy)


@router.delete(
    "/{sheet_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Discard a draft sheet (hard delete)",
)
async def discard_draft(
    sheet_id: str,
    principal: Principal = Depends(require(Capability.SUBMIT_OWN_SHEET)),
    session: Session = Depends(get_session),
) -> None:
    """Permanently discard a DRAFT sheet and its line items. Owner-only, DRAFT-only. For a
    soft withdraw that preserves the audit trail, use POST /sheets/{id}/withdraw instead."""
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    sheet_service.delete_draft(session, sheet, principal)


@router.post(
    "/{sheet_id}/withdraw",
    response_model=SheetOut,
    summary="Withdraw a submitted sheet back to DRAFT (recall)",
    responses={
        404: {"description": "Sheet not found"},
        409: {"description": "Sheet is not in a withdrawable state"},
    },
)
async def withdraw_sheet(
    sheet_id: str,
    principal: Principal = Depends(require(Capability.SUBMIT_OWN_SHEET)),
    session: Session = Depends(get_session),
    policy: BaselinePolicy = Depends(get_policy),
) -> SheetOut:
    """Recall an in-flight sheet (submitted / in review) back to the employee as a DRAFT —
    clears verdicts and removes it from the manager/finance queues."""
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    sheet = sheet_service.recall_sheet(session, sheet, principal)
    return _to_out(session, sheet, policy=policy)


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
    policy: BaselinePolicy = Depends(get_policy),
) -> SheetOut:
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    sheet_service.add_line_item(session, sheet, principal, body)
    return _to_out(session, sheet, policy=policy)


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
    policy: BaselinePolicy = Depends(get_policy),
) -> SheetOut:
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    item = sheet_service.get_line_item_or_404(session, sheet, line_item_id)
    sheet_service.delete_line_item(session, sheet, item, principal)
    return _to_out(session, sheet, policy=policy)


@router.get(
    "/{sheet_id}/receipts",
    response_model=list[AttachmentOut],
    summary="All receipts on a sheet (scope-checked) — for manager/finance review",
    responses={404: {"description": "Sheet not found"}},
)
async def list_sheet_receipts(
    sheet_id: str,
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> list[AttachmentOut]:
    """Every receipt across the sheet's line items, so a reviewer (manager in-agency, or
    Finance/Admin org-wide) can see all supporting documents in one call."""
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    rbac_scope.assert_can_view_sheet(principal, sheet)
    item_ids = list(
        session.exec(select(LineItem.id).where(LineItem.sheet_id == sheet.id)).all()
    )
    if not item_ids:
        return []
    rows = session.exec(
        select(Attachment).where(Attachment.line_item_id.in_(item_ids))  # type: ignore[attr-defined]
    ).all()
    return [AttachmentOut.model_validate(a) for a in rows]


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


@router.post(
    "/{sheet_id}/line-items/{line_item_id}/receipt/from-library",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Attach a receipt already in My Receipts to a line item",
    responses={404: {"description": "Sheet, line item, or receipt not found"}},
)
async def attach_receipt_from_library(
    sheet_id: str,
    line_item_id: str,
    body: ReceiptAttachFromLibrary,
    principal: Principal = Depends(require(Capability.SUBMIT_OWN_SHEET)),
    session: Session = Depends(get_session),
) -> AttachmentOut:
    """Attach a receipt the employee previously uploaded to their library (My Receipts) to a
    line item. The bytes move into a normal attachment and the library entry is removed."""
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    item = sheet_service.get_line_item_or_404(session, sheet, line_item_id)
    att = receipt_library_service.attach_to_line_item(
        session, principal, sheet=sheet, item=item, receipt_id=body.receipt_id,
    )
    return AttachmentOut.model_validate(att)


@router.post(
    "/{sheet_id}/line-items/{line_item_id}/scan",
    response_model=ReceiptScanOut,
    summary="Scan the line item's receipt (Document Intelligence) and reconcile",
    responses={404: {"description": "Sheet, line item, or receipt not found"}},
)
async def scan_receipt(
    sheet_id: str,
    line_item_id: str,
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> ReceiptScanOut:
    """OCR + extract the most-recent receipt on a line item and reconcile against the entered
    amount. Live with Azure Document Intelligence; offline it parses text receipts and returns
    `source="unavailable"` for binary files with no OCR configured."""
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    rbac_scope.assert_can_view_sheet(principal, sheet)
    item = sheet_service.get_line_item_or_404(session, sheet, line_item_id)
    attachments = session.exec(
        select(Attachment).where(Attachment.line_item_id == item.id)
    ).all()
    if not attachments:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no receipt attached to scan")
    result = receipt_scan_service.scan_receipt(attachments[-1].blob_uri, item.amount, settings)
    # Persist the review flag for Finance (employee UI shows nothing).
    item.needs_human_review = result.human_intervention_required
    item.review_reason = result.detail if result.human_intervention_required else None
    session.add(item)
    session.commit()
    return result


@router.get(
    "/{sheet_id}/line-items/{line_item_id}/receipts/{attachment_id}/file",
    summary="Download/preview a receipt's bytes (scope-checked)",
    responses={404: {"description": "Sheet, line item, or attachment not found"}},
)
async def download_receipt(
    sheet_id: str,
    line_item_id: str,
    attachment_id: str,
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> Response:
    """Stream a receipt back for inline preview/download. The browser can't send the bearer
    token on a plain navigation, so the client fetches this with auth and renders a blob."""
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    rbac_scope.assert_can_view_sheet(principal, sheet)
    item = sheet_service.get_line_item_or_404(session, sheet, line_item_id)
    att = session.get(Attachment, attachment_id)
    if att is None or att.line_item_id != item.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="attachment not found")
    try:
        data = read_receipt_blob(att.blob_uri)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"receipt unavailable: {exc}") from exc
    return Response(content=data, media_type=att.file_type or "application/octet-stream")

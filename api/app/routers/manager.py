"""Manager routes (SCOPING §3.1, §6.2). Per-line-item approve/reject/request-info,
restricted to the manager's own agency. SoD: cannot action own line items."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth.dependencies import require
from app.db import get_session
from app.models.expense_sheet import ExpenseSheet
from app.models.line_item import LineItem
from app.principal import Principal
from app.rbac.permissions import Capability
from app.schemas.dto import ManagerActionRequest, SheetOut
from app.pagination import PageParams
from app.serializers import sheet_to_out, sheets_to_out
from app.services import sheet_service
from expense_core.schemas.enums import LineItemStatus, SheetStatus

router = APIRouter(
    prefix="/manager",
    tags=["manager"],
    responses={
        401: {"description": "Missing or invalid bearer token"},
        403: {"description": "Not a manager, or sheet outside your agency"},
    },
)

_ALLOWED_ACTIONS = {
    LineItemStatus.MANAGER_APPROVED,
    LineItemStatus.MANAGER_REJECTED,
    LineItemStatus.INFO_REQUESTED,
}


@router.get("/queue", response_model=list[SheetOut], summary="My agency's manager-review queue")
async def manager_queue(
    page: PageParams = Depends(),
    principal: Principal = Depends(require(Capability.MANAGER_ACTION_LINE_ITEM)),
    session: Session = Depends(get_session),
) -> list[SheetOut]:
    """Sheets awaiting manager review in the manager's own agency only (SCOPING §19.1).
    Paginated + bounded."""
    rows = session.exec(
        select(ExpenseSheet)
        .where(
            ExpenseSheet.agency_id == principal.agency_id,
            ExpenseSheet.status == SheetStatus.IN_MANAGER_REVIEW,
        )
        .order_by(ExpenseSheet.updated_at.desc())  # type: ignore[attr-defined]
        .limit(page.limit)
        .offset(page.offset)
    ).all()
    return sheets_to_out(session, list(rows))


@router.post(
    "/sheets/{sheet_id}/action",
    response_model=SheetOut,
    summary="Approve / reject / request-info on a line item",
    responses={
        400: {"description": "Invalid manager action"},
        404: {"description": "Sheet or line item not found"},
    },
)
async def action_line_item(
    sheet_id: str,
    body: ManagerActionRequest,
    principal: Principal = Depends(require(Capability.MANAGER_ACTION_LINE_ITEM)),
    session: Session = Depends(get_session),
) -> SheetOut:
    if body.action not in _ALLOWED_ACTIONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid manager action")

    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    item = session.get(LineItem, body.line_item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="line item not found")

    sheet = sheet_service.manager_action(session, sheet, item, principal, body.action, body.reason)
    return sheet_to_out(session, sheet)


@router.post(
    "/sheets/{sheet_id}/approve",
    response_model=SheetOut,
    summary="Approve the whole sheet (all not-yet-rejected line items) and advance to finance",
    responses={
        400: {"description": "Sheet has no line items"},
        404: {"description": "Sheet not found"},
        409: {"description": "Sheet not in manager review"},
    },
)
async def approve_sheet(
    sheet_id: str,
    principal: Principal = Depends(require(Capability.MANAGER_ACTION_LINE_ITEM)),
    session: Session = Depends(get_session),
) -> SheetOut:
    """One-click approve: marks every not-yet-rejected line item MANAGER_APPROVED and advances
    the sheet to finance review. Agency scope + SoD enforced (SCOPING §6.2, §8)."""
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    sheet = sheet_service.manager_approve_sheet(session, sheet, principal)
    return sheet_to_out(session, sheet)

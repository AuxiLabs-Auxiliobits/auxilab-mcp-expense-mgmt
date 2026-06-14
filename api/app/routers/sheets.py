"""Employee-facing expense-sheet routes (SCOPING §3.1, §5, §6). Create a draft with line
items, view own/permitted sheets, submit and resubmit."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth.dependencies import current_principal, require
from app.db import get_session
from app.deps import get_policy
from app.models.expense_sheet import ExpenseSheet
from app.models.line_item import LineItem
from app.principal import Principal
from app.rbac import scope as rbac_scope
from app.rbac.permissions import Capability
from app.schemas.dto import SheetCreate, SheetOut
from app.serializers import sheet_to_out as _to_out
from app.services import sheet_service
from expense_core.policy import BaselinePolicy

router = APIRouter(prefix="/sheets", tags=["sheets"])


@router.post("", response_model=SheetOut, status_code=status.HTTP_201_CREATED)
async def create_sheet(
    body: SheetCreate,
    principal: Principal = Depends(require(Capability.SUBMIT_OWN_SHEET)),
    session: Session = Depends(get_session),
) -> SheetOut:
    if principal.agency_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="user has no agency assigned")

    sheet = ExpenseSheet(employee_id=principal.subject_id, agency_id=principal.agency_id,
                         period=body.period)
    session.add(sheet)
    session.flush()  # assign sheet.id
    for li in body.line_items:
        session.add(
            LineItem(
                sheet_id=sheet.id, employee_id=principal.subject_id,
                category=li.category, amount=li.amount, currency=li.currency,
                merchant=li.merchant, description=li.description, expense_date=li.expense_date,
                receipt_datetime=li.receipt_datetime, receipt_total=li.receipt_total,
                has_receipt=li.has_receipt,
            )
        )
    session.commit()
    session.refresh(sheet)
    return _to_out(session, sheet)


@router.get("", response_model=list[SheetOut])
async def list_my_sheets(
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> list[SheetOut]:
    rows = session.exec(
        select(ExpenseSheet).where(ExpenseSheet.employee_id == principal.subject_id)
    ).all()
    return [_to_out(session, s) for s in rows]


@router.get("/{sheet_id}", response_model=SheetOut)
async def get_sheet(
    sheet_id: str,
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> SheetOut:
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    rbac_scope.assert_can_view_sheet(principal, sheet)
    return _to_out(session, sheet)


@router.post("/{sheet_id}/submit", response_model=SheetOut)
async def submit_sheet(
    sheet_id: str,
    principal: Principal = Depends(require(Capability.SUBMIT_OWN_SHEET)),
    session: Session = Depends(get_session),
    policy: BaselinePolicy = Depends(get_policy),
) -> SheetOut:
    """Submit or resubmit. Resubmission keeps the same ID and bumps version (SCOPING §5.1)."""
    sheet = sheet_service.get_sheet_or_404(session, sheet_id)
    if sheet.employee_id != principal.subject_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="not your sheet")
    sheet = sheet_service.submit_sheet(session, sheet, principal, policy)
    return _to_out(session, sheet)

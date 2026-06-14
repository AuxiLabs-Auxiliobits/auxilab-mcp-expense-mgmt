"""Model → DTO serialization shared across routers."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.expense_sheet import ExpenseSheet
from app.models.line_item import LineItem
from app.schemas.dto import LineItemOut, SheetOut


def sheet_to_out(session: Session, sheet: ExpenseSheet) -> SheetOut:
    items = session.exec(select(LineItem).where(LineItem.sheet_id == sheet.id)).all()
    out = SheetOut.model_validate(sheet)
    out.line_items = [LineItemOut.model_validate(i) for i in items]
    return out

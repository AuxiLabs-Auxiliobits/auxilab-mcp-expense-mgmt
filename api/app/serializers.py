"""Model → DTO serialization shared across routers."""

from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.attachment import Attachment
from app.models.expense_sheet import ExpenseSheet
from app.models.line_item import LineItem
from app.schemas.dto import LineItemOut, SheetOut


def sheet_to_out(session: Session, sheet: ExpenseSheet) -> SheetOut:
    items = list(session.exec(select(LineItem).where(LineItem.sheet_id == sheet.id)).all())
    # One grouped query for attachment counts rather than N per-item queries.
    counts = dict(
        session.exec(
            select(Attachment.line_item_id, func.count(Attachment.id))
            .where(Attachment.line_item_id.in_([i.id for i in items] or [""]))  # type: ignore[attr-defined]
            .group_by(Attachment.line_item_id)
        ).all()
    )
    out = SheetOut.model_validate(sheet)
    line_outs: list[LineItemOut] = []
    for i in items:
        li = LineItemOut.model_validate(i)
        li.receipt_count = counts.get(i.id, 0)
        line_outs.append(li)
    out.line_items = line_outs
    return out

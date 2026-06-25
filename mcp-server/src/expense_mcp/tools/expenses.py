"""Expense-sheet tools (employee workflow). Thin wrappers over the /sheets API — all
ownership/state-machine/validation rules are enforced server-side."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from pydantic import Field

from expense_mcp import client
from expense_mcp.annotations import DESTRUCTIVE, READ, WRITE
from expense_mcp.instance import mcp


@mcp.tool(annotations=READ)
def list_my_expenses() -> list[dict[str, Any]]:
    """List the current user's own expense sheets (id, title, status, period, total)."""
    return client.get("/sheets")


@mcp.tool(annotations=READ)
def get_expense(sheet_id: str) -> dict[str, Any]:
    """Get one expense sheet with its line items, totals, status, and submit/blocker info."""
    return client.get(f"/sheets/{sheet_id}")


@mcp.tool(annotations=WRITE)
def create_expense(title: str, period: Annotated[str, Field(description="Month 'YYYY-MM'")]) -> dict[str, Any]:
    """Create a DRAFT expense sheet. Add line items + receipts, then submit."""
    return client.post("/sheets", json={"title": title, "period": period})


@mcp.tool(annotations=WRITE)
def add_line_item(
    sheet_id: str,
    amount: Annotated[Decimal, Field(gt=0)],
    merchant: str,
    expense_date: Annotated[str, Field(description="'YYYY-MM-DD'")],
    category: str,
    currency: str = "USD",
    description: str = "",
    receipt_total: Decimal | None = None,
    receipt_datetime: str | None = None,
) -> dict[str, Any]:
    """Add a line item to a DRAFT sheet. `category` must be a valid expense category."""
    body = {
        "amount": str(amount), "merchant": merchant, "expense_date": expense_date,
        "category": category, "currency": currency, "description": description,
    }
    if receipt_total is not None:
        body["receipt_total"] = str(receipt_total)
    if receipt_datetime:
        body["receipt_datetime"] = receipt_datetime
    return client.post(f"/sheets/{sheet_id}/line-items", json=body)


@mcp.tool(annotations=WRITE)
def update_expense(sheet_id: str, title: str | None = None, period: str | None = None) -> dict[str, Any]:
    """Edit a DRAFT sheet's title and/or period."""
    body = {k: v for k, v in {"title": title, "period": period}.items() if v is not None}
    return client.patch(f"/sheets/{sheet_id}", json=body)


@mcp.tool(annotations=WRITE)
def submit_expense(sheet_id: str) -> dict[str, Any]:
    """Submit a DRAFT sheet for manager review (runs the intake gate first)."""
    return client.post(f"/sheets/{sheet_id}/submit")


@mcp.tool(annotations=WRITE)
def resubmit_expense(sheet_id: str) -> dict[str, Any]:
    """Resubmit a returned/rejected sheet (bumps version, restarts review)."""
    return client.post(f"/sheets/{sheet_id}/resubmit")


@mcp.tool(annotations=DESTRUCTIVE)
def withdraw_expense(sheet_id: str) -> dict[str, Any]:
    """Withdraw a DRAFT sheet (soft — keeps the record, moves it to WITHDRAWN)."""
    return client.post(f"/sheets/{sheet_id}/withdraw")


@mcp.tool(annotations=READ)
def search_expenses(
    scope: Annotated[str, Field(description="'mine' or 'all' (all = finance/admin only)")] = "mine",
    status: str | None = None,
    category: str | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Search expense sheets with filters + pagination + totals. `scope='all'` searches every
    sheet (requires finance/admin or manager agency scope); `scope='mine'` is the caller's own."""
    rows = client.get("/finance/sheets" if scope == "all" else "/sheets")
    def _amt(s: dict[str, Any]) -> float:
        try:
            return float(s.get("total") or 0)
        except (TypeError, ValueError):
            return 0.0
    filtered = []
    for s in rows:
        if status and s.get("status") != status:
            continue
        if category and not any(li.get("category") == category for li in s.get("line_items", [])):
            continue
        a = _amt(s)
        if min_amount is not None and a < min_amount:
            continue
        if max_amount is not None and a > max_amount:
            continue
        filtered.append(s)
    total_amount = sum(_amt(s) for s in filtered)
    page = filtered[offset : offset + limit]
    return {
        "count": len(filtered),
        "returned": len(page),
        "offset": offset,
        "limit": limit,
        "total_amount": round(total_amount, 2),
        "results": page,
    }


# --- draft cleanup + decision history + line-item edits ----------------------------------- #
@mcp.tool(annotations=READ)
def get_decisions(sheet_id: str) -> list[dict[str, Any]]:
    """The decision/approval history for a sheet (who did what, when, with reasons)."""
    return client.get(f"/sheets/{sheet_id}/decisions")


@mcp.tool(annotations=DESTRUCTIVE)
def discard_draft(sheet_id: str) -> dict[str, Any] | None:
    """Permanently delete a DRAFT sheet. Only drafts can be discarded."""
    return client.delete(f"/sheets/{sheet_id}")


@mcp.tool(annotations=WRITE)
def update_line_item(
    sheet_id: str,
    line_item_id: str,
    amount: Decimal | None = None,
    merchant: str | None = None,
    description: str | None = None,
    category: str | None = None,
    expense_date: str | None = None,
    currency: str | None = None,
    receipt_total: Decimal | None = None,
    receipt_datetime: str | None = None,
    tax: Decimal | None = None,
) -> dict[str, Any]:
    """Edit a line item on a DRAFT sheet. Only the provided fields change."""
    body = {k: v for k, v in {
        "amount": amount, "merchant": merchant, "description": description, "category": category,
        "expense_date": expense_date, "currency": currency, "receipt_total": receipt_total,
        "receipt_datetime": receipt_datetime, "tax": tax,
    }.items() if v is not None}
    return client.patch(f"/sheets/{sheet_id}/line-items/{line_item_id}", json=body)


@mcp.tool(annotations=DESTRUCTIVE)
def remove_line_item(sheet_id: str, line_item_id: str) -> dict[str, Any]:
    """Remove a line item from a DRAFT sheet."""
    return client.delete(f"/sheets/{sheet_id}/line-items/{line_item_id}")

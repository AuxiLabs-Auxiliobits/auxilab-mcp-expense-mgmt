"""Expense-sheet tools (employee workflow). Thin wrappers over the /sheets API — all
ownership/state-machine/validation rules are enforced server-side."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from pydantic import Field

from expense_mcp import client
from expense_mcp.instance import mcp


@mcp.tool()
def list_my_expenses() -> list[dict[str, Any]]:
    """List the current user's own expense sheets (id, title, status, period, total)."""
    return client.get("/sheets")


@mcp.tool()
def get_expense(sheet_id: str) -> dict[str, Any]:
    """Get one expense sheet with its line items, totals, status, and submit/blocker info."""
    return client.get(f"/sheets/{sheet_id}")


@mcp.tool()
def create_expense(title: str, period: Annotated[str, Field(description="Month 'YYYY-MM'")]) -> dict[str, Any]:
    """Create a DRAFT expense sheet. Add line items + receipts, then submit."""
    return client.post("/sheets", json={"title": title, "period": period})


@mcp.tool()
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


@mcp.tool()
def update_expense(sheet_id: str, title: str | None = None, period: str | None = None) -> dict[str, Any]:
    """Edit a DRAFT sheet's title and/or period."""
    body = {k: v for k, v in {"title": title, "period": period}.items() if v is not None}
    return client.patch(f"/sheets/{sheet_id}", json=body)


@mcp.tool()
def submit_expense(sheet_id: str) -> dict[str, Any]:
    """Submit a DRAFT sheet for manager review (runs the intake gate first)."""
    return client.post(f"/sheets/{sheet_id}/submit")


@mcp.tool()
def resubmit_expense(sheet_id: str) -> dict[str, Any]:
    """Resubmit a returned/rejected sheet (bumps version, restarts review)."""
    return client.post(f"/sheets/{sheet_id}/resubmit")


@mcp.tool()
def withdraw_expense(sheet_id: str) -> dict[str, Any]:
    """Withdraw a DRAFT sheet (soft — keeps the record, moves it to WITHDRAWN)."""
    return client.post(f"/sheets/{sheet_id}/withdraw")


@mcp.tool()
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

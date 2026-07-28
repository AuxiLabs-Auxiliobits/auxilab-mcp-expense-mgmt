"""Dashboard / analytics tools. Results are role-scoped by the API (manager → own agency;
finance/admin → all, optionally filtered)."""

from __future__ import annotations

from typing import Any

from expense_mcp import client
from expense_mcp.annotations import READ
from expense_mcp.instance import mcp


@mcp.tool(annotations=READ)
def get_dashboard_metrics(period: str | None = None, agency_id: str | None = None) -> dict[str, Any]:
    """Dashboard summary: KPIs, spend-by-category, compliance, status breakdown. `period`
    ('YYYY-MM') and `agency_id` are optional filters."""
    params = {k: v for k, v in {"period": period, "agency_id": agency_id}.items() if v}
    return client.get("/reports/summary", params=params or None)


@mcp.tool(annotations=READ)
def get_spend_by_category() -> list[dict[str, Any]]:
    """Total spend per expense category within the caller's scope, highest first."""
    return client.get("/reports/spend-by-category")


@mcp.tool(annotations=READ)
def get_finance_kpis() -> dict[str, Any]:
    """Finance KPIs: auto-approval rate, manual interventions, policy citations, compliance."""
    return client.get("/finance/kpis")

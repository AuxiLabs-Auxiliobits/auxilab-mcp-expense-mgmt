"""AI insights tools — read the platform's advisory AI layer (recommendations, the AI Workspace,
analytics) and record feedback. Advisory only: these never change a sheet's state. RBAC-scoped by
the API (employee → own, manager → agency, finance/admin → all)."""

from __future__ import annotations

from typing import Any

from expense_mcp import client
from expense_mcp.annotations import COMPUTE, READ, WRITE
from expense_mcp.instance import mcp


@mcp.tool(annotations=COMPUTE)
def get_ai_recommendation(sheet_id: str, refresh: bool = False) -> dict[str, Any]:
    """Advisory AI recommendation for a sheet: summary, risk score/band, policy compliance,
    missing info, duplicate likelihood, suggested action, confidence, and the rationale
    (why / data analyzed / policies considered). `refresh=true` recomputes it."""
    return client.get(f"/ai/sheets/{sheet_id}/recommendation", params={"refresh": refresh})


@mcp.tool(annotations=READ)
def get_ai_workspace() -> dict[str, Any]:
    """The AI Workspace for the caller: counts + recommendations needing attention, high-risk
    sheets, duplicate candidates, policy violations, missing receipts, and recent AI actions."""
    return client.get("/ai/workspace")


@mcp.tool(annotations=READ)
def get_ai_analytics() -> dict[str, Any]:
    """AI analytics: recommendations generated, risk-band split, acceptance/helpful rates,
    policy violations + duplicates detected, average approval time, engagement."""
    return client.get("/ai/analytics")


@mcp.tool(annotations=WRITE)
def submit_ai_feedback(
    recommendation_id: str,
    helpful: bool | None = None,
    decision: str | None = None,  # accepted | ignored | dismissed
    reason: str | None = None,
) -> dict[str, Any]:
    """Record feedback on an AI recommendation (helpful + accepted/ignored/dismissed + reason)."""
    body = {k: v for k, v in {"helpful": helpful, "decision": decision, "reason": reason}.items() if v is not None}
    return client.post(f"/ai/recommendations/{recommendation_id}/feedback", json=body)

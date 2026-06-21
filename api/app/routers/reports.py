"""Reporting routes (SCOPING §3.2, §4). Dashboard KPI + spend-by-category + compliance.
Manager → own agency; Finance/Admin → all (optionally filtered by `agency_id`)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.auth.dependencies import require
from app.db import get_session
from app.principal import Principal
from app.rbac.permissions import Capability
from app.schemas.dto import ReportSummaryOut
from app.services import reports_service

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    responses={
        401: {"description": "Missing or invalid bearer token"},
        403: {"description": "Reports require Manager/Finance/Admin"},
    },
)


@router.get("/summary", response_model=ReportSummaryOut, summary="Dashboard summary (KPIs + spend + compliance)")
async def summary(
    period: str | None = None,
    agency_id: str | None = None,
    principal: Principal = Depends(require(Capability.VIEW_REPORTS)),
    session: Session = Depends(get_session),
) -> ReportSummaryOut:
    """Aggregated totals for the dashboard. `period` ('YYYY-MM') and `agency_id` are optional
    filters; managers are always scoped to their own agency regardless of `agency_id`."""
    return reports_service.build_summary(session, principal, period=period, agency_id=agency_id)

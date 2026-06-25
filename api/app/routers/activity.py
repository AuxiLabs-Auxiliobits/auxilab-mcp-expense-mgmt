"""Activity / audit-trail routes (SCOPING §3.3, §6.5). Every role can see the activity it's
entitled to — scoped, paginated and filterable — so the portal's "Activity" screens are real
for everyone (employee → own, manager → agency, finance/admin → org-wide)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.auth.dependencies import current_principal
from app.db import get_session
from app.principal import Principal
from app.schemas.dto import ActivityPageOut
from app.services import activity_service

router = APIRouter(
    prefix="/activity",
    tags=["activity"],
    responses={401: {"description": "Missing or invalid bearer token"}},
)


@router.get("", response_model=ActivityPageOut, summary="Audit activity (role-scoped, paginated, filtered)")
async def list_activity(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    action: str | None = None,
    actor_id: str | None = None,
    q: str | None = Query(None, description="Search in action / entity"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> ActivityPageOut:
    """The audit trail the caller may see. Employees see their own actions; managers see their
    agency's; finance/admin see everything. Supports `action`/`actor_id`/`q`/date filters."""
    return activity_service.list_activity(
        session,
        principal,
        page=page,
        page_size=page_size,
        action=action,
        actor_id=actor_id,
        q=q,
        date_from=date_from,
        date_to=date_to,
    )

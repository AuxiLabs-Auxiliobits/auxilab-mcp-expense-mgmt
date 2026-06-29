"""Self-service audit routes (SCOPING §6.5). Any authenticated user may read the trail of
their *own* actions. The org-wide / agency log stays Finance/Admin-gated on /finance/audit."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth.dependencies import current_principal
from app.db import get_session
from app.models.audit import AuditLog
from app.principal import Principal

router = APIRouter(
    prefix="/audit",
    tags=["audit"],
    responses={401: {"description": "Missing or invalid bearer token"}},
)


@router.get("/me", response_model=list[AuditLog], summary="My own activity trail")
async def my_audit(
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
    limit: int = 200,
) -> list[AuditLog]:
    """The actions this user personally performed, most recent first. Powers the per-user
    'My Activity' view; unlike /finance/audit it is never org-wide."""
    rows = session.exec(
        select(AuditLog)
        .where(AuditLog.actor_id == principal.subject_id)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
    ).all()
    return list(rows)

"""Notification routes (SCOPING §6.4). The signed-in user's in-app notifications + a
mark-all-read. Scoped to the recipient by the bearer token."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.auth.dependencies import current_principal
from app.db import get_session
from app.principal import Principal
from app.schemas.dto import NotificationOut
from app.services import notification_service

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    responses={401: {"description": "Missing or invalid bearer token"}},
)


@router.get("", response_model=list[NotificationOut], summary="My notifications (newest first)")
async def list_notifications(
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> list[NotificationOut]:
    return [NotificationOut.model_validate(n) for n in notification_service.list_for(session, principal)]


@router.post("/read", response_model=list[NotificationOut], summary="Mark all my notifications read")
async def mark_read(
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> list[NotificationOut]:
    return [
        NotificationOut.model_validate(n) for n in notification_service.mark_all_read(session, principal)
    ]

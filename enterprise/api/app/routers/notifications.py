"""Notification routes (SCOPING §6.4). The signed-in user's in-app notifications + a
mark-all-read. Scoped to the recipient by the bearer token."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Response
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

_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "notification not found")


@router.get("", response_model=list[NotificationOut], summary="My notifications (newest first)")
async def list_notifications(
    include_archived: bool = False,
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> list[NotificationOut]:
    return [
        NotificationOut.model_validate(n)
        for n in notification_service.list_for(session, principal, include_archived=include_archived)
    ]


@router.post("/read", response_model=list[NotificationOut], summary="Mark all my notifications read")
async def mark_read(
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> list[NotificationOut]:
    return [
        NotificationOut.model_validate(n) for n in notification_service.mark_all_read(session, principal)
    ]


@router.post("/{notification_id}/read", response_model=NotificationOut, summary="Mark one notification read")
async def mark_one_read(
    notification_id: str,
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> NotificationOut:
    n = notification_service.mark_one_read(session, principal, notification_id)
    if n is None:
        raise _NOT_FOUND
    return NotificationOut.model_validate(n)


@router.post("/{notification_id}/archive", response_model=NotificationOut, summary="Archive a notification")
async def archive(
    notification_id: str,
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> NotificationOut:
    n = notification_service.set_archived(session, principal, notification_id, True)
    if n is None:
        raise _NOT_FOUND
    return NotificationOut.model_validate(n)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a notification")
async def delete_notification(
    notification_id: str,
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> Response:
    if not notification_service.delete_one(session, principal, notification_id):
        raise _NOT_FOUND
    return Response(status_code=status.HTTP_204_NO_CONTENT)

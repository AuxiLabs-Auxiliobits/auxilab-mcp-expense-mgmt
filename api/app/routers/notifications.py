"""Notification routes (SCOPING §3.4, §6.5). Recipient-scoped: a user only ever sees and
mutates their own notifications, derived from the auth token (never a client-supplied id)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth.dependencies import current_principal
from app.db import get_session
from app.models.notification import Notification
from app.principal import Principal
from app.schemas.dto import NotificationOut

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    responses={401: {"description": "Missing or invalid bearer token"}},
)


def _to_out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id, kind=n.kind, icon=n.icon, title=n.title, body=n.body,
        href=n.href, read=n.read, timestamp=n.created_at,
    )


@router.get("", response_model=list[NotificationOut], summary="My notifications (newest first)")
async def list_notifications(
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
    limit: int = 50,
) -> list[NotificationOut]:
    rows = session.exec(
        select(Notification)
        .where(Notification.recipient_id == principal.subject_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    ).all()
    return [_to_out(n) for n in rows]


@router.post("/read", response_model=list[NotificationOut], summary="Mark all my notifications read")
async def mark_all_read(
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> list[NotificationOut]:
    """Flip every unread notification for the caller to read, then return the current list."""
    unread = session.exec(
        select(Notification).where(
            Notification.recipient_id == principal.subject_id,
            Notification.read == False,  # noqa: E712 — SQL boolean comparison
        )
    ).all()
    for n in unread:
        n.read = True
        session.add(n)
    session.commit()

    rows = session.exec(
        select(Notification)
        .where(Notification.recipient_id == principal.subject_id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    ).all()
    return [_to_out(n) for n in rows]

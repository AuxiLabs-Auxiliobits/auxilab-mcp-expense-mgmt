"""Notification routes (SCOPING §3.4, §6.5). Recipient-scoped: a user only ever sees and
mutates their own notifications, derived from the auth token (never a client-supplied id)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth.dependencies import current_principal
from app.db import get_session
from app.models.notification import Notification
from app.principal import Principal
from app.schemas.dto import MessageResponse, NotificationOut

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    responses={401: {"description": "Missing or invalid bearer token"}},
)


def _to_out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id, kind=n.kind, icon=n.icon, title=n.title, body=n.body,
        href=n.href, entity=n.entity, read=n.read, archived=n.archived, timestamp=n.created_at,
    )


def _owned(session: Session, principal: Principal, notif_id: str) -> Notification:
    """Fetch a notification, enforcing recipient ownership (404 otherwise — never reveal others')."""
    n = session.get(Notification, notif_id)
    if n is None or n.recipient_id != principal.subject_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    return n


@router.get("", response_model=list[NotificationOut], summary="My notifications (newest first)")
async def list_notifications(
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
    limit: int = 50,
    include_archived: bool = False,
) -> list[NotificationOut]:
    stmt = select(Notification).where(Notification.recipient_id == principal.subject_id)
    if not include_archived:
        stmt = stmt.where(Notification.archived == False)  # noqa: E712
    rows = session.exec(stmt.order_by(Notification.created_at.desc()).limit(limit)).all()
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
        .where(
            Notification.recipient_id == principal.subject_id,
            Notification.archived == False,  # noqa: E712
        )
        .order_by(Notification.created_at.desc())
        .limit(50)
    ).all()
    return [_to_out(n) for n in rows]


@router.post("/{notif_id}/read", response_model=NotificationOut, summary="Mark one notification read")
async def mark_one_read(
    notif_id: str,
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> NotificationOut:
    n = _owned(session, principal, notif_id)
    if not n.read:
        n.read = True
        session.add(n)
        session.commit()
        session.refresh(n)
    return _to_out(n)


@router.post("/{notif_id}/archive", response_model=NotificationOut, summary="Archive one notification")
async def archive_one(
    notif_id: str,
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> NotificationOut:
    n = _owned(session, principal, notif_id)
    n.archived = True
    n.read = True  # archiving implies seen
    session.add(n)
    session.commit()
    session.refresh(n)
    return _to_out(n)


@router.delete("/{notif_id}", response_model=MessageResponse, summary="Delete one notification")
async def delete_one(
    notif_id: str,
    principal: Principal = Depends(current_principal),
    session: Session = Depends(get_session),
) -> MessageResponse:
    n = _owned(session, principal, notif_id)
    session.delete(n)
    session.commit()
    return MessageResponse(message="Notification deleted")

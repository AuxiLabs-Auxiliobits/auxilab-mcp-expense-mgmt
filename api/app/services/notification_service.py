"""In-app notifications (SCOPING §6.4). Emitted on workflow transitions; read per-recipient.
`notify`/`notify_role_in_agency` only add rows — the caller commits with the surrounding unit
of work so the notification and the effect are atomic.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.notification import Notification
from app.models.user import User
from app.principal import Principal, Role


def notify(
    session: Session,
    *,
    recipient_id: str | None,
    kind: str,
    title: str,
    body: str = "",
    href: str | None = None,
    icon: str = "notifications",
    entity: str | None = None,
    agency_id: str | None = None,
) -> None:
    if not recipient_id:
        return
    session.add(
        Notification(
            recipient_id=recipient_id, agency_id=agency_id, kind=kind, icon=icon,
            title=title, body=body, href=href, entity=entity,
        )
    )


def notify_role_in_agency(
    session: Session,
    *,
    agency_id: str | None,
    role: Role,
    kind: str,
    title: str,
    body: str = "",
    href: str | None = None,
    icon: str = "notifications",
    entity: str | None = None,
    exclude_user_id: str | None = None,
) -> None:
    """Notify every active user with `role` in `agency_id` (e.g. all managers of an agency).
    `exclude_user_id` skips one recipient (e.g. the actor who triggered the event)."""
    if not agency_id:
        return
    recipients = session.exec(
        select(User).where(
            User.agency_id == agency_id,
            User.role == role,
            User.is_active == True,  # noqa: E712 — SQLModel/SQLAlchemy boolean column compare
        )
    ).all()
    for u in recipients:
        if exclude_user_id and u.id == exclude_user_id:
            continue
        session.add(
            Notification(
                recipient_id=u.id, agency_id=agency_id, kind=kind, icon=icon,
                title=title, body=body, href=href, entity=entity,
            )
        )


def list_for(session: Session, principal: Principal, *, limit: int = 50) -> list[Notification]:
    return list(
        session.exec(
            select(Notification)
            .where(Notification.recipient_id == principal.subject_id)
            .order_by(Notification.created_at.desc())  # type: ignore[attr-defined]
            .limit(limit)
        ).all()
    )


def mark_all_read(session: Session, principal: Principal) -> list[Notification]:
    rows = session.exec(
        select(Notification).where(
            Notification.recipient_id == principal.subject_id,
            Notification.read == False,  # noqa: E712
        )
    ).all()
    for n in rows:
        n.read = True
        session.add(n)
    session.commit()
    return list_for(session, principal)

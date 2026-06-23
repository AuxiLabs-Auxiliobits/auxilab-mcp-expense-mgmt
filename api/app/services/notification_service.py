"""In-app notification generation (SCOPING §3.4, §6.5).

Notifications are created at workflow transitions by the sheet/finance services and read back
recipient-scoped via the /notifications router. Like audit, writes here do NOT commit — the
caller owns the surrounding unit of work so the notification and its triggering effect are
atomic.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.notification import Notification
from app.models.user import User
from app.principal import Role


def notify(
    session: Session,
    *,
    recipient_id: str,
    title: str,
    body: str = "",
    kind: str = "info",
    icon: str = "notifications",
    href: str | None = None,
    entity: str | None = None,
    agency_id: str | None = None,
) -> Notification:
    """Queue one notification for a single recipient (no commit)."""
    n = Notification(
        recipient_id=recipient_id, title=title, body=body, kind=kind, icon=icon,
        href=href, entity=entity, agency_id=agency_id,
    )
    session.add(n)
    return n


def notify_role_in_agency(
    session: Session,
    *,
    role: Role,
    agency_id: str,
    title: str,
    body: str = "",
    kind: str = "info",
    icon: str = "notifications",
    href: str | None = None,
    entity: str | None = None,
    exclude_user_id: str | None = None,
) -> list[Notification]:
    """Fan out one notification to every active user of `role` in `agency_id`.

    Used to alert all of an agency's managers when a sheet lands in their review queue.
    `exclude_user_id` avoids notifying the actor about their own action.
    """
    recipients = session.exec(
        select(User).where(
            User.role == role,
            User.agency_id == agency_id,
            User.is_active == True,  # noqa: E712 — SQL boolean comparison
        )
    ).all()
    out: list[Notification] = []
    for u in recipients:
        if exclude_user_id is not None and u.id == exclude_user_id:
            continue
        out.append(
            notify(
                session, recipient_id=u.id, title=title, body=body, kind=kind,
                icon=icon, href=href, entity=entity, agency_id=agency_id,
            )
        )
    return out

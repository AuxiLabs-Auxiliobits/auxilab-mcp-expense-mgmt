"""In-app notifications (SCOPING §6.4). Emitted on workflow transitions; read per-recipient.
`notify`/`notify_role_in_agency` only add rows — the caller commits with the surrounding unit
of work so the notification and the effect are atomic.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.notification import Notification
from app.models.user import User
from app.principal import Principal, Role

# Default on/off per notification category — MUST match the Settings page fallbacks so an
# unset preference behaves identically in the UI and here (frontend: settings/page.tsx PREFS).
_PREF_DEFAULTS = {
    "statusChanges": True,
    "infoRequests": True,
    "paymentConfirmations": False,
}


def _wants(session: Session, recipient_id: str, category: str | None) -> bool:
    """Whether the recipient opted in to this notification category. Uncategorised
    notifications (category=None) are always delivered; categorised ones respect the user's
    saved toggle, falling back to the category default when unset (SCOPING §6.4)."""
    if category is None:
        return True
    user = session.get(User, recipient_id)
    prefs = (user.preferences or {}) if user else {}
    if category in prefs:
        return bool(prefs[category])
    return _PREF_DEFAULTS.get(category, True)


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
    category: str | None = None,
) -> None:
    if not recipient_id:
        return
    # Honour the recipient's notification preferences (write-once, read-here).
    if not _wants(session, recipient_id, category):
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


def notify_role(
    session: Session,
    *,
    role: Role,
    kind: str,
    title: str,
    body: str = "",
    href: str | None = None,
    icon: str = "notifications",
    entity: str | None = None,
) -> int:
    """Notify every active user with `role` org-wide (e.g. all Finance reviewers, who aren't
    agency-bound). Returns the number of recipients. Adds rows only — caller commits."""
    recipients = session.exec(
        select(User).where(
            User.role == role,
            User.is_active == True,  # noqa: E712
        )
    ).all()
    for u in recipients:
        session.add(
            Notification(
                recipient_id=u.id, agency_id=u.agency_id, kind=kind, icon=icon,
                title=title, body=body, href=href, entity=entity,
            )
        )
    return len(recipients)


def list_for(
    session: Session, principal: Principal, *, limit: int = 50, include_archived: bool = False
) -> list[Notification]:
    stmt = select(Notification).where(Notification.recipient_id == principal.subject_id)
    if not include_archived:
        stmt = stmt.where(Notification.archived == False)  # noqa: E712
    return list(
        session.exec(
            stmt.order_by(Notification.created_at.desc()).limit(limit)  # type: ignore[attr-defined]
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


def _owned_or_none(session: Session, principal: Principal, notification_id: str) -> Notification | None:
    """Fetch a notification only if it belongs to the caller — otherwise None (the router
    turns that into a 404, so a non-owner can't even tell the row exists)."""
    n = session.get(Notification, notification_id)
    if n is None or n.recipient_id != principal.subject_id:
        return None
    return n


def mark_one_read(session: Session, principal: Principal, notification_id: str) -> Notification | None:
    n = _owned_or_none(session, principal, notification_id)
    if n is None:
        return None
    n.read = True
    session.add(n)
    session.commit()
    session.refresh(n)
    return n


def set_archived(
    session: Session, principal: Principal, notification_id: str, archived: bool
) -> Notification | None:
    n = _owned_or_none(session, principal, notification_id)
    if n is None:
        return None
    n.archived = archived
    session.add(n)
    session.commit()
    session.refresh(n)
    return n


def delete_one(session: Session, principal: Principal, notification_id: str) -> bool:
    n = _owned_or_none(session, principal, notification_id)
    if n is None:
        return False
    session.delete(n)
    session.commit()
    return True

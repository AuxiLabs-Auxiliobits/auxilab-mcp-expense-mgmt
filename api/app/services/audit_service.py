"""Append-only audit writer (SCOPING §3.3, §9). Every permission-relevant action and
state transition flows through here. Records are never updated or deleted in app code.
"""

from __future__ import annotations

from sqlmodel import Session

from app.models.audit import AuditLog
from app.principal import Principal


def record(
    session: Session,
    *,
    action: str,
    actor: Principal | None = None,
    entity: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    agency_id: str | None = None,
) -> AuditLog:
    """Append one audit row. Caller controls the transaction (commit happens with the
    surrounding unit of work so audit and effect are atomic)."""
    entry = AuditLog(
        actor_id=actor.subject_id if actor else None,
        actor_role=str(actor.role) if actor else None,
        agency_id=agency_id or (actor.agency_id if actor else None),
        action=action,
        entity=entity,
        before=before,
        after=after,
    )
    session.add(entry)
    return entry

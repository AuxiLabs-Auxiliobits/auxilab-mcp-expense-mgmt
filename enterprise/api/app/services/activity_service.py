"""Audit-trail / activity feed reads (SCOPING §3.3, §6.5, §9).

Role-scoped, paginated, filterable view over the append-only audit log:
  • Employee  → only their own actions
  • Manager   → every actor in their own agency (their department)
  • Finance / Admin → org-wide
  • Agent     → its own actions (service principal)

Writes go through `audit_service.record`; this module never mutates the log.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.audit import AuditLog
from app.models.user import User
from app.principal import Principal, Role, Scope
from app.schemas.dto import ActivityPageOut, AuditEntryOut

_MAX_PAGE_SIZE = 100


def _summary(action: str, actor_name: str | None, actor_role: str | None, entity: str | None) -> str:
    who = actor_name or (actor_role.title() if actor_role else "System")
    verb = action.replace("_", " ").lower()
    what = ""
    if entity:
        kind = entity.split(":", 1)[0].replace("_", " ")
        what = f" — {kind}"
    return f"{who} {verb}{what}"


def list_activity(
    session: Session,
    principal: Principal,
    *,
    page: int = 1,
    page_size: int = 25,
    action: str | None = None,
    actor_id: str | None = None,
    q: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> ActivityPageOut:
    page = max(1, page)
    page_size = min(max(1, page_size), _MAX_PAGE_SIZE)

    conds = []
    # --- Role scope (SCOPING §6.5) -------------------------------------------
    if principal.role is Role.EMPLOYEE or principal.role is Role.AGENT:
        conds.append(AuditLog.actor_id == principal.subject_id)
    elif principal.scope is Scope.AGENCY:  # manager → own agency
        conds.append(AuditLog.agency_id == principal.agency_id)
    # finance / admin (Scope.ALL) → no scope filter (org-wide)

    # --- Filters -------------------------------------------------------------
    if action:
        conds.append(AuditLog.action == action)
    if actor_id:
        conds.append(AuditLog.actor_id == actor_id)
    if q:
        like = f"%{q}%"
        conds.append(AuditLog.action.ilike(like) | AuditLog.entity.ilike(like))  # type: ignore[union-attr]
    if date_from is not None:
        conds.append(AuditLog.timestamp >= date_from)
    if date_to is not None:
        conds.append(AuditLog.timestamp <= date_to)

    base = select(AuditLog)
    for c in conds:
        base = base.where(c)

    total = session.exec(select(func.count()).select_from(base.subquery())).one()
    rows = list(
        session.exec(
            base.order_by(AuditLog.timestamp.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )

    # Resolve actor display names in one query.
    actor_ids = {r.actor_id for r in rows if r.actor_id}
    names: dict[str, str] = {}
    if actor_ids:
        names = {
            u.id: u.name
            for u in session.exec(select(User).where(User.id.in_(actor_ids))).all()  # type: ignore[attr-defined]
        }

    items = [
        AuditEntryOut(
            id=r.id,
            actor_id=r.actor_id,
            actor_name=names.get(r.actor_id) if r.actor_id else None,
            actor_role=r.actor_role,
            agency_id=r.agency_id,
            action=r.action,
            entity=r.entity,
            summary=_summary(r.action, names.get(r.actor_id) if r.actor_id else None, r.actor_role, r.entity),
            before=r.before,
            after=r.after,
            timestamp=r.timestamp,
        )
        for r in rows
    ]
    return ActivityPageOut(items=items, total=int(total), page=page, page_size=page_size)

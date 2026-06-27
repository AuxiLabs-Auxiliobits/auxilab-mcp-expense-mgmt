"""SLA / aging escalation (SCOPING §6.4, §8).

Sheets that sit in a review queue past the SLA are surfaced with **aging → escalation**
alerts so manager out-of-office and stuck manual-intervention sheets don't stall silently.
This is the backend counterpart to the portal's aging badges (frontend/src/lib/aging.ts):

  • SUBMITTED / IN_MANAGER_REVIEW   → waiting on the agency's managers
  • IN_FINANCE_REVIEW                → waiting on the LLM approver (stuck on the queue)
  • FINANCE_MANUAL_REVIEW            → waiting on a Finance reviewer

Each sheet is alerted **once per level per stage**: a warning when it crosses the warning
SLA, an escalation when it crosses the critical SLA. `last_escalation_level` /
`last_escalated_at` on the sheet make the job idempotent — re-running it doesn't re-notify,
and a sheet that advances stage (its `updated_at` moves past `last_escalated_at`) starts
aging afresh without every transition having to reset the counters.

Run it on a schedule (Container Apps job / cron hitting `POST /admin/escalations/run`, or
`python -m app.jobs.escalation_job`). It's a pure function over a session — fully testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.config import settings
from app.models.base import utcnow
from app.models.expense_sheet import ExpenseSheet
from app.principal import Role
from app.services import audit_service, notification_service
from expense_core.schemas.enums import SheetStatus

# Levels: 0 = within SLA, 1 = warning (aging), 2 = critical (escalation).
_WARNING = 1
_CRITICAL = 2

# Stages that can age, and who is alerted when they do.
_MANAGER_STAGES = {SheetStatus.SUBMITTED, SheetStatus.IN_MANAGER_REVIEW}
_FINANCE_STAGES = {SheetStatus.IN_FINANCE_REVIEW, SheetStatus.FINANCE_MANUAL_REVIEW}
_WAITING_STAGES = _MANAGER_STAGES | _FINANCE_STAGES


@dataclass
class EscalationSummary:
    scanned: int = 0  # sheets in a waiting stage considered
    warnings: int = 0  # sheets newly raised to the warning level this run
    escalations: int = 0  # sheets newly raised to the critical level this run

    def as_dict(self) -> dict[str, int]:
        return {"scanned": self.scanned, "warnings": self.warnings, "escalations": self.escalations}


def run_escalations(session: Session, *, now: datetime | None = None) -> EscalationSummary:
    """Scan every waiting sheet, emit aging/escalation alerts for those crossing an SLA, and
    record the new level on the sheet. Commits once at the end. Returns a run summary."""
    now = now or utcnow()
    warning_hours = settings.escalation_warning_hours
    critical_hours = settings.escalation_critical_hours

    summary = EscalationSummary()
    sheets = session.exec(
        select(ExpenseSheet).where(ExpenseSheet.status.in_(_WAITING_STAGES))  # type: ignore[attr-defined]
    ).all()

    for sheet in sheets:
        summary.scanned += 1
        waited_hours = _hours_waiting(sheet, now)
        level = (
            _CRITICAL if waited_hours >= critical_hours
            else _WARNING if waited_hours >= warning_hours
            else 0
        )
        if level == 0 or level <= _effective_prev_level(sheet):
            continue  # within SLA, or already alerted at this (or a higher) level this stage

        _emit(session, sheet, level=level, hours=waited_hours)
        sheet.last_escalation_level = level
        sheet.last_escalated_at = now
        session.add(sheet)
        if level == _CRITICAL:
            summary.escalations += 1
        else:
            summary.warnings += 1

    session.commit()
    return summary


def _hours_waiting(sheet: ExpenseSheet, now: datetime) -> float:
    """Hours since the sheet entered its current stage. `updated_at` is stamped on every
    transition, so it's the start of the current wait; fall back to submitted_at/created_at."""
    anchor = sheet.updated_at or sheet.submitted_at or sheet.created_at
    if anchor is None:
        return 0.0
    return max(0.0, (_aware(now) - _aware(anchor)).total_seconds() / 3600.0)


def _aware(dt: datetime) -> datetime:
    """Treat naive timestamps (SQLite round-trips drop tzinfo) as UTC so arithmetic with the
    timezone-aware `utcnow()` never mixes naive and aware datetimes."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _effective_prev_level(sheet: ExpenseSheet) -> int:
    """The level already alerted on for the *current* wait. A prior alert is stale (→ 0) once
    the sheet has changed stage since it was raised (updated_at past last_escalated_at)."""
    if sheet.last_escalated_at is None:
        return 0
    if sheet.updated_at and _aware(sheet.updated_at) > _aware(sheet.last_escalated_at):
        return 0
    return sheet.last_escalation_level


def _emit(session: Session, sheet: ExpenseSheet, *, level: int, hours: float) -> None:
    title_word = "Escalation" if level == _CRITICAL else "Aging sheet"
    kind = "error" if level == _CRITICAL else "warning"
    days = int(hours // 24)
    waited = f"{days}d" if days >= 1 else f"{int(hours)}h"
    sheet_title = sheet.title or "Expense sheet"
    body = f'"{sheet_title}" has been waiting {waited} for review.'

    if sheet.status in _MANAGER_STAGES:
        notification_service.notify_role_in_agency(
            session, role=Role.MANAGER, agency_id=sheet.agency_id, kind=kind, icon="schedule",
            title=f"{title_word}: awaiting manager review",
            body=body, href="/manager", entity=f"expense_sheet:{sheet.id}",
        )
    else:  # finance stages (LLM queue or manual review)
        notification_service.notify_role(
            session, role=Role.FINANCE, kind=kind, icon="schedule",
            title=f"{title_word}: awaiting finance review",
            body=body, href="/finance", entity=f"expense_sheet:{sheet.id}",
        )

    audit_service.record(
        session,
        action="ESCALATION_CRITICAL" if level == _CRITICAL else "ESCALATION_WARNING",
        entity=f"expense_sheet:{sheet.id}",
        agency_id=sheet.agency_id,
        after={"status": str(sheet.status), "hours_waiting": round(hours, 1), "level": level},
    )

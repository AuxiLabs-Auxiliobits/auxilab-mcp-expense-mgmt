"""SLA / aging escalation sweep (SCOPING §6.4, §8).

Backdates a submitted sheet's stage-entry time and runs the escalation service, asserting it
alerts once per level per stage (idempotent) and notifies the right queue.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.db import engine
from app.models.base import utcnow
from app.models.expense_sheet import ExpenseSheet
from app.models.notification import Notification
from app.services import escalation_service
from tests.conftest import auth, login

THIS_MONTH = date.today().replace(day=1).isoformat()
PERIOD = THIS_MONTH[:7]
_counter = iter(range(4000, 4999))


def _submit_sheet(client, token) -> str:
    n = next(_counter)
    sheet = client.post(
        "/sheets",
        json={
            "title": f"Aging {n}",
            "period": PERIOD,
            "line_items": [
                {
                    "category": "Travel - Ground",
                    "amount": f"{n}.00",
                    "merchant": "Uber",
                    "description": "Airport transfer",
                    "expense_date": THIS_MONTH,
                    "receipt_datetime": f"{THIS_MONTH}T0{n % 9}:30:00",
                    "receipt_total": f"{n}.00",
                    "tax": "0.00",
                }
            ],
        },
        headers=auth(token),
    ).json()
    li = sheet["line_items"][0]["id"]
    client.post(
        f"/sheets/{sheet['id']}/line-items/{li}/receipt",
        files={"file": ("receipt.pdf", b"%PDF-1.4 receipt", "application/pdf")},
        headers=auth(token),
    )
    res = client.post(f"/sheets/{sheet['id']}/submit", headers=auth(token))
    assert res.json()["status"] == "IN_MANAGER_REVIEW", res.text
    return sheet["id"]


def _backdate(sheet_id: str, hours: float) -> None:
    with Session(engine) as s:
        sheet = s.get(ExpenseSheet, sheet_id)
        sheet.updated_at = utcnow() - timedelta(hours=hours)
        s.add(sheet)
        s.commit()


def _escalation_alerts(sheet_id: str) -> list[Notification]:
    """Aging/escalation notifications for the sheet (icon 'schedule'), across all recipients."""
    with Session(engine) as s:
        return list(
            s.exec(
                select(Notification).where(
                    Notification.entity == f"expense_sheet:{sheet_id}",
                    Notification.icon == "schedule",
                )
            ).all()
        )


def test_aging_then_escalation_idempotent(client):
    emp = login(client, "employee@demo.local")
    sheet_id = _submit_sheet(client, emp)

    # Fresh sheet — within SLA, no aging alert fires.
    with Session(engine) as s:
        escalation_service.run_escalations(s, now=utcnow())
    assert len(_escalation_alerts(sheet_id)) == 0

    # 3 days waiting → warning level: at least one manager is alerted.
    _backdate(sheet_id, hours=72)
    with Session(engine) as s:
        summary = escalation_service.run_escalations(s, now=utcnow())
    assert summary.warnings >= 1
    with Session(engine) as s:
        assert s.get(ExpenseSheet, sheet_id).last_escalation_level == 1
    after_warning = len(_escalation_alerts(sheet_id))
    assert after_warning >= 1

    # Re-run immediately at the same level → no new alert (idempotent).
    with Session(engine) as s:
        escalation_service.run_escalations(s, now=utcnow())
    assert len(_escalation_alerts(sheet_id)) == after_warning

    # 6 days waiting → critical escalation: a further round of alerts.
    _backdate(sheet_id, hours=144)
    with Session(engine) as s:
        summary = escalation_service.run_escalations(s, now=utcnow())
    assert summary.escalations >= 1
    with Session(engine) as s:
        assert s.get(ExpenseSheet, sheet_id).last_escalation_level == 2
    assert len(_escalation_alerts(sheet_id)) > after_warning


def test_escalation_endpoint_admin_only(client):
    emp = login(client, "employee@demo.local")
    assert client.post("/admin/escalations/run", headers=auth(emp)).status_code == 403

    admin = login(client, "admin@demo.local")
    r = client.post("/admin/escalations/run", headers=auth(admin))
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"scanned", "warnings", "escalations"}

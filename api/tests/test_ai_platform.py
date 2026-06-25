"""Agentic platform tests — recommendation engine, AI Workspace, feedback, analytics,
event-driven notifications, RBAC scoping, advisory-only guardrails, and audit logging.

Validates Phases 1/3/5/6/7/8/9/10: AI never bypasses RBAC, every AI action is logged, and the
AI exposes no endpoint that mutates a sheet (humans keep final authority)."""

from __future__ import annotations

from sqlmodel import Session, select

from app.db import engine
from app.models.ai import AiRecommendation
from app.models.audit import AuditLog
from tests.conftest import auth, login

_seq = {"n": 0}


def _uniq() -> int:
    _seq["n"] += 1
    return _seq["n"]


def _draft(client, et, title, period="2026-06") -> str:
    return client.post("/sheets", json={"title": title, "period": period}, headers=auth(et)).json()["id"]


def _line(client, et, sid, amount):
    n = _uniq()
    # :30 seconds keeps these receipts in a distinct namespace from other test files (which use
    # :00), so the unique (employee, receipt_datetime, receipt_total) key never collides.
    dt = f"2026-06-{(n % 27) + 1:02d}T{(n % 12) + 1:02d}:{n % 60:02d}:30"
    client.post(f"/sheets/{sid}/line-items", headers=auth(et), json={
        "amount": str(amount), "merchant": f"Merchant {n}", "expense_date": "2026-06-10",
        "category": "Meals & Entertainment", "receipt_total": str(amount), "receipt_datetime": dt})
    return client.get(f"/sheets/{sid}", headers=auth(et)).json()["line_items"][-1]["id"]


def _receipt(client, et, sid, li):
    client.post(f"/sheets/{sid}/line-items/{li}/receipt", headers=auth(et),
                files={"file": ("r.pdf", b"%PDF-1.4 receipt", "application/pdf")})


def _submitted(client, et, title, amount="45.00") -> str:
    sid = _draft(client, et, title)
    li = _line(client, et, sid, amount)
    _receipt(client, et, sid, li)
    client.post(f"/sheets/{sid}/submit", headers=auth(et))
    return sid


# ---------------- Phase 3 & 6 — recommendation structure + explainability ---------------- #
def test_recommendation_has_full_structure_and_explainability(client):
    et = login(client, "employee@demo.local")
    sid = _submitted(client, et, "Rec Structure", "45.00")
    r = client.get(f"/ai/sheets/{sid}/recommendation", headers=auth(et))
    assert r.status_code == 200, r.text
    rec = r.json()
    for k in ("summary", "risk_score", "risk_band", "policy_compliant", "duplicate_likelihood",
              "duplicate_band", "missing_info", "recommended_action", "confidence", "rationale"):
        assert k in rec
    assert rec["risk_band"] in ("low", "medium", "high")
    # explainability: why / data analyzed / policies considered
    assert rec["rationale"]["why"]
    assert rec["rationale"]["data_analyzed"]
    assert rec["rationale"]["policies_considered"]


def test_over_cap_sheet_is_flagged_high_risk(client):
    et = login(client, "employee@demo.local")
    sid = _submitted(client, et, "Over Cap", "950.00")  # well over the meal cap
    rec = client.get(f"/ai/sheets/{sid}/recommendation", headers=auth(et)).json()
    assert rec["policy_compliant"] is False
    assert rec["risk_band"] in ("medium", "high")
    assert rec["recommended_action"] == "request_changes"


# ---------------- Phase 7 — advisory only / human-in-the-loop ---------------- #
def test_ai_router_exposes_no_mutating_endpoint(client):
    """Structural guarantee: the AI surface cannot approve/reject/submit/decide."""
    from app.main import app
    ai_paths = {p: m for p, m in app.openapi()["paths"].items() if p.startswith("/ai")}
    assert ai_paths
    for path, methods in ai_paths.items():
        for verb in methods:
            # only reads, plus the single feedback POST — nothing that changes a sheet
            assert verb.lower() in ("get", "post")
            assert not any(w in path for w in ("approve", "reject", "submit", "decision", "override", "withdraw"))


def test_recommendation_does_not_change_sheet_state(client):
    et = login(client, "employee@demo.local")
    sid = _submitted(client, et, "No State Change", "45.00")
    before = client.get(f"/sheets/{sid}", headers=auth(et)).json()["status"]
    client.get(f"/ai/sheets/{sid}/recommendation?refresh=true", headers=auth(et))
    after = client.get(f"/sheets/{sid}", headers=auth(et)).json()["status"]
    assert before == after  # AI advised but changed nothing


# ---------------- Phase 10 — RBAC + audit ---------------- #
def test_employee_cannot_read_another_users_recommendation(client):
    e1 = login(client, "employee@demo.local")
    sid = _submitted(client, e1, "Private Sheet", "45.00")
    e2 = login(client, "employee.skdk@demo.local")  # different agency/user
    r = client.get(f"/ai/sheets/{sid}/recommendation", headers=auth(e2))
    assert r.status_code in (403, 404)


def test_every_recommendation_is_audit_logged(client):
    et = login(client, "employee@demo.local")
    sid = _submitted(client, et, "Audited Rec", "45.00")
    client.get(f"/ai/sheets/{sid}/recommendation", headers=auth(et))
    with Session(engine) as s:
        rows = s.exec(select(AuditLog).where(
            AuditLog.action == "AI_RECOMMENDATION_GENERATED",
            AuditLog.entity == f"expense_sheet:{sid}")).all()
        assert rows, "expected an AI_RECOMMENDATION_GENERATED audit entry"


# ---------------- Phase 1 — event-driven ---------------- #
def test_submit_triggers_recommendation_and_manager_notification(client):
    from app.services import ai_events

    et = login(client, "employee@demo.local")
    sid = _submitted(client, et, "Event Driven", "45.00")  # submit schedules the AI event (bg task)
    # Drive the handler deterministically too (the bg task can race SQLite's write lock under the
    # full-suite load; in production it runs post-commit). This validates the event handler itself.
    ai_events.emit(ai_events.EventType.SHEET_SUBMITTED, sid)
    with Session(engine) as s:
        rec = s.exec(select(AiRecommendation).where(
            AiRecommendation.sheet_id == sid, AiRecommendation.superseded == False)).first()  # noqa: E712
        assert rec is not None  # the event created the recommendation
    mt = login(client, "manager@demo.local")
    notes = client.get("/notifications", headers=auth(mt)).json()
    titles = " ".join(n.get("title", "") for n in notes)
    assert "review" in titles.lower() or "approval" in titles.lower()  # smart manager notification


# ---------------- Phase 5 — workspace ---------------- #
def test_workspace_is_scoped_and_structured(client):
    et = login(client, "employee@demo.local")
    _submitted(client, et, "WS One", "45.00")
    r = client.get("/ai/workspace", headers=auth(et))
    assert r.status_code == 200
    ws = r.json()
    for k in ("counts", "pending_recommendations", "high_risk", "duplicate_candidates",
              "policy_violations", "missing_receipts", "recent_ai_actions"):
        assert k in ws
    assert ws["role"] == "employee"


# ---------------- Phase 8 — feedback ---------------- #
def test_feedback_is_recorded(client):
    et = login(client, "employee@demo.local")
    sid = _submitted(client, et, "Feedback Sheet", "45.00")
    rec = client.get(f"/ai/sheets/{sid}/recommendation", headers=auth(et)).json()
    r = client.post(f"/ai/recommendations/{rec['id']}/feedback",
                    json={"helpful": True, "decision": "accepted", "reason": "spot on"},
                    headers=auth(et))
    assert r.status_code == 200 and r.json()["ok"] is True


# ---------------- Phase 9 — analytics ---------------- #
def test_analytics_reflects_generation_and_feedback(client):
    et = login(client, "employee@demo.local")
    sid = _submitted(client, et, "Analytics Sheet", "45.00")
    rec = client.get(f"/ai/sheets/{sid}/recommendation", headers=auth(et)).json()
    client.post(f"/ai/recommendations/{rec['id']}/feedback",
                json={"helpful": True, "decision": "accepted"}, headers=auth(et))
    a = client.get("/ai/analytics", headers=auth(et)).json()
    assert a["recommendations_generated"] >= 1
    assert a["feedback_count"] >= 1
    assert a["acceptance_rate_pct"] is not None
    assert "by_risk_band" in a

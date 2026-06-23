"""Coverage for the finance decision lifecycle (Line 3) and admin agency/user CRUD —
the two largest previously-untested modules (finance_service, admin router)."""

from __future__ import annotations

from datetime import date

from tests.conftest import auth, login

THIS_MONTH = date.today().replace(day=1).isoformat()
_counter = iter(range(11000, 19000))


def _sheet_to_finance_review(client) -> str:
    """Drive a fresh sheet all the way to IN_FINANCE_REVIEW (employee submit → manager approve)."""
    n = next(_counter)
    emp = login(client, "employee@demo.local")
    payload = {
        "title": f"Fin {n}",
        "period": THIS_MONTH[:7],
        "line_items": [
            {
                "category": "Travel - Air",
                "amount": f"{n}.00",
                "merchant": f"Air {n}",
                "description": "Flight",
                "expense_date": THIS_MONTH,
                "receipt_datetime": f"{THIS_MONTH}T0{n % 9}:15:00",
                "receipt_total": f"{n}.00",
                "tax": "0.00",
            }
        ],
    }
    sheet = client.post("/sheets", json=payload, headers=auth(emp)).json()
    for li in sheet["line_items"]:
        client.post(
            f"/sheets/{sheet['id']}/line-items/{li['id']}/receipt",
            files={"file": ("r.pdf", b"%PDF-1.4 r", "application/pdf")},
            headers=auth(emp),
        )
    client.post(f"/sheets/{sheet['id']}/submit", headers=auth(emp))
    mgr = login(client, "manager@demo.local")
    res = client.post(f"/manager/sheets/{sheet['id']}/approve", headers=auth(mgr))
    assert res.json()["status"] == "IN_FINANCE_REVIEW", res.text
    return sheet["id"]


def _llm(decision: str) -> dict:
    return {
        "decision": decision,
        "model_version": "gpt-4o@test",
        "policy_version": "baseline-v1",
        "cited_clauses": ["§4.2 meal cap"],
        "confidence": 0.91,
    }


# --- LLM (agent) decision webhook ------------------------------------------ #
def test_llm_auto_approve(client):
    sid = _sheet_to_finance_review(client)
    agent = login(client, "agent@demo.local")
    r = client.post(f"/finance/sheets/{sid}/llm-decision", json=_llm("APPROVED"), headers=auth(agent))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "FINANCE_APPROVED"


def test_llm_route_to_human_then_finance_resolves(client):
    sid = _sheet_to_finance_review(client)
    agent = login(client, "agent@demo.local")
    r = client.post(
        f"/finance/sheets/{sid}/llm-decision", json=_llm("ROUTED_TO_HUMAN"), headers=auth(agent)
    )
    assert r.json()["status"] == "FINANCE_MANUAL_REVIEW", r.text
    # The sheet now shows up in the finance manual-review queue.
    fin = login(client, "finance@demo.local")
    queue = client.get("/finance/queue", headers=auth(fin)).json()
    assert any(s["id"] == sid for s in queue)
    # Finance resolves it.
    dec = client.post(
        f"/finance/sheets/{sid}/decision",
        json={"approve": True, "reason": "Justified."},
        headers=auth(fin),
    )
    assert dec.status_code == 200, dec.text
    assert dec.json()["status"] == "APPROVED"


def test_llm_decision_requires_agent_role(client):
    sid = _sheet_to_finance_review(client)
    fin = login(client, "finance@demo.local")  # finance is not the AGENT principal
    r = client.post(f"/finance/sheets/{sid}/llm-decision", json=_llm("APPROVED"), headers=auth(fin))
    assert r.status_code == 403, r.text


def test_finance_override_llm_decision(client):
    sid = _sheet_to_finance_review(client)
    agent = login(client, "agent@demo.local")
    client.post(f"/finance/sheets/{sid}/llm-decision", json=_llm("APPROVED"), headers=auth(agent))
    fin = login(client, "finance@demo.local")
    r = client.post(
        f"/finance/sheets/{sid}/override",
        json={"approve": False, "reason": "Receipt mismatch on audit."},
        headers=auth(fin),
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "REJECTED"


def test_decision_trail_records_actions(client):
    sid = _sheet_to_finance_review(client)
    agent = login(client, "agent@demo.local")
    client.post(f"/finance/sheets/{sid}/llm-decision", json=_llm("APPROVED"), headers=auth(agent))
    emp = login(client, "employee@demo.local")
    trail = client.get(f"/sheets/{sid}/decisions", headers=auth(emp))
    assert trail.status_code == 200, trail.text
    assert any(d["action"] == "APPROVED" for d in trail.json())


# --- Admin: agency CRUD ---------------------------------------------------- #
def test_agency_crud_lifecycle(client):
    admin = login(client, "admin@demo.local")
    created = client.post("/admin/agencies", json={"name": f"Northwind {next(_counter)}"}, headers=auth(admin))
    assert created.status_code == 201, created.text
    aid = created.json()["id"]

    assert client.get(f"/admin/agencies/{aid}", headers=auth(admin)).status_code == 200
    renamed = client.patch(f"/admin/agencies/{aid}", json={"name": f"NW {next(_counter)}"}, headers=auth(admin))
    assert renamed.status_code == 200, renamed.text
    # No open sheets reference it → soft delete succeeds.
    deleted = client.delete(f"/admin/agencies/{aid}", headers=auth(admin))
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["status"] == "soft_deleted"


def test_agency_list_reports_user_counts(client):
    """The admin agency table column must show the real active-user count, not 0."""
    admin = login(client, "admin@demo.local")
    rows = client.get("/admin/agencies", headers=auth(admin)).json()
    crispin = next(a for a in rows if a["name"] == "Crispin")
    # Seeded: 5 demo users live in Crispin (employee/manager/finance/admin/agent).
    assert crispin["user_count"] >= 5, crispin


def test_agency_get_404(client):
    admin = login(client, "admin@demo.local")
    assert client.get("/admin/agencies/nope", headers=auth(admin)).status_code == 404


def test_admin_routes_forbidden_for_non_admin(client):
    fin = login(client, "finance@demo.local")
    assert client.get("/admin/agencies", headers=auth(fin)).status_code == 403
    assert client.get("/admin/users", headers=auth(fin)).status_code == 403


# --- Admin: user CRUD ------------------------------------------------------ #
def test_user_crud_lifecycle(client):
    admin = login(client, "admin@demo.local")
    email = f"crud-{next(_counter)}@demo.local"
    created = client.post(
        "/admin/users",
        json={"name": "CRUD User", "email": email, "role": "employee", "password": "demo"},
        headers=auth(admin),
    )
    assert created.status_code == 201, created.text
    uid = created.json()["id"]
    assert "password_hash" not in created.json()  # never leak the hash

    assert client.get(f"/admin/users/{uid}", headers=auth(admin)).status_code == 200
    upd = client.patch(f"/admin/users/{uid}", json={"role": "manager"}, headers=auth(admin))
    assert upd.status_code == 200 and upd.json()["role"] == "manager", upd.text
    # Soft delete (deactivate).
    de = client.delete(f"/admin/users/{uid}", headers=auth(admin))
    assert de.status_code == 200 and de.json()["is_active"] is False, de.text
    # Filter by is_active=false includes the deactivated user.
    inactive = client.get("/admin/users?is_active=false", headers=auth(admin)).json()
    assert any(u["id"] == uid for u in inactive)


def test_create_user_duplicate_email_conflicts(client):
    admin = login(client, "admin@demo.local")
    r = client.post(
        "/admin/users",
        json={"name": "Dup", "email": "employee@demo.local", "role": "employee", "password": "demo"},
        headers=auth(admin),
    )
    assert r.status_code == 409, r.text


def test_admin_cannot_deactivate_self(client):
    admin = login(client, "admin@demo.local")
    me = client.get("/auth/me", headers=auth(admin)).json()
    r = client.delete(f"/admin/users/{me['subject_id']}", headers=auth(admin))
    assert r.status_code == 409, r.text


def test_create_user_invalid_role_422(client):
    admin = login(client, "admin@demo.local")
    r = client.post(
        "/admin/users",
        json={"name": "Bad", "email": f"bad-{next(_counter)}@demo.local", "role": "wizard", "password": "x"},
        headers=auth(admin),
    )
    assert r.status_code == 422, r.text

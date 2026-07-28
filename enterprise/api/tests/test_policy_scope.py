"""Per-agency Finance isolation for policy-document management (design decision: Finance is
agency-scoped for policy docs; Admin stays org-wide). Seeded users live in the Crispin
agency; SKDK/JetFuel exist with no users."""

from __future__ import annotations

from tests.conftest import auth, login


def _agency_ids(client) -> dict[str, str]:
    admin = login(client, "admin@demo.local")
    rows = client.get("/admin/agencies", headers=auth(admin)).json()
    return {a["name"]: a["id"] for a in rows}


def test_finance_can_list_own_agency_policies(client):
    fin = login(client, "finance@demo.local")
    own = client.get("/auth/me", headers=auth(fin)).json()["agency_id"]
    r = client.get(f"/finance/policies/{own}", headers=auth(fin))
    assert r.status_code == 200


def test_finance_denied_other_agency_policies(client):
    fin = login(client, "finance@demo.local")
    ids = _agency_ids(client)
    other = ids["SKDK"]  # finance is in Crispin
    r = client.get(f"/finance/policies/{other}", headers=auth(fin))
    assert r.status_code == 403


def test_admin_can_list_any_agency_policies(client):
    admin = login(client, "admin@demo.local")
    ids = _agency_ids(client)
    r = client.get(f"/finance/policies/{ids['JetFuel']}", headers=auth(admin))
    assert r.status_code == 200

"""Policy Assistant RAG endpoint (SCOPING §7, §11). Offline path here (no Azure configured):
retrieval over the baseline ruleset + agency policy doc, deterministic grounded answer."""

from __future__ import annotations

from tests.conftest import auth, login


def test_assistant_answers_with_citations(client):
    token = login(client, "employee@demo.local")
    r = client.post("/assistant/policy", json={"query": "What is the per-meal limit?"}, headers=auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["answer"]
    assert body["routed_to_human"] is False
    # Grounded: cites at least one clause, and the meal cap is referenced.
    assert body["citations"], "expected cited clauses"
    assert any("meal" in (c["title"] + c["text"]).lower() for c in body["citations"])


def test_assistant_routes_to_human_when_uncovered(client):
    token = login(client, "employee@demo.local")
    r = client.post(
        "/assistant/policy",
        json={"query": "What is the company holiday schedule?"},
        headers=auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["routed_to_human"] is True
    assert body["citations"] == []
    assert "human" in body["answer"].lower()


def test_assistant_available_to_all_roles(client):
    for email in ("manager@demo.local", "finance@demo.local", "admin@demo.local"):
        token = login(client, email)
        r = client.post("/assistant/policy", json={"query": "Do I need a receipt?"}, headers=auth(token))
        assert r.status_code == 200, f"{email}: {r.text}"


def test_assistant_requires_auth(client):
    assert client.post("/assistant/policy", json={"query": "hi"}).status_code == 401


def test_assistant_rejects_empty_query(client):
    token = login(client, "employee@demo.local")
    assert client.post("/assistant/policy", json={"query": ""}, headers=auth(token)).status_code == 422

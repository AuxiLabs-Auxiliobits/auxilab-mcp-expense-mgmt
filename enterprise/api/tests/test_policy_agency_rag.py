"""Policy Assistant — agency-scoped RAG (Foundry/Azure Search + offline).

Verifies the assistant grounds answers in the *caller's own agency* policy:
  • Azure path: semantic-ranked retrieval, a broad agency fallback when nothing matches, and
    defense-in-depth agency trimming (no cross-agency leakage).
  • Offline path: the agency's uploaded policy document is preferred over the generic baseline.
"""

from __future__ import annotations

from sqlmodel import Session

from app.db import engine
from app.models.policy import AgencyPolicy
from app.services import assistant_service as svc
from tests.conftest import auth, login


# ----------------------------- Azure retrieval (unit) ----------------------------- #
class _FakeSearch:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def search(self, **kw):
        self.calls.append(kw)
        return self._responses.pop(0) if self._responses else []


def test_azure_uses_semantic_then_broad_agency_fallback():
    """Semantic pass returns nothing → fall back to the agency's full policy; cross-agency rows
    are dropped even if the index returns them."""
    fake = _FakeSearch([
        [],  # semantic pass: no hit
        [
            {"agency_id": "A1", "content": "Client dinners up to $200 per guest.", "policy_version": "v3"},
            {"agency_id": "OTHER", "content": "LEAK from another agency", "policy_version": "v9"},
        ],
    ])
    clauses, version = svc._azure_search(fake, "A1", "can I expense a client dinner?")
    assert fake.calls[0]["query_type"] == "semantic"               # semantic attempted first
    assert "agency_id eq 'A1'" in fake.calls[0]["filter"]          # agency-filtered
    assert fake.calls[1]["search_text"] == "*"                     # broad fallback used
    assert len(clauses) == 1 and "200" in clauses[0].text          # only the agency's clause
    assert version == "v3"


def test_azure_semantic_hit_skips_fallback():
    fake = _FakeSearch([[{"agency_id": "A1", "content": "Meals up to $75.", "policy_version": "v1"}]])
    clauses, version = svc._azure_search(fake, "A1", "meal limit?")
    assert len(fake.calls) == 1                                    # no fallback needed
    assert clauses and version == "v1"


def test_azure_semantic_error_falls_back_to_broad():
    """A service tier without the semantic ranker raises; we still return the agency's policy."""
    class _ErrSearch:
        def __init__(self):
            self.calls = []

        def search(self, **kw):
            self.calls.append(kw)
            if kw.get("query_type") == "semantic":
                raise RuntimeError("semantic ranker not available on this tier")
            return [{"agency_id": "A1", "content": "Hotels up to $250/night.", "policy_version": "v2"}]

    fake = _ErrSearch()
    clauses, version = svc._azure_search(fake, "A1", "hotel cap?")
    assert len(fake.calls) == 2 and clauses and version == "v2"


# ----------------------------- Offline agency preference (integration) ----------------------------- #
def test_offline_prefers_agency_policy_over_baseline(client, monkeypatch):
    token = login(client, "employee@demo.local")
    aid = client.get("/auth/me", headers=auth(token)).json()["agency_id"]

    # Give this agency an uploaded policy doc with an agency-specific clause.
    with Session(engine) as s:
        s.add(AgencyPolicy(agency_id=aid, version=99, doc_blob_uri="blob://agency-test-policy"))
        s.commit()
    monkeypatch.setattr(
        svc, "read_blob",
        lambda _uri: b"Client entertainment is reimbursed up to $200 per guest with prior manager approval.",
    )

    r = client.post("/assistant/policy",
                    json={"query": "what is the client entertainment limit?"}, headers=auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["routed_to_human"] is False
    # the answer is grounded in the AGENCY's own policy, not the generic baseline
    assert any("Agency policy" in c["source"] for c in body["citations"])
    assert "200" in body["answer"]
    assert body["policy_version"] == "agency-policy-v99"

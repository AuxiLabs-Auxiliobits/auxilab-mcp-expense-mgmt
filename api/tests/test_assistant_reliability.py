"""AI Assistant stabilization suite (Phases 1-9): full conversation flows, robust confirmation,
context/state management, duplicate prevention, varied input, MCP-tool verification, error
recovery, and user isolation. Drives the real MCP tools in-process against the seeded test DB."""

from __future__ import annotations

import pytest

from expense_mcp import auth as mcp_auth
from expense_mcp import client as mcp_client
from tests.conftest import auth, login


@pytest.fixture(autouse=True)
def _route_mcp_into_test_app(client):
    mcp_client.set_client(client)
    yield
    mcp_client.close()
    mcp_auth.clear_token()


def chat(client, token, message, context=None):
    r = client.post("/assistant/chat", json={"message": message, "context": context}, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


# --- state builders (all via the real API, so RBAC/state machine apply) -------------------- #
def _draft(client, etoken, title, period="2026-06") -> str:
    return client.post("/sheets", json={"title": title, "period": period}, headers=auth(etoken)).json()["id"]


_seq = {"n": 0}


def _uniq() -> int:
    _seq["n"] += 1
    return _seq["n"]


def _submittable(client, etoken, title) -> str:
    # The DB enforces a unique (employee_id, receipt_datetime, receipt_total) — vary both so each
    # built sheet has a distinct receipt (this IS the app's duplicate-receipt prevention).
    n = _uniq()
    amount = f"{40 + n}.00"
    dt = f"2026-06-{(n % 27) + 1:02d}T{(n % 12) + 1:02d}:{n % 60:02d}:00"
    sid = _draft(client, etoken, title)
    client.post(f"/sheets/{sid}/line-items", headers=auth(etoken), json={
        "amount": amount, "merchant": f"Cafe {n}", "expense_date": "2026-06-10",
        "category": "Meals & Entertainment", "receipt_total": amount,
        "receipt_datetime": dt})
    li = client.get(f"/sheets/{sid}", headers=auth(etoken)).json()["line_items"][0]["id"]
    client.post(f"/sheets/{sid}/line-items/{li}/receipt", headers=auth(etoken),
                files={"file": ("r.pdf", b"%PDF-1.4 receipt", "application/pdf")})
    return sid


def _submitted(client, etoken, title) -> str:
    sid = _submittable(client, etoken, title)
    client.post(f"/sheets/{sid}/submit", headers=auth(etoken))
    return sid


def _in_finance_manual(client, etoken, title) -> str:
    """submitted → manager approve → AI-approver routes to human → FINANCE_MANUAL_REVIEW."""
    sid = _submitted(client, etoken, title)
    mtoken = login(client, "manager@demo.local")
    client.post(f"/manager/sheets/{sid}/approve", headers=auth(mtoken))
    atoken = login(client, "agent@demo.local")
    client.post(f"/finance/sheets/{sid}/llm-decision", headers=auth(atoken), json={
        "decision": "ROUTED_TO_HUMAN", "model_version": "test", "policy_version": "baseline-v1",
        "cited_clauses": ["meal cap"], "confidence": 0.6})
    return sid


# ============================ Phase 3 & 6 — robust confirmation ============================ #
@pytest.mark.parametrize("affirm", ["yes", "okay", "ok", "sure", "go ahead", "do it", "yep", "proceed"])
def test_fuzzy_yes_confirms(client, affirm):
    et = login(client, "employee@demo.local")
    _submittable(client, et, f"Confirm {affirm}")
    listing = chat(client, et, "show my expenses")
    ref = [i["ref"] for i in listing["context"]["last_list"] if i["title"] == f"Confirm {affirm}"][0]
    ask = chat(client, et, f"submit {ref}", listing["context"])
    assert ask["pending"]["action"] == "submit"
    done = chat(client, et, affirm, ask["context"])
    assert "submit_expense" in done["tools_used"]
    assert done["pending"] is None  # state cleared


@pytest.mark.parametrize("deny", ["no", "cancel", "never mind", "stop", "nope", "forget it"])
def test_fuzzy_no_cancels_and_clears(client, deny):
    et = login(client, "employee@demo.local")
    _submittable(client, et, f"Deny {deny}")
    listing = chat(client, et, "show my expenses")
    ref = [i["ref"] for i in listing["context"]["last_list"] if i["title"] == f"Deny {deny}"][0]
    ask = chat(client, et, f"submit {ref}", listing["context"])
    out = chat(client, et, deny, ask["context"])
    assert "cancelled" in out["reply"].lower()
    assert out["pending"] is None
    assert "submit_expense" not in out["tools_used"]


def test_ambiguous_reply_keeps_pending(client):
    et = login(client, "employee@demo.local")
    _submittable(client, et, "Ambiguous Keep")
    listing = chat(client, et, "show my expenses")
    ref = [i["ref"] for i in listing["context"]["last_list"] if i["title"] == "Ambiguous Keep"][0]
    ask = chat(client, et, f"submit {ref}", listing["context"])
    huh = chat(client, et, "hmm not sure", ask["context"])
    assert huh["pending"] is not None and huh["pending"]["action"] == "submit"  # preserved
    assert "yes" in huh["reply"].lower()


def test_new_command_during_pending_switches(client):
    et = login(client, "employee@demo.local")
    _submittable(client, et, "Switch Away")
    listing = chat(client, et, "show my expenses")
    ref = listing["context"]["last_list"][0]["ref"]
    ask = chat(client, et, f"submit {ref}", listing["context"])
    # instead of yes/no, ask something else — should switch (implicit cancel)
    switched = chat(client, et, "what's the per-meal limit?", ask["context"])
    assert "ask_policy" in switched["tools_used"]
    assert switched["pending"] is None


# ============================ Phase 4 & 6 — references ============================ #
def test_ordinal_reference(client):
    et = login(client, "employee@demo.local")
    _submittable(client, et, "Ord Alpha")
    _submittable(client, et, "Ord Beta")
    listing = chat(client, et, "show my expenses")
    # pick the title at ref 2 to assert "the second one" maps to it
    second_title = [i["title"] for i in listing["context"]["last_list"] if i["ref"] == 2][0]
    out = chat(client, et, "submit the second one", listing["context"])
    assert out["pending"]["title"] == second_title


def test_latest_reference_without_a_list(client):
    et = login(client, "employee@demo.local")
    _submittable(client, et, "Latest Draft")
    # no prior listing in context — "submit my latest" must fetch + pick newest
    out = chat(client, et, "submit my latest draft")
    assert out["pending"] and out["pending"]["action"] == "submit"


def test_title_reference(client):
    et = login(client, "employee@demo.local")
    _submittable(client, et, "Barcelona Trip")
    listing = chat(client, et, "show my expenses")
    out = chat(client, et, "submit the Barcelona sheet", listing["context"])
    assert out["pending"]["title"] == "Barcelona Trip"


# ============================ Phase 1 — full flows ============================ #
def test_employee_submit_flow(client):
    et = login(client, "employee@demo.local")
    _submittable(client, et, "Submit Only Flow")
    l1 = chat(client, et, "show my expenses")
    ref = [i["ref"] for i in l1["context"]["last_list"] if i["title"] == "Submit Only Flow"][0]
    done = chat(client, et, "yes", chat(client, et, f"submit {ref}", l1["context"])["context"])
    assert "submit_expense" in done["tools_used"]


def test_employee_withdraw_draft_flow(client):
    """Withdraw is DRAFT-only in this app (draft → withdrawn)."""
    et = login(client, "employee@demo.local")
    _draft(client, et, "Withdraw Draft Flow")  # a plain draft
    l1 = chat(client, et, "show my expenses")
    ref = [i["ref"] for i in l1["context"]["last_list"] if i["title"] == "Withdraw Draft Flow"][0]
    done = chat(client, et, "yes", chat(client, et, f"withdraw {ref}", l1["context"])["context"])
    assert "withdraw_expense" in done["tools_used"]


def test_employee_resubmit_after_return(client):
    et = login(client, "employee@demo.local")
    sid = _submitted(client, et, "Resub Flow")
    # manager returns it
    mt = login(client, "manager@demo.local")
    ml = chat(client, mt, "show pending approvals")
    ref = [i["ref"] for i in ml["context"]["last_list"] if i["title"] == "Resub Flow"][0]
    chat(client, mt, "yes", chat(client, mt, f"return {ref} because itemize please", ml["context"])["context"])
    # employee resubmits
    el = chat(client, et, "show my expenses")
    ref2 = [i["ref"] for i in el["context"]["last_list"] if i["title"] == "Resub Flow"][0]
    done = chat(client, et, "yes", chat(client, et, f"resubmit {ref2}", el["context"])["context"])
    assert "resubmit_expense" in done["tools_used"]


def test_finance_approve_flow(client):
    et = login(client, "employee@demo.local")
    _in_finance_manual(client, et, "Fin Approve Flow")
    ft = login(client, "finance@demo.local")
    fl = chat(client, ft, "show the finance queue")
    ref = [i["ref"] for i in fl["context"]["last_list"] if i["title"] == "Fin Approve Flow"][0]
    done = chat(client, ft, "yes", chat(client, ft, f"approve {ref}", fl["context"])["context"])
    assert "finance_decision" in done["tools_used"]
    assert "approved" in done["reply"].lower()


def test_finance_reject_flow(client):
    et = login(client, "employee@demo.local")
    _in_finance_manual(client, et, "Fin Reject Flow")
    ft = login(client, "finance@demo.local")
    fl = chat(client, ft, "show the finance queue")
    ref = [i["ref"] for i in fl["context"]["last_list"] if i["title"] == "Fin Reject Flow"][0]
    ask = chat(client, ft, f"reject {ref} because it exceeds policy", fl["context"])
    assert ask["pending"]["action"] == "finance_reject" and "exceeds policy" in ask["pending"]["reason"]
    done = chat(client, ft, "yes", ask["context"])
    assert "finance_decision" in done["tools_used"]


# ============================ Phase 5 — duplicate prevention ============================ #
def test_duplicate_create_is_guarded(client):
    et = login(client, "employee@demo.local")
    _draft(client, et, "Dupe Guard", "2026-06")
    # guided create of the same title+period must hit the duplicate guard
    t1 = chat(client, et, "create a new expense sheet")
    t2 = chat(client, et, "Dupe Guard", t1["context"])
    out = chat(client, et, "2026-06", t2["context"])
    assert out["pending"] and out["pending"]["action"] == "create_confirm"
    assert "already have a draft" in out["reply"].lower()
    # confirming creates the second one
    done = chat(client, et, "yes", out["context"])
    assert "create_expense" in done["tools_used"]


def test_double_submit_is_rejected_gracefully(client):
    et = login(client, "employee@demo.local")
    sid = _submitted(client, et, "Double Submit")  # already submitted
    out = chat(client, et, "submit the Double Submit sheet")
    # bridge asks to confirm; confirming hits the API which rejects the state transition
    if out.get("pending"):
        out = chat(client, et, "yes", out["context"])
    assert "submit_expense" not in out["tools_used"] or "conflict" in out["reply"].lower() \
        or "didn't" in out["reply"].lower() or "already" in out["reply"].lower()


# ============================ Phase 6 — varied input ============================ #
def test_next_steps(client):
    mt = login(client, "manager@demo.local")
    out = chat(client, mt, "what do I need to do next?")
    assert "get_pending_approvals" in out["tools_used"]


def test_cross_user_request_declined(client):
    et = login(client, "employee@demo.local")
    out = chat(client, et, "show John's expenses")
    assert "your own" in out["reply"].lower()
    assert out["tools_used"] == []


def test_logout_requires_confirmation(client):
    et = login(client, "employee@demo.local")
    ask = chat(client, et, "log out")
    assert ask["pending"]["action"] == "logout"
    done = chat(client, et, "yes", ask["context"])
    assert "logout" in done["tools_used"]


# ============================ Phase 8 — error recovery ============================ #
def test_permission_denied_is_friendly_and_clears(client):
    et = login(client, "employee@demo.local")
    out = chat(client, et, "show the finance queue")
    assert "access" in out["reply"].lower()
    assert out["confidence"] == "low"


def test_submit_empty_sheet_explains_business_rule(client):
    et = login(client, "employee@demo.local")
    _draft(client, et, "Empty Sheet")  # no line items / receipt
    listing = chat(client, et, "show my expenses")
    ref = [i["ref"] for i in listing["context"]["last_list"] if i["title"] == "Empty Sheet"][0]
    done = chat(client, et, "yes", chat(client, et, f"submit {ref}", listing["context"])["context"])
    assert "submit_expense" not in done["tools_used"]
    assert done["reply"]  # a plain-language reason, no stack trace
    assert "Traceback" not in done["reply"]


# ============================ Phase 2/9 — user isolation ============================ #
def test_concurrent_users_do_not_cross_context(client):
    """Interleaved requests from two users must each act in their own scope (token is a ContextVar)."""
    et = login(client, "employee@demo.local")
    ft = login(client, "finance@demo.local")
    emp = chat(client, et, "who am i")
    fin = chat(client, ft, "who am i")
    assert "Employee" in emp["reply"] and "Finance" in fin["reply"]
    # employee listing then finance listing — refs must not bleed across users
    e_list = chat(client, et, "show my expenses")
    f_list = chat(client, ft, "show the finance queue")
    assert e_list["context"]["list_kind"] == "mine"
    assert f_list["context"]["list_kind"] == "finance"


# ============================ Phase 4 — the canonical numbered example ============================ #
def test_numbered_reference_submits_correct_sheet(client):
    et = login(client, "employee@demo.local")
    _submittable(client, et, "Travel")
    _submittable(client, et, "Meals")
    listing = chat(client, et, "show my expenses")
    target = [i for i in listing["context"]["last_list"] if i["title"] == "Meals"][0]
    ask = chat(client, et, f"submit {target['ref']}", listing["context"])
    assert ask["pending"]["title"] == "Meals" and ask["pending"]["id"] == target["id"]
    done = chat(client, et, "yes", ask["context"])
    assert "submit_expense" in done["tools_used"]
    assert "Meals" in done["reply"]

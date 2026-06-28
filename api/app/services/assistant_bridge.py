"""In-app AI Assistant bridge.

Turns a natural-language message into MCP **tool** calls — never direct backend logic. Every
business action runs through the existing `expense_mcp` tools (which forward the user's token,
so RBAC / agency-scope / SoD / audit are enforced by the API exactly as elsewhere). NL
understanding here is a transparent deterministic router + guided flows (slot-filling /
confirmation); it upgrades to an LLM by configuring Azure Foundry, without changing this contract.

Responses are business-friendly: numbered lists (no raw ids), plain-language summaries, and an
explainability footer (which MCP tools ran, what was done, what to do next).

State model (host-owned, stateless server): every reply returns an opaque `context` blob the
client echoes back. It carries the last numbered list (`last_list` + `list_kind`) for follow-up
references and a `pending` action awaiting confirmation. Confirmation is robust (fuzzy yes/no),
ambiguous replies keep the pending action, an explicit new command switches away from it, and a
transient failure preserves it so "yes" retries.
"""

from __future__ import annotations

import difflib
import re
from typing import Any, Callable

from app.principal import Principal

# ---- small NL lexicons ------------------------------------------------------------------- #
_AFFIRM = {
    "yes", "y", "yeah", "yep", "yup", "ya", "sure", "ok", "okay", "k", "confirm", "confirmed",
    "do it", "go ahead", "go", "proceed", "please do", "yes please", "sounds good", "correct",
    "affirmative", "approved", "submit it", "approve it", "send it", "absolutely",
}
_NEGATE = {
    "no", "n", "nope", "nah", "cancel", "never mind", "nevermind", "stop", "abort", "don't",
    "dont", "forget it", "leave it", "not now", "no thanks", "negative", "wait",
}
_ORDINALS = {
    "first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4,
    "fifth": 5, "5th": 5, "sixth": 6, "6th": 6, "seventh": 7, "7th": 7, "eighth": 8, "8th": 8,
    "ninth": 9, "9th": 9, "tenth": 10, "10th": 10,
}
_TITLE_STOPWORDS = {
    "the", "my", "a", "an", "of", "to", "for", "that", "this", "one", "it", "please", "sheet",
    "sheets", "expense", "expenses", "submit", "approve", "reject", "return", "withdraw",
    "resubmit", "draft", "latest", "last", "recent", "show", "review", "and", "with",
}
_TRANSIENT = {0, 408, 425, 429, 500, 502, 503, 504}


# --- result container --------------------------------------------------------------------- #
class ChatResult:
    def __init__(self) -> None:
        self.reply: str = ""
        self.tools_used: list[str] = []
        self.actions: list[str] = []
        self.suggestions: list[str] = []
        self.needs: list[str] | None = None
        self.pending: dict[str, Any] | None = None
        self.context: dict[str, Any] | None = None
        self.confidence: str = "high"

    def as_dict(self) -> dict[str, Any]:
        # `context` is the single opaque state blob the client echoes back next turn. Fold the
        # pending action into it so the round-trip carries everything (host-owned memory).
        ctx = dict(self.context or {})
        if self.pending is not None:
            ctx["pending"] = self.pending
        return {
            "reply": self.reply, "tools_used": self.tools_used, "actions": self.actions,
            "suggestions": self.suggestions, "needs": self.needs, "pending": self.pending,
            "context": ctx or None, "confidence": self.confidence,
        }


def _mcp():
    """Lazy import so the API still loads if the MCP package isn't installed."""
    from expense_mcp import auth as mcp_auth  # noqa: PLC0415
    from expense_mcp.client import ApiError  # noqa: PLC0415
    from expense_mcp.tools import (  # noqa: PLC0415
        admin, approvals, assistant, auth_tools, dashboard, expenses, finance, system, users,
    )
    return mcp_auth, ApiError, {
        "admin": admin, "approvals": approvals, "assistant": assistant, "auth_tools": auth_tools,
        "dashboard": dashboard, "expenses": expenses, "finance": finance,
        "system": system, "users": users,
    }


def handle_chat(token: str, principal: Principal, message: str, context: dict[str, Any] | None) -> dict[str, Any]:
    """Entry point (runs in a threadpool — the MCP tools are sync HTTP clients)."""
    mcp_auth, ApiError, T = _mcp()
    mcp_auth.set_token(token)  # this user's token for every MCP tool call (ContextVar-isolated)
    ctx = context or {}
    res = ChatResult()
    msg = message.strip()
    low = msg.lower()

    try:
        pending = ctx.get("pending")
        if pending:
            return _resolve_pending(T, ApiError, msg, low, ctx, pending, res, principal)
        skill = _route(low)
        skill(T, ApiError, msg, low, ctx, res, principal)
    except ApiError as e:
        res.reply = _friendly_error(e)
        res.confidence = "low"
    res.suggestions = res.suggestions or _suggestions_for(principal.role)
    return res.as_dict()


# --- routing ------------------------------------------------------------------------------ #
# A leading action verb wins over keyword matching, so a reason like "reject 1 because it
# breaks policy" routes to the reject action, not the policy reader.
_LEADING_VERBS: dict[str, Callable] = {}  # populated after skill defs (see _init_verbs)


def _route(low: str) -> Callable:
    head = re.findall(r"[a-z']+", low)[:3]
    for tok in head:
        if tok in ("please", "pls", "can", "could", "you", "would", "kindly", "now", "hey", "hi"):
            continue
        if tok in _LEADING_VERBS:
            return _LEADING_VERBS[tok]
        # Typo-tolerant imperative: "aprove 1", "submt the latest", "widthdraw" → nearest verb.
        near = difflib.get_close_matches(tok, _LEADING_VERBS.keys(), n=1, cutoff=0.82)
        if near:
            return _LEADING_VERBS[near[0]]
        break  # only the first meaningful word counts as the imperative verb
    # Order matters: more specific intents first (e.g. "resubmit"/"withdraw" before "submit").
    table: list[tuple[tuple[str, ...], Callable]] = [
        (("who am i", "what's my role", "whoami", "am i logged"), _skill_whoami),
        (("log out", "logout", "sign out", "log off"), _skill_logout),
        (("what do i need", "what next", "what's next", "next step", "what should i do",
          "anything pending", "my to-do", "my todo"), _skill_next),
        (("policy", "per-meal", "meal cap", "hotel cap", "limit", "allowed", "receipt rule",
          "deadline", "reimburse", "reimbursement", "is this allowed", "what's the cap"), _skill_policy),
        (("'s expense", "'s sheet", "'s receipt", "'s approval", "someone else", "other people",
          "another user", "other users"), _skill_cross_user),
        (("pending approval", "to approve", "to review", "review queue", "approvals", "pending sheets"), _skill_pending),
        (("finance queue", "manual review", "routed sheets", "finance review"), _skill_finance_queue),
        (("spend by category", "category spend", "by category"), _skill_spend_category),
        (("kpi", "auto-approval", "auto approval", "compliance rate"), _skill_kpis),
        (("dashboard", "metrics", "overview", "summary of spend", "total spend", "how much"), _skill_dashboard),
        (("list users", "all users", "user list", "accounts", "who has access"), _skill_users),
        (("list agencies", "all agencies", "agency list", "show agencies"), _skill_list_agencies),
        (("find user", "lookup user", "look up user", "user details", "who is", "is user",
          "has permission", "has access", "has role", "check user", "user info"), _skill_find_user),
        (("assign role", "change role", "set role", "promote", "make user", "give role",
          "grant role"), _skill_assign_role_admin),
        (("deactivate user", "disable user", "remove user", "revoke access"), _skill_deactivate_user_admin),
        (("create agency", "add agency", "new agency", "onboard agency"), _skill_create_agency),
        (("run escalation", "escalation sweep", "sla sweep", "aging check", "escalations"), _skill_run_escalations),
        (("system health", "is the system", "health check", "are services", "is everything up"), _skill_health),
        (("my activity", "my history", "audit", "what did i do"), _skill_activity),
        (("resubmit", "re-submit", "send it back in", "submit again"), _skill_resubmit),
        (("withdraw", "recall", "pull back", "take back"), _skill_withdraw),
        (("approve",), _skill_approve),
        (("reject", "return", "send back", "decline"), _skill_reject),
        (("submit",), _skill_submit),
        (("create", "new expense", "start an expense", "new sheet", "new draft", "add a sheet"), _skill_create),
        (("my expense", "my sheet", "my draft", "status of my", "my expenses", "my claims"), _skill_my_expenses),
    ]
    for keys, fn in table:
        if any(k in low for k in keys):
            return fn
    # Nothing in the exact table matched — try a fuzzy/synonym pass before giving up, so
    # off-script phrasings ("bin that draft", "what's on my plate", "kill sheet 2") still route.
    fn, _label, score = _fuzzy_route(low)
    if fn is not None and score >= _FUZZY_THRESHOLD:
        return fn
    return _skill_fallback


# --- read skills -------------------------------------------------------------------------- #
def _skill_whoami(T, ApiError, msg, low, ctx, res, principal):
    me = T["auth_tools"].whoami()
    res.tools_used = ["whoami"]
    res.reply = f"You're signed in as **{me.get('name')}** — {str(me.get('role','')).title()} at {me.get('agency') or 'your agency'}."
    res.actions = ["Read your profile"]


def _skill_policy(T, ApiError, msg, low, ctx, res, principal):
    ans = T["assistant"].ask_policy(msg)
    res.tools_used = ["ask_policy"]
    cites = ", ".join(c.get("title", "clause") for c in ans.get("citations", [])) or "none"
    res.reply = ans.get("answer", "")
    res.actions = [f"Answered from agency policy (cited: {cites})"]
    if ans.get("routed_to_human"):
        res.confidence = "low"


def _skill_pending(T, ApiError, msg, low, ctx, res, principal):
    rows = T["approvals"].get_pending_approvals()
    res.tools_used = ["get_pending_approvals"]
    res.reply, res.context = _numbered_sheets(rows, "pending sheet", "approvals")
    res.actions = [f"Listed {len(rows)} sheet(s) awaiting your review"]
    if rows:
        res.reply += "\n\nSay e.g. *“approve 1”* or *“return 1 because the receipt is missing”*."


def _skill_finance_queue(T, ApiError, msg, low, ctx, res, principal):
    rows = T["finance"].get_finance_queue()
    res.tools_used = ["get_finance_queue"]
    res.reply, res.context = _numbered_sheets(rows, "routed sheet", "finance")
    res.actions = [f"Listed {len(rows)} sheet(s) in finance manual review"]
    if rows:
        res.reply += "\n\nSay e.g. *“approve 1”* or *“reject 1 because it exceeds policy”*."


def _skill_my_expenses(T, ApiError, msg, low, ctx, res, principal):
    rows = T["expenses"].list_my_expenses()
    res.tools_used = ["list_my_expenses"]
    res.reply, res.context = _numbered_sheets(rows, "sheet", "mine")
    res.actions = [f"Listed your {len(rows)} expense sheet(s)"]
    if rows:
        res.reply += "\n\nSay e.g. *“submit 1”*, *“withdraw 2”*, or *“resubmit 1”*."


def _skill_dashboard(T, ApiError, msg, low, ctx, res, principal):
    d = T["dashboard"].get_dashboard_metrics()
    res.tools_used = ["get_dashboard_metrics"]
    res.reply = (
        f"**Spend overview**\n- Total spend: **{_money(d.get('grand_total'))}**\n"
        f"- Sheets: {d.get('sheet_count', 0)} · Line items: {d.get('line_item_count', 0)}\n"
        f"- Compliance rate: {d.get('compliance_rate_pct')}%\n"
        f"- At risk: {_money(d.get('total_at_risk'))} ({d.get('violation_count', 0)} flag(s))"
    )
    res.actions = ["Read the dashboard summary"]


def _skill_spend_category(T, ApiError, msg, low, ctx, res, principal):
    rows = T["dashboard"].get_spend_by_category()
    res.tools_used = ["get_spend_by_category"]
    if not rows:
        res.reply = "No spend recorded yet."
    else:
        lines = "\n".join(f"- {r.get('category')}: **{_money(r.get('amount'))}**" for r in rows[:10])
        res.reply = f"**Spend by category**\n{lines}"
    res.actions = ["Read spend-by-category"]


def _skill_kpis(T, ApiError, msg, low, ctx, res, principal):
    k = T["dashboard"].get_finance_kpis()
    res.tools_used = ["get_finance_kpis"]
    res.reply = (
        f"**Finance KPIs**\n- Auto-approval rate: {k.get('auto_approval_rate')}%\n"
        f"- Manual interventions: {k.get('manual_interventions')}\n"
        f"- Policy citations: {k.get('policy_citations')}\n"
        f"- Compliance rate: {k.get('policy_compliance_rate')}%"
    )
    res.actions = ["Read finance KPIs"]


def _skill_users(T, ApiError, msg, low, ctx, res, principal):
    rows = T["users"].list_users()
    res.tools_used = ["list_users"]
    lines = []
    for u in rows[:25]:
        role = str(u.get("role", "")).title()
        agency = u.get("agencyName") or u.get("agency_name") or ""
        active = u.get("isActive", u.get("is_active", True))
        parts = ["- **{}** \u2014 {}".format(u.get("name"), role)]
        if agency:
            parts.append(" \u00b7 {}".format(agency))
        if not active:
            parts.append(" (inactive)")
        lines.append("".join(parts))
    res.reply = "**Users ({})**\n".format(len(rows)) + "\n".join(lines)
    res.actions = ["Listed {} user(s)".format(len(rows))]
def _skill_health(T, ApiError, msg, low, ctx, res, principal):
    h = T["system"].server_health()
    res.tools_used = ["server_health"]
    res.reply = (
        f"**System status**\n- Assistant: online (v{h.get('version')})\n"
        f"- Backend reachable: {'yes' if h.get('api_reachable') else 'no'}"
    )
    res.actions = ["Checked system health"]


def _skill_activity(T, ApiError, msg, low, ctx, res, principal):
    rows = T["users"].my_activity(limit=15)
    res.tools_used = ["my_activity"]
    if not rows:
        res.reply = "No recorded activity yet."
    else:
        lines = "\n".join(f"- {str(r.get('action', '')).replace('_', ' ').capitalize()}" for r in rows[:15])
        res.reply = f"**Your recent activity**\n{lines}"
    res.actions = ["Read your activity trail"]



# --- admin skills ------------------------------------------------------------------------- #
_ROLE_PERMS = {
    "employee": "can create and submit their own expense sheets",
    "manager": "can approve or return expense sheets for their agency",
    "finance": "can make finance decisions on all sheets and view audit logs",
    "admin": "platform administrator — manages all users and agencies across the platform",
}
_ROLE_SYNONYMS: dict[str, str] = {
    "employee": "employee", "staff": "employee", "worker": "employee",
    "manager": "manager", "lead": "manager", "supervisor": "manager",
    "finance": "finance", "financial": "finance", "accountant": "finance", "reviewer": "finance",
    "admin": "admin", "administrator": "admin",
}


def _extract_name_hint(msg: str, low: str) -> str | None:
    patterns = [
        r"(?:find|lookup|look up|who is|is|check|show|about|for)\s+(?:user\s+)?([a-zA-Z0-9_.@\-]{2,40})",
        r"([a-zA-Z0-9_.@\-]{2,40})(?:'s)?\s+(?:permission|role|access|account|status|profile)",
        r"user\s+([a-zA-Z0-9_.@\-]{2,40})",
        r"(?:deactivate|disable|remove|promote|assign\s+role\s+to)\s+([a-zA-Z0-9_.@\-]{2,40})",
    ]
    stopwords = {"a", "an", "the", "is", "has", "with", "user", "admin", "role", "please"}
    for pat in patterns:
        m = re.search(pat, msg, re.I)
        if m:
            name = m.group(1).strip().lower()
            if name and name not in stopwords:
                return name
    return None


def _match_user(hint: str, rows: list[dict]) -> list[dict]:
    hint_l = hint.lower()
    return [
        u for u in rows
        if hint_l in str(u.get("name", "")).lower() or hint_l in str(u.get("email", "")).lower()
    ]


def _extract_target_role(low: str) -> str | None:
    for kw, role in _ROLE_SYNONYMS.items():
        if re.search(rf"\b{kw}\b", low):
            return role
    return None


def _format_user_card(u: dict) -> str:
    role = str(u.get("role", "")).lower()
    active = u.get("isActive", u.get("is_active", True))
    agency = u.get("agencyName") or u.get("agency_name") or ("All agencies" if role == "admin" else "—")
    perms = _ROLE_PERMS.get(role, role)
    status_str = "Active ✓" if active else "Inactive ✗"
    return (
        "**{}** ({})\n- Role: {} · Agency: {}\n- Status: {}\n- Permissions: {}".format(
            u.get("name"), u.get("email"), role.title(), agency, status_str, perms
        )
    )


def _skill_find_user(T, ApiError, msg, low, ctx, res, principal):
    name_hint = _extract_name_hint(msg, low)
    rows = T["users"].list_users()
    res.tools_used = ["list_users"]
    matches = _match_user(name_hint, rows) if name_hint else rows
    if not matches:
        res.reply = "No user found matching {}.".format(repr(name_hint))
        res.confidence = "low"
        return
    if len(matches) == 1:
        res.reply = _format_user_card(matches[0])
    elif len(matches) <= 5:
        res.reply = "Found {} matching users:\n\n".format(len(matches)) + "\n\n".join(_format_user_card(u) for u in matches)
    else:
        lines = "\n".join(
            "- **{}** ({}) — {}".format(u.get("name"), u.get("email"), str(u.get("role", "")).title())
            for u in matches[:10]
        )
        res.reply = "Found {} users matching {}:\n{}".format(len(matches), repr(name_hint), lines)
    res.actions = ["Looked up user details"]


def _skill_list_agencies(T, ApiError, msg, low, ctx, res, principal):
    rows = T["admin"].list_agencies()
    res.tools_used = ["list_agencies"]
    if not rows:
        res.reply = "No agencies found."
    else:
        lines = "\n".join(
            "- **{}** · {} user(s) · {}".format(
                a.get("name"), a.get("userCount", a.get("user_count", 0)), str(a.get("status", "active")).title()
            )
            for a in rows
        )
        res.reply = "**Agencies ({})**\n{}".format(len(rows), lines)
    res.actions = ["Listed {} agenc(ies)".format(len(rows))]


def _skill_create_agency(T, ApiError, msg, low, ctx, res, principal):
    m = re.search(r'(?:called|named|titled|agency)\s+["\']?([A-Za-z0-9 _\-&\.]{2,60})["\']?', msg, re.I)
    name = m.group(1).strip() if m else None
    if not name:
        res.needs = ["name"]
        res.pending = {"action": "create_agency"}
        res.reply = "What should the new agency be **named**?"
        return
    res.pending = {"action": "create_agency_confirm", "name": name}
    res.context = _carry(ctx)
    res.reply = "Create a new agency named **{}**? Reply **yes** to confirm.".format(name)
    res.confidence = "medium"


def _skill_assign_role_admin(T, ApiError, msg, low, ctx, res, principal):
    target_role = _extract_target_role(low)
    name_hint = _extract_name_hint(msg, low)
    if not name_hint:
        res.reply = "Which user should I change the role for? Try: assign manager role to [name]."
        res.confidence = "low"
        return
    rows = T["users"].list_users()
    res.tools_used = ["list_users"]
    matches = _match_user(name_hint, rows)
    if not matches:
        res.reply = "No user found matching {}.".format(repr(name_hint))
        res.confidence = "low"
        return
    if len(matches) > 1:
        lines = "\n".join(
            "- {} ({}) — {}".format(u.get("name"), u.get("email"), str(u.get("role", "")).title())
            for u in matches[:5]
        )
        res.reply = "Multiple users match {}:\n{}\n\nPlease be more specific (use their email).".format(repr(name_hint), lines)
        res.confidence = "low"
        return
    u = matches[0]
    if not target_role:
        res.reply = "What role should **{}** have? Choose: employee, manager, finance, or admin.".format(u.get("name"))
        res.pending = {"action": "assign_role_await_role", "user_id": u.get("id"), "user_name": u.get("name"), "user_email": u.get("email")}
        res.context = _carry(ctx)
        res.confidence = "medium"
        return
    res.pending = {
        "action": "assign_role_admin",
        "user_id": u.get("id"), "user_name": u.get("name"),
        "user_email": u.get("email"), "role": target_role,
    }
    res.context = _carry(ctx)
    res.reply = (
        "Change **{}**'s role from {} to **{}**? Reply **yes** to confirm.".format(
            u.get("name"), str(u.get("role", "")).title(), target_role.title()
        )
    )
    res.confidence = "medium"


def _skill_deactivate_user_admin(T, ApiError, msg, low, ctx, res, principal):
    name_hint = _extract_name_hint(msg, low)
    if not name_hint:
        res.reply = "Which user should I deactivate? Try: deactivate [name or email]."
        res.confidence = "low"
        return
    rows = T["users"].list_users()
    res.tools_used = ["list_users"]
    matches = _match_user(name_hint, rows)
    if not matches:
        res.reply = "No user found matching {}.".format(repr(name_hint))
        res.confidence = "low"
        return
    if len(matches) > 1:
        lines = "\n".join("- {} ({})".format(u.get("name"), u.get("email")) for u in matches[:5])
        res.reply = "Multiple users match {}:\n{}\n\nPlease be more specific.".format(repr(name_hint), lines)
        res.confidence = "low"
        return
    u = matches[0]
    if not u.get("isActive", u.get("is_active", True)):
        res.reply = "**{}** is already inactive.".format(u.get("name"))
        res.tools_used = ["list_users"]
        return
    res.pending = {"action": "deactivate_user_admin", "user_id": u.get("id"), "user_name": u.get("name")}
    res.context = _carry(ctx)
    res.reply = (
        "Deactivate **{}** ({})? They will no longer be able to sign in. Reply **yes** to confirm.".format(
            u.get("name"), u.get("email")
        )
    )
    res.confidence = "medium"


def _skill_run_escalations(T, ApiError, msg, low, ctx, res, principal):
    res.pending = {"action": "run_escalations"}
    res.context = _carry(ctx)
    res.reply = (
        "Run the SLA/aging escalation sweep now? This scans all queues and flags overdue sheets. "
        "Reply **yes** to confirm."
    )
    res.confidence = "medium"


# --- end admin skills --------------------------------------------------------------------- #

def _skill_next(T, ApiError, msg, low, ctx, res, principal):
    """'What do I need to do next?' — role-aware summary of outstanding work."""
    role = str(principal.role).lower()
    if role == "manager":
        rows = T["approvals"].get_pending_approvals()
        res.tools_used = ["get_pending_approvals"]
        res.reply = (
            f"You have **{len(rows)}** sheet(s) awaiting approval."
            + (" Say *“show pending approvals”* to review them." if rows else " Your queue is clear. 🎉")
        )
    elif role == "finance":
        rows = T["finance"].get_finance_queue()
        res.tools_used = ["get_finance_queue"]
        res.reply = (
            f"**{len(rows)}** sheet(s) need finance review."
            + (" Say *“show the finance queue”*." if rows else " Nothing routed to you right now. 🎉")
        )
    else:
        rows = T["expenses"].list_my_expenses()
        res.tools_used = ["list_my_expenses"]
        drafts = [r for r in rows if r.get("can_submit") or "DRAFT" in str(r.get("status", ""))]
        returned = [r for r in rows if "RETURN" in str(r.get("status", "")).upper()]
        res.reply = (
            f"You have **{len(drafts)}** draft(s) ready to submit and "
            f"**{len(returned)}** returned sheet(s) to fix."
        )
    res.actions = ["Summarized your next steps"]


def _skill_cross_user(T, ApiError, msg, low, ctx, res, principal):
    if str(principal.role).lower() == "admin":
        return _skill_find_user(T, ApiError, msg, low, ctx, res, principal)
    res.confidence = "low"
    res.reply = (
        "I can only access **your own** expenses and whatever your role already lets you see "
        "(e.g. a manager's own approval queue) — I can't pull up another person's expenses for you."
    )
    res.actions = ["Declined a cross-user request (out of scope)"]


# --- action skills (guided + confirmation) ------------------------------------------------ #
def _skill_approve(T, ApiError, msg, low, ctx, res, principal):
    role = str(principal.role).lower()
    if role == "finance":
        target = _resolve_target(low, ctx, lambda: T["finance"].get_finance_queue())
        if not target:
            return _ask_to_list(res, "approve", "show the finance queue")
        res.pending = {"action": "finance_approve", "id": target["id"], "title": target["title"]}
        res.reply = f"Approve **{target['title']}** in finance review? Reply **yes** to confirm."
    else:
        target = _resolve_target(low, ctx, lambda: T["approvals"].get_pending_approvals())
        if not target:
            return _ask_to_list(res, "approve", "show pending approvals")
        res.pending = {"action": "approve", "id": target["id"], "title": target["title"]}
        res.reply = f"Approve **{target['title']}**? This advances it to finance review. Reply **yes** to confirm."
    res.context = _carry(ctx)
    res.confidence = "medium"


def _skill_reject(T, ApiError, msg, low, ctx, res, principal):
    role = str(principal.role).lower()
    reason = _extract_reason(msg)
    if role == "finance":
        target = _resolve_target(low, ctx, lambda: T["finance"].get_finance_queue())
        if not target:
            return _ask_to_list(res, "reject", "show the finance queue")
        reason = reason or "Rejected by finance."
        res.pending = {"action": "finance_reject", "id": target["id"], "title": target["title"], "reason": reason}
        res.reply = f"Reject **{target['title']}** with the note *“{reason}”*? Reply **yes** to confirm."
    else:
        target = _resolve_target(low, ctx, lambda: T["approvals"].get_pending_approvals())
        if not target:
            return _ask_to_list(res, "return", "show pending approvals")
        reason = reason or "Please review and correct."
        res.pending = {"action": "return", "id": target["id"], "title": target["title"], "reason": reason}
        res.reply = f"Return **{target['title']}** to the employee with the note *“{reason}”*? Reply **yes** to confirm."
    res.context = _carry(ctx)
    res.confidence = "medium"


def _skill_submit(T, ApiError, msg, low, ctx, res, principal):
    target = _resolve_target(low, ctx, lambda: T["expenses"].list_my_expenses())
    if not target:
        return _ask_to_list(res, "submit", "show my expenses")
    res.pending = {"action": "submit", "id": target["id"], "title": target["title"]}
    res.context = _carry(ctx)
    res.reply = f"Submit **{target['title']}** for manager review? Reply **yes** to confirm."
    res.confidence = "medium"


def _skill_withdraw(T, ApiError, msg, low, ctx, res, principal):
    target = _resolve_target(low, ctx, lambda: T["expenses"].list_my_expenses())
    if not target:
        return _ask_to_list(res, "withdraw", "show my expenses")
    res.pending = {"action": "withdraw", "id": target["id"], "title": target["title"]}
    res.context = _carry(ctx)
    res.reply = f"Withdraw **{target['title']}**? This recalls it back to a draft so you can edit and resubmit. Reply **yes** to confirm."
    res.confidence = "medium"


def _skill_resubmit(T, ApiError, msg, low, ctx, res, principal):
    target = _resolve_target(low, ctx, lambda: T["expenses"].list_my_expenses())
    if not target:
        return _ask_to_list(res, "resubmit", "show my expenses")
    res.pending = {"action": "resubmit", "id": target["id"], "title": target["title"]}
    res.context = _carry(ctx)
    res.reply = f"Resubmit **{target['title']}** for review? Reply **yes** to confirm."
    res.confidence = "medium"


def _skill_logout(T, ApiError, msg, low, ctx, res, principal):
    res.pending = {"action": "logout"}
    res.reply = "Sign out of the assistant session? Reply **yes** to confirm."
    res.confidence = "medium"


def _skill_create(T, ApiError, msg, low, ctx, res, principal):
    period = _extract_period(msg)
    m = re.search(r"(?:called|titled|named)\s+[\"']?(.+?)[\"']?(?:\s+for\b|\s+in\b|$)", msg, re.I)
    title = m.group(1).strip()[:50] if m else None
    if not title:
        res.needs = ["title"]
        res.pending = {"action": "create", "period": period}
        res.reply = "Sure — what should the expense sheet be **titled**?"
        return
    if not period:
        res.needs = ["period"]
        res.pending = {"action": "create", "title": title}
        res.reply = f"Got it — **{title}**. Which **month** is it for? (e.g. 2026-06)"
        return
    _do_create(T, ApiError, title, period, res, principal, ctx)


# --- pending resolution ------------------------------------------------------------------- #
def _resolve_pending(T, ApiError, msg, low, ctx, pending, res, principal):
    action = pending.get("action")

    # 0) Admin slot-filling: awaiting a role name.
    if action == "assign_role_await_role":
        role = _extract_target_role(low)
        if not role:
            res.pending = pending
            res.context = _carry(ctx)
            res.reply = "Which role? Reply with: **employee**, **manager**, **finance**, or **admin**."
            res.confidence = "medium"
        else:
            res.pending = {
                "action": "assign_role_admin",
                "user_id": pending["user_id"], "user_name": pending["user_name"],
                "user_email": pending["user_email"], "role": role,
            }
            res.context = _carry(ctx)
            res.reply = "Change **{}**'s role to **{}**? Reply **yes** to confirm.".format(
                pending["user_name"], role.title()
            )
            res.confidence = "medium"
        res.suggestions = _suggestions_for(principal.role)
        return res.as_dict()

    # 0b) Admin agency name slot-filling.
    if action == "create_agency":
        name = _strip(msg)
        if not name:
            res.needs = ["name"]; res.pending = pending; res.reply = "What should the agency be named?"
        else:
            res.pending = {"action": "create_agency_confirm", "name": name}
            res.context = _carry(ctx)
            res.reply = "Create a new agency named **{}**? Reply **yes** to confirm.".format(name)
            res.confidence = "medium"
        res.suggestions = _suggestions_for(principal.role)
        return res.as_dict()

    # 1) Guided create slot-filling: the message supplies the next missing field.
    if action == "create":
        merged = dict(pending)
        if not merged.get("title"):
            merged["title"] = _strip(msg) or "Expenses"
        elif not merged.get("period"):
            merged["period"] = _extract_period(msg) or msg.strip()
        if not merged.get("title"):
            res.needs = ["title"]; res.pending = merged; res.reply = "What should the sheet be titled?"
        elif not merged.get("period"):
            res.needs = ["period"]; res.pending = merged
            res.reply = f"Which **month** is **{merged['title']}** for? (e.g. 2026-06)"
        else:
            _do_create(T, ApiError, merged["title"], merged["period"], res, principal, ctx)
        res.suggestions = _suggestions_for(principal.role)
        return res.as_dict()

    # 2) Confirmation actions: robust yes / no / ambiguous / new-command handling.
    if _affirmative(low):
        _execute(T, ApiError, action, pending, res, principal)
        res.suggestions = _suggestions_for(principal.role)
        return res.as_dict()
    if _negative(low):
        res.reply = "Okay, cancelled — nothing was changed."
        res.actions = ["Cancelled the pending action"]
        res.suggestions = _suggestions_for(principal.role)
        return res.as_dict()

    # Not a clear yes/no. If it's plainly a new command, switch to it (implicit cancel);
    # otherwise re-ask and KEEP the pending action so the task isn't lost.
    new_skill = _route(low)
    if new_skill is not _skill_fallback:
        ctx2 = {k: v for k, v in ctx.items() if k != "pending"}
        new_skill(T, ApiError, msg, low, ctx2, res, principal)
        res.suggestions = res.suggestions or _suggestions_for(principal.role)
        return res.as_dict()

    res.pending = pending  # keep it alive
    res.context = _carry(ctx)
    res.reply = f"Sorry, I didn't catch that — reply **yes** to {pending.get('action', 'confirm')} or **no** to cancel."
    res.confidence = "low"
    res.suggestions = _suggestions_for(principal.role)
    return res.as_dict()


def _execute(T, ApiError, action, pending, res, principal):
    """Run the confirmed MCP tool. On a transient failure, keep `pending` so 'yes' retries."""
    try:
        if action == "approve":
            out = T["approvals"].approve_sheet(pending["id"])
            res.tools_used = ["approve_sheet"]
            res.reply = f"Approved **{pending['title']}** — it's now in {_status(out)}."
            res.actions = [f"Approved “{pending['title']}”"]
        elif action == "finance_approve":
            out = T["finance"].finance_decision(pending["id"], True, "Approved by finance.")
            res.tools_used = ["finance_decision"]
            res.reply = f"Approved **{pending['title']}** — it's now {_status(out)}."
            res.actions = [f"Finance-approved “{pending['title']}”"]
        elif action == "finance_reject":
            out = T["finance"].finance_decision(pending["id"], False, pending.get("reason", "Rejected."))
            res.tools_used = ["finance_decision"]
            res.reply = f"Rejected **{pending['title']}** — it's now {_status(out)}."
            res.actions = [f"Finance-rejected “{pending['title']}”"]
        elif action == "return":
            sheet = T["expenses"].get_expense(pending["id"])
            items = sheet.get("line_items") or []
            if not items:
                res.reply = "That sheet has no line items to return."
                res.confidence = "low"
                return
            T["approvals"].return_to_employee(pending["id"], items[0]["id"], pending["reason"])
            res.tools_used = ["get_expense", "return_to_employee"]
            res.reply = f"Returned **{pending['title']}** to the employee with your note."
            res.actions = [f"Returned “{pending['title']}”"]
        elif action == "submit":
            out = T["expenses"].submit_expense(pending["id"])
            res.tools_used = ["submit_expense"]
            res.reply = f"Submitted **{pending['title']}** — it's now in {_status(out)}."
            res.actions = [f"Submitted “{pending['title']}”"]
        elif action == "withdraw":
            out = T["expenses"].withdraw_expense(pending["id"])
            res.tools_used = ["withdraw_expense"]
            res.reply = f"Withdrew the draft **{pending['title']}** — it's now {_status(out)}."
            res.actions = [f"Withdrew “{pending['title']}”"]
        elif action == "resubmit":
            out = T["expenses"].resubmit_expense(pending["id"])
            res.tools_used = ["resubmit_expense"]
            res.reply = f"Resubmitted **{pending['title']}** — it's now in {_status(out)}."
            res.actions = [f"Resubmitted “{pending['title']}”"]
        elif action == "create_confirm":
            _do_create(T, ApiError, pending["title"], pending["period"], res, principal, {}, force=True)
        elif action == "create_agency_confirm":
            out = T["admin"].create_agency(pending["name"])
            res.tools_used = ["create_agency"]
            res.reply = "Created agency **{}**. You can now onboard users into it.".format(
                out.get("name", pending["name"])
            )
            res.actions = ["Created agency '{}'".format(pending["name"])]
        elif action == "assign_role_admin":
            T["admin"].assign_role(pending["user_email"], pending["role"])
            res.tools_used = ["assign_role"]
            res.reply = "Updated **{}**'s role to **{}**.".format(
                pending["user_name"], str(pending["role"]).title()
            )
            res.actions = ["Assigned role {} to {}".format(pending["role"], pending["user_name"])]
        elif action == "deactivate_user_admin":
            T["admin"].deactivate_user(pending["user_id"])
            res.tools_used = ["deactivate_user"]
            res.reply = "Deactivated **{}** — they can no longer sign in.".format(pending["user_name"])
            res.actions = ["Deactivated user {}".format(pending["user_name"])]
        elif action == "run_escalations":
            out = T["admin"].run_escalations()
            res.tools_used = ["run_escalations"]
            scanned = out.get("sheets_checked", out.get("checked", "?"))
            raised = out.get("newly_raised", out.get("escalated", "?"))
            res.reply = "Escalation sweep complete — scanned **{}** sheet(s), raised **{}** new alert(s).".format(
                scanned, raised
            )
            res.actions = ["Ran the SLA escalation sweep"]
        elif action == "logout":
            T["auth_tools"].logout()
            res.tools_used = ["logout"]
            res.reply = "You've been signed out of the assistant session."
            res.actions = ["Signed out"]
        else:
            res.reply = "That request is no longer valid — let's start over."
            res.confidence = "low"
    except ApiError as e:
        res.reply = _friendly_error(e)
        res.confidence = "low"
        if getattr(e, "status", 0) in _TRANSIENT:
            res.pending = pending  # preserve so the user can retry with "yes"
            res.reply += " Reply **yes** to try again."


def _do_create(T, ApiError, title, period, res, principal, ctx, force=False):
    """Create a draft — with a duplicate guard (Phase 5) unless the user already confirmed."""
    if not force:
        existing = [
            s for s in T["expenses"].list_my_expenses()
            if str(s.get("title", "")).strip().lower() == title.strip().lower()
            and str(s.get("period", "")) == period
            and "DRAFT" in str(s.get("status", "")).upper()
        ]
        if existing:
            res.tools_used = ["list_my_expenses"]
            res.pending = {"action": "create_confirm", "title": title, "period": period}
            res.reply = (
                f"You already have a draft **{title}** for {period}. "
                "Create another one anyway? Reply **yes** to confirm or **no** to cancel."
            )
            res.confidence = "medium"
            return
    sheet = T["expenses"].create_expense(title, period)
    res.tools_used = (res.tools_used or []) + ["create_expense"]
    res.reply = f"Created a draft **{title}** for {period}. Add line items and receipts, then submit it."
    res.actions = ["Created a draft expense sheet"]


def _skill_fallback(T, ApiError, msg, low, ctx, res, principal):
    res.confidence = "low"
    _fn, label, score = _fuzzy_route(low)
    role = str(principal.role).lower()
    if role == "admin":
        base = (
            "As admin I can: **list users**, **find a user** by name or email, **list agencies**, "
            "**create an agency**, **assign a role** to a user, **deactivate a user**, "
            "**run the escalation sweep**, check **system health**, or show the **dashboard**."
        )
    else:
        base = "I can help with expenses, approvals, receipts, policy questions, reports, and dashboards."
    hint = f" Did you mean *“{label}”*?" if label and score >= _NEARMISS_THRESHOLD else ""
    res.reply = (
        base
        + hint
        + " Try one of the suggestions below, or ask *“what do I need to do next?”*"
    )


# --- helpers ------------------------------------------------------------------------------ #
def _numbered_sheets(rows: list[dict], noun: str, kind: str) -> tuple[str, dict | None]:
    if not rows:
        return (f"No {noun}s right now. 🎉", {"last_list": [], "list_kind": kind})
    last_list, lines = [], []
    for i, s in enumerate(rows, 1):
        title = s.get("title") or "Untitled"
        who = s.get("employee_name")
        suffix = f" — {who}" if who else ""
        lines.append(f"{i}. **{title}**{suffix} · {_money(s.get('total'))} · {_status(s)}")
        last_list.append({"ref": i, "id": s.get("id"), "title": title})
    return ("\n".join(lines), {"last_list": last_list, "list_kind": kind})


def _carry(ctx: dict) -> dict | None:
    """Preserve the active list across a confirmation turn so follow-ups keep working."""
    kept = {k: ctx[k] for k in ("last_list", "list_kind") if k in ctx}
    return kept or None


def _ask_to_list(res, verb: str, list_cmd: str):
    res.reply = f"Which one should I {verb}? Say *“{list_cmd}”* first, then e.g. *“{verb} 1”* (or *“{verb} the latest”*)."
    res.confidence = "low"
    return None


def _ref_in(low: str) -> int | None:
    m = re.search(r"#?\b(\d{1,3})\b", low)
    if m:
        return int(m.group(1))
    for word, n in _ORDINALS.items():
        if re.search(rf"\b{re.escape(word)}\b", low):
            return n
    return None


def _title_match(low: str, title: str) -> bool:
    title_l = title.lower()
    for tok in re.findall(r"[a-z0-9]{3,}", low):
        if tok not in _TITLE_STOPWORDS and tok in title_l:
            return True
    return False


def _resolve_ref(low: str, ctx: dict) -> dict | None:
    """Resolve a reference against the last shown numbered list (digit / ordinal / last / title)."""
    last = ctx.get("last_list") or []
    if not last:
        return None
    ref = _ref_in(low)
    if ref is None and any(w in low for w in ("last", "latest", "most recent", "final")):
        ref = len(last)
    if ref is not None:
        return next((it for it in last if it.get("ref") == ref), None)
    return next((it for it in last if _title_match(low, it.get("title", ""))), None)


def _resolve_target(low: str, ctx: dict, fetch: Callable[[], list[dict]]) -> dict | None:
    """Resolve a target sheet — first from the last list, else by fetching the relevant list
    and matching by title / 'latest' / a single candidate."""
    hit = _resolve_ref(low, ctx)
    if hit:
        return hit
    rows = fetch() or []
    if not rows:
        return None
    for r in rows:
        if _title_match(low, r.get("title", "")):
            return {"id": r.get("id"), "title": r.get("title") or "Untitled"}
    if any(w in low for w in ("last", "latest", "most recent", "recent")):
        newest = max(rows, key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""))
        return {"id": newest.get("id"), "title": newest.get("title") or "Untitled"}
    if len(rows) == 1:
        return {"id": rows[0].get("id"), "title": rows[0].get("title") or "Untitled"}
    return None


def _affirmative(low: str) -> bool:
    s = low.strip().rstrip("!. ")
    return s in _AFFIRM or bool(re.match(r"^(yes|yeah|yep|sure|ok|okay|confirm|go ahead|do it|proceed)\b", s))


def _negative(low: str) -> bool:
    s = low.strip().rstrip("!. ")
    return s in _NEGATE or bool(re.match(r"^(no|nope|nah|cancel|never ?mind|stop|abort|don'?t|forget)\b", s))


def _extract_reason(msg: str) -> str | None:
    m = re.search(r"\b(?:because|reason|since|due to|:|-)\s+(.*)", msg, re.I)
    return m.group(1).strip().rstrip(".") if m else None


_MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}


def _extract_period(msg: str) -> str | None:
    # Numeric form first: 2026-06, 2026/06, 2026 06.
    m = re.search(r"\b(20\d{2})[-/ ](0[1-9]|1[0-2])\b", msg)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    # Natural month name + year, either order: "June 2026", "2026 Jun", "sept 2026".
    low = msg.lower()
    nm = re.search(r"\b([a-z]{3,9})\.?\s+(20\d{2})\b", low) or re.search(r"\b(20\d{2})\s+([a-z]{3,9})\b", low)
    if nm:
        a, b = nm.group(1), nm.group(2)
        name, year = (a, b) if not a.isdigit() else (b, a)
        mon = _MONTHS.get(name[:3])
        if mon and re.fullmatch(r"20\d{2}", year):
            return f"{year}-{mon:02d}"
    return None


def _strip(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()[:50]


def _money(v) -> str:
    try:
        return f"${float(v):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _status(s: dict) -> str:
    return str(s.get("status", "")).replace("_", " ").title() or "—"


def _friendly_error(e) -> str:
    status = getattr(e, "status", 0)
    msg = re.sub(r"^Request failed:\s*", "", getattr(e, "message", str(e)) or "")
    if status == 401:
        return "Your session has expired. Please sign in again."
    if status == 403:
        return "You don't have access to that — it's outside your role or agency."
    if status == 404:
        return "I couldn't find that item — it may have changed. Try listing again."
    if status == 409:
        return msg or "That conflicts with the item's current state — it may have already moved on."
    if status == 422:
        return msg or "Some details weren't valid — please check and try again."
    if status in _TRANSIENT:
        return "That didn't go through due to a temporary problem."
    return msg or "Sorry, that didn't work."


def _suggestions_for(role: str) -> list[str]:
    role = str(role or "").lower()
    if role == "manager":
        return ["Show pending approvals", "What do I need to do next?", "What's the per-meal limit?"]
    if role == "finance":
        return ["Show the finance queue", "Generate finance KPIs", "Spend by category"]
    if role == "admin":
        return ["List users", "List agencies", "Find user by name", "Assign role"]
    return ["Show my expenses", "Create a new expense sheet", "What do I need to do next?"]


def suggestions_for_screen(role: str, screen: str | None) -> list[str]:
    """Context-aware suggestions for the current screen (Phase 4)."""
    screen = str(screen or "").lower()
    if "manager" in screen:
        return ["Review pending approvals", "What do I need to do next?", "Show returned items"]
    if "finance" in screen:
        return ["Review the finance queue", "Generate finance KPIs", "Find likely duplicate expenses"]
    if "admin" in screen:
        return ["List users", "List agencies", "Find user by name", "Run escalation sweep"]
    if "employee" in screen:
        return ["Create a new expense sheet", "What do I need to do next?", "Show my expenses"]
    return _suggestions_for(role)


# Imperative verbs that should win over keyword routing (populated once skills are defined).
_LEADING_VERBS.update({
    "approve": _skill_approve, "reject": _skill_reject, "return": _skill_reject,
    "decline": _skill_reject, "submit": _skill_submit, "resubmit": _skill_resubmit,
    "withdraw": _skill_withdraw, "recall": _skill_withdraw, "create": _skill_create,
    "assign": _skill_assign_role_admin, "promote": _skill_assign_role_admin,
    "deactivate": _skill_deactivate_user_admin, "disable": _skill_deactivate_user_admin,
    "find": _skill_find_user, "lookup": _skill_find_user,
})


# --- offline fuzzy / synonym router ------------------------------------------------------- #
# Used ONLY when the exact keyword table above finds nothing. It widens recall to off-script
# phrasings and typos without an LLM: multi-word phrases match as substrings; single words match
# any message token by edit-distance ratio. Order mirrors the table — more specific intents lead,
# so e.g. "resubmit" wins over "submit" on a tie. (`label` is the human nudge for near-misses.)
_FUZZY_THRESHOLD = 0.82   # route to this intent
_NEARMISS_THRESHOLD = 0.7  # don't route, but suggest "did you mean…?"

_INTENT_VOCAB: list[tuple[Callable, str, tuple[str, ...]]] = [
    (_skill_whoami, "who am I", ("who am i", "my role", "whoami", "my profile", "my account")),
    (_skill_logout, "log out", ("log out", "logout", "sign out", "log off", "end session")),
    (_skill_next, "what do I need to do next?", (
        "what next", "what should i do", "next step", "to do", "todo", "outstanding",
        "on my plate", "left to do", "anything pending", "what's left")),
    (_skill_policy, "ask a policy question", (
        "policy", "per meal", "meal cap", "hotel cap", "limit", "allowed", "receipt rule",
        "deadline", "reimburse", "reimbursement", "rule", "claimable", "cap")),
    (_skill_cross_user, "(another user's expenses — not allowed)", (
        "someone else", "another user", "other people", "other users", "their expenses",
        "everyone", "everybody")),
    (_skill_pending, "show pending approvals", (
        "pending approvals", "to approve", "review queue", "approvals", "awaiting approval",
        "needs approval", "approval queue")),
    (_skill_finance_queue, "show the finance queue", (
        "finance queue", "manual review", "routed sheets", "finance review")),
    (_skill_spend_category, "spend by category", ("spend by category", "category spend", "by category", "categories")),
    (_skill_kpis, "show finance KPIs", ("kpi", "auto approval", "compliance rate", "interventions")),
    (_skill_dashboard, "show the dashboard", ("dashboard", "overview", "summary", "total spend", "spending")),
    (_skill_users, "list users", ("list users", "all users", "user list", "accounts", "who has access", "team members")),
    (_skill_list_agencies, "list agencies", ("list agencies", "all agencies", "agency list", "agencies", "show agencies")),
    (_skill_find_user, "find user by name or email", (
        "find user", "lookup user", "look up user", "who is", "user details", "user info",
        "has permission", "has role", "has access", "check user", "user permission")),
    (_skill_assign_role_admin, "assign a role to a user", (
        "assign role", "change role", "set role", "promote user", "make manager",
        "make admin", "grant role", "role change")),
    (_skill_deactivate_user_admin, "deactivate a user", (
        "deactivate user", "disable user", "remove user", "revoke access", "disable account")),
    (_skill_create_agency, "create an agency", ("create agency", "new agency", "add agency", "onboard agency")),
    (_skill_run_escalations, "run escalation sweep", (
        "run escalation", "escalation sweep", "sla sweep", "aging check", "escalations", "flag overdue")),
    (_skill_health, "check system health", ("system health", "health check", "services up", "everything up")),
    (_skill_activity, "show my activity", ("my activity", "my history", "audit trail", "what did i do", "recent activity")),
    (_skill_resubmit, "resubmit a sheet", ("resubmit", "submit again", "send back in")),
    (_skill_withdraw, "withdraw a sheet", ("withdraw", "recall", "pull back", "take back", "unsubmit")),
    (_skill_approve, "approve a sheet", ("approve", "accept", "sign off", "okay this")),
    (_skill_reject, "reject / return a sheet", ("reject", "return", "send back", "decline", "deny", "bounce")),
    (_skill_submit, "submit a sheet", ("submit", "send for review", "file it", "turn in")),
    (_skill_create, "create a new expense sheet", (
        "create", "new expense", "start an expense", "new sheet", "new draft", "add a sheet",
        "open a draft", "make a sheet", "begin a claim", "start a claim")),
    (_skill_my_expenses, "show my expenses", (
        "my expenses", "my sheets", "my drafts", "status of my", "my claims", "my reports")),
]


def _fuzzy_route(low: str) -> tuple[Callable | None, str | None, float]:
    """Best (skill, label, score) for a free-form message. Multi-word phrases match as
    substrings (score 1.0); single words match the closest message token by ratio. Tokens
    shorter than 3 chars are ignored so fillers like "ok"/"go" never trip a match."""
    tokens = [t for t in re.findall(r"[a-z']+", low) if len(t) >= 3]
    best: tuple[Callable | None, str | None, float] = (None, None, 0.0)
    for fn, label, vocab in _INTENT_VOCAB:
        score = 0.0
        for phrase in vocab:
            if " " in phrase:
                if phrase in low:
                    score = 1.0
                    break
            else:
                for tok in tokens:
                    r = difflib.SequenceMatcher(None, tok, phrase).ratio()
                    if r > score:
                        score = r
        if score > best[2]:
            best = (fn, label, score)
    return best

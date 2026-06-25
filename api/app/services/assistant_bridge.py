"""In-app AI Assistant bridge.

Turns a natural-language message into MCP **tool** calls — never direct backend logic. Every
business action runs through the existing `expense_mcp` tools (which forward the user's token,
so RBAC / agency-scope / SoD / audit are enforced by the API exactly as elsewhere). NL
understanding here is a transparent deterministic router + guided flows (slot-filling /
confirmation); it upgrades to an LLM by configuring Azure Foundry, without changing this contract.

Responses are business-friendly: numbered lists (no raw ids), plain-language summaries, and an
explainability footer (which MCP tools ran, what was done, what to do next).
"""

from __future__ import annotations

import re
from typing import Any, Callable

from app.principal import Principal


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
        approvals, assistant, auth_tools, dashboard, expenses, finance, system, users,
    )
    return mcp_auth, ApiError, {
        "approvals": approvals, "assistant": assistant, "auth_tools": auth_tools,
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
        # 1) Resolve a pending confirmation (human-in-the-loop) first.
        pending = ctx.get("pending")
        if pending:
            return _resolve_pending(T, ApiError, msg, low, pending, res, principal)

        # 2) Otherwise route the message to a skill.
        skill = _route(low)
        skill(T, ApiError, msg, low, ctx, res, principal)
    except ApiError as e:
        res.reply = _friendly_error(e)
        res.confidence = "low"
    res.suggestions = res.suggestions or _suggestions_for(principal.role)
    return res.as_dict()


# --- routing ------------------------------------------------------------------------------ #
def _route(low: str) -> Callable:
    table: list[tuple[tuple[str, ...], Callable]] = [
        (("who am i", "what's my role", "whoami"), _skill_whoami),
        (("policy", "per-meal", "meal cap", "hotel cap", "limit", "allowed", "receipt rule",
          "deadline", "reimburse", "reimbursement", "is this allowed", "what's the cap"), _skill_policy),
        (("pending approval", "to approve", "to review", "review queue", "approvals", "pending sheets"), _skill_pending),
        (("finance queue", "manual review", "routed sheets"), _skill_finance_queue),
        (("spend by category", "category spend", "by category"), _skill_spend_category),
        (("kpi", "auto-approval", "auto approval", "compliance rate"), _skill_kpis),
        (("dashboard", "metrics", "overview", "summary of spend", "total spend", "how much"), _skill_dashboard),
        (("list users", "users", "accounts", "who has access"), _skill_users),
        (("system health", "is the system", "health check", "are services"), _skill_health),
        (("my activity", "my history", "audit", "what did i do"), _skill_activity),
        (("approve",), _skill_approve),
        (("reject", "return"), _skill_reject),
        (("submit",), _skill_submit),
        (("create", "new expense", "start an expense", "new sheet", "new draft"), _skill_create),
        (("my expense", "my sheet", "my draft", "status of my", "my expenses"), _skill_my_expenses),
    ]
    for keys, fn in table:
        if any(k in low for k in keys):
            return fn
    return _skill_fallback


# --- read skills -------------------------------------------------------------------------- #
def _skill_whoami(T, ApiError, msg, low, ctx, res, principal):
    me = T["auth_tools"].whoami()
    res.tools_used = ["whoami"]
    res.reply = f"You're signed in as **{me.get('name')}** — {me.get('role','').title()} at {me.get('agency') or 'your agency'}."
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
    res.reply, res.context = _numbered_sheets(rows, "pending sheet")
    res.actions = [f"Listed {len(rows)} sheet(s) awaiting your review"]
    if rows:
        res.reply += "\n\nSay e.g. *“approve 1”* or *“return 1 because the receipt is missing”*."


def _skill_finance_queue(T, ApiError, msg, low, ctx, res, principal):
    rows = T["finance"].get_finance_queue()
    res.tools_used = ["get_finance_queue"]
    res.reply, res.context = _numbered_sheets(rows, "routed sheet")
    res.actions = [f"Listed {len(rows)} sheet(s) in finance manual review"]


def _skill_my_expenses(T, ApiError, msg, low, ctx, res, principal):
    rows = T["expenses"].list_my_expenses()
    res.tools_used = ["list_my_expenses"]
    res.reply, res.context = _numbered_sheets(rows, "sheet")
    res.actions = [f"Listed your {len(rows)} expense sheet(s)"]
    if rows:
        res.reply += "\n\nSay e.g. *“submit 1”* to submit a draft."


def _skill_dashboard(T, ApiError, msg, low, ctx, res, principal):
    d = T["dashboard"].get_dashboard_metrics()
    res.tools_used = ["get_dashboard_metrics"]
    total = d.get("grand_total"); comp = d.get("compliance_rate_pct")
    res.reply = (
        f"**Spend overview**\n- Total spend: **{_money(total)}**\n"
        f"- Sheets: {d.get('sheet_count', 0)} · Line items: {d.get('line_item_count', 0)}\n"
        f"- Compliance rate: {comp}%\n- At risk: {_money(d.get('total_at_risk'))} "
        f"({d.get('violation_count', 0)} flag(s))"
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
    lines = "\n".join(f"- {u.get('name')} — {str(u.get('role','')).title()}" for u in rows[:25])
    res.reply = f"**Users ({len(rows)})**\n{lines}"
    res.actions = [f"Listed {len(rows)} user(s)"]


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
        lines = "\n".join(f"- {str(r.get('action','')).replace('_', ' ').capitalize()}" for r in rows[:15])
        res.reply = f"**Your recent activity**\n{lines}"
    res.actions = ["Read your activity trail"]


# --- action skills (guided + confirmation) ------------------------------------------------ #
def _skill_approve(T, ApiError, msg, low, ctx, res, principal):
    sheet = _resolve_ref(low, ctx)
    if not sheet:
        res.reply = "Which sheet should I approve? List your queue first (*“show pending approvals”*), then say *“approve 1”*."
        res.confidence = "low"
        return
    res.pending = {"action": "approve", "id": sheet["id"], "title": sheet["title"]}
    res.context = ctx.get("last_list") and {"last_list": ctx["last_list"]} or None
    res.reply = f"Approve **{sheet['title']}**? This advances it to finance review. Reply **yes** to confirm."
    res.confidence = "medium"


def _skill_reject(T, ApiError, msg, low, ctx, res, principal):
    sheet = _resolve_ref(low, ctx)
    if not sheet:
        res.reply = "Which sheet should I return, and why? e.g. *“return 1 because the receipt is missing”*."
        res.confidence = "low"
        return
    reason = _extract_reason(msg) or "Please review and correct."
    res.pending = {"action": "return", "id": sheet["id"], "title": sheet["title"], "reason": reason}
    res.reply = f"Return **{sheet['title']}** to the employee with the note: *“{reason}”*? Reply **yes** to confirm."
    res.confidence = "medium"


def _skill_submit(T, ApiError, msg, low, ctx, res, principal):
    sheet = _resolve_ref(low, ctx)
    if not sheet:
        res.reply = "Which draft should I submit? List them (*“show my expenses”*), then say *“submit 1”*."
        res.confidence = "low"
        return
    res.pending = {"action": "submit", "id": sheet["id"], "title": sheet["title"]}
    res.reply = f"Submit **{sheet['title']}** for manager review? Reply **yes** to confirm."
    res.confidence = "medium"


def _skill_create(T, ApiError, msg, low, ctx, res, principal):
    title = ctx.get("draft_title")
    period = _extract_period(msg) or ctx.get("draft_period")
    # naive title: text after "called/titled/named"
    m = re.search(r"(?:called|titled|named)\s+[\"']?([^\"']{3,50})", msg, re.I)
    if m:
        title = m.group(1).strip()
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
    sheet = T["expenses"].create_expense(title, period)
    res.tools_used = ["create_expense"]
    res.reply = f"Created a draft **{title}** for {period}. Add line items and receipts, then submit it."
    res.actions = ["Created a draft expense sheet"]


def _resolve_pending(T, ApiError, msg, low, pending, res, principal):
    action = pending.get("action")
    # create slot-filling: the message supplies the next missing field (keep original case).
    if action == "create":
        merged = dict(pending)
        if not merged.get("title"):
            merged["title"] = _strip(msg) or "Expenses"
        elif not merged.get("period"):
            merged["period"] = _extract_period(msg) or msg.strip()
        try:
            out = _create_from(T, ApiError, merged, res)
        except ApiError as e:
            res.reply = _friendly_error(e); res.confidence = "low"
            res.suggestions = _suggestions_for(principal.role)
            return res.as_dict()
        res.suggestions = _suggestions_for(principal.role)
        return out
    # confirmation actions
    if low not in ("yes", "y", "confirm", "do it", "approve", "go ahead"):
        res.reply = "Okay, cancelled — nothing was changed."
        res.actions = ["Cancelled the pending action"]
        return res.as_dict()
    try:
        if action == "approve":
            out = T["approvals"].approve_sheet(pending["id"])
            res.tools_used = ["approve_sheet"]
            res.reply = f"Approved **{pending['title']}** — it's now in {_status(out)}."
            res.actions = [f"Approved “{pending['title']}”"]
        elif action == "return":
            # Return = request-info on the first line item (manager 'return' action).
            sheet = T["expenses"].get_expense(pending["id"])
            li = sheet["line_items"][0]["id"]
            T["approvals"].return_to_employee(pending["id"], li, pending["reason"])
            res.tools_used = ["get_expense", "return_to_employee"]
            res.reply = f"Returned **{pending['title']}** to the employee with your note."
            res.actions = [f"Returned “{pending['title']}”"]
        elif action == "submit":
            out = T["expenses"].submit_expense(pending["id"])
            res.tools_used = ["submit_expense"]
            res.reply = f"Submitted **{pending['title']}** — it's now in {_status(out)}."
            res.actions = [f"Submitted “{pending['title']}”"]
    except ApiError as e:
        res.reply = _friendly_error(e)
        res.confidence = "low"
    res.suggestions = _suggestions_for(principal.role)
    return res.as_dict()


def _create_from(T, ApiError, merged, res):
    if not merged.get("title"):
        res.needs = ["title"]; res.pending = merged; res.reply = "What should the sheet be titled?"
        return res.as_dict()
    if not merged.get("period"):
        res.needs = ["period"]; res.pending = merged; res.reply = "Which month is it for? (e.g. 2026-06)"
        return res.as_dict()
    sheet = T["expenses"].create_expense(merged["title"], merged["period"])
    res.tools_used = ["create_expense"]
    res.reply = f"Created a draft **{merged['title']}** for {merged['period']}."
    res.actions = ["Created a draft expense sheet"]
    return res.as_dict()


def _skill_fallback(T, ApiError, msg, low, ctx, res, principal):
    res.confidence = "low"
    res.reply = (
        "I can help with expenses, approvals, receipts, policy questions, reports, and dashboards. "
        "Try one of the suggestions below."
    )


# --- helpers ------------------------------------------------------------------------------ #
def _numbered_sheets(rows: list[dict], noun: str) -> tuple[str, dict | None]:
    if not rows:
        return (f"No {noun}s right now. 🎉", None)
    last_list = []
    lines = []
    for i, s in enumerate(rows, 1):
        title = s.get("title") or "Untitled"
        who = s.get("employee_name")
        amt = _money(s.get("total"))
        suffix = f" — {who}" if who else ""
        lines.append(f"{i}. **{title}**{suffix} · {amt} · {_status(s)}")
        last_list.append({"ref": i, "id": s.get("id"), "title": title})
    return ("\n".join(lines), {"last_list": last_list})


def _resolve_ref(low: str, ctx: dict) -> dict | None:
    m = re.search(r"\b(\d{1,3})\b", low)
    last = ctx.get("last_list") or []
    if m and last:
        ref = int(m.group(1))
        for item in last:
            if item.get("ref") == ref:
                return item
    return None


def _extract_reason(msg: str) -> str | None:
    m = re.search(r"\b(?:because|reason|since|due to|:)\s+(.*)", msg, re.I)
    return m.group(1).strip().rstrip(".") if m else None


def _extract_period(msg: str) -> str | None:
    m = re.search(r"\b(20\d{2})[-/ ](0[1-9]|1[0-2])\b", msg)
    return f"{m.group(1)}-{m.group(2)}" if m else None


def _strip(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()[:50]


def _money(v) -> str:
    try:
        return f"${float(v):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _status(s: dict) -> str:
    raw = str(s.get("status", "")).replace("_", " ").title()
    return raw or "—"


def _friendly_error(e) -> str:
    msg = getattr(e, "message", str(e))
    status = getattr(e, "status", 0)
    if status == 403:
        return "You don't have access to that — it's outside your role or agency."
    if status == 401:
        return "Your session has expired. Please sign in again."
    return msg


def _suggestions_for(role: str) -> list[str]:
    role = (role or "").lower()
    if role == "manager":
        return ["Show pending approvals", "What's the per-meal limit?", "Summarize the spend dashboard"]
    if role == "finance":
        return ["Show the finance queue", "Generate finance KPIs", "Spend by category"]
    if role == "admin":
        return ["List users", "System health", "Show the dashboard"]
    return ["Show my expenses", "Create a new expense sheet", "What's the receipt policy?"]


def suggestions_for_screen(role: str, screen: str | None) -> list[str]:
    """Context-aware suggestions for the current screen (Phase 4)."""
    role = (role or "").lower()
    screen = (screen or "").lower()
    if "manager" in screen:
        return ["Review pending approvals", "Flag high-value sheets to review", "Show returned items"]
    if "finance" in screen:
        return ["Review the finance queue", "Generate the monthly report", "Find likely duplicate expenses"]
    if "admin" in screen:
        return ["User summary", "System health", "Audit/activity summary"]
    if "employee" in screen:
        return ["Create a new expense sheet", "Check my approval status", "View my returned expenses"]
    return _suggestions_for(role)

# In-App AI Assistant

A conversational assistant embedded in the web app. Users interact in natural language; **every
business action is performed through the existing MCP tools** — the assistant never touches
business logic or the database directly, so RBAC, agency-scope, segregation-of-duties, and audit
are enforced by the API exactly as for any other client.

## Architecture

```
┌─────────────────┐   POST /assistant/chat   ┌──────────────────────────────┐
│  Browser widget │ ───────────────────────▶ │  API bridge (assistant_bridge)│
│ (assistant-     │   {message, context}     │  • deterministic router       │
│  widget.tsx)    │ ◀─────────────────────── │  • guided flows / confirm     │
└─────────────────┘   {reply, tools_used,    │  • sets caller token (CtxVar) │
        ▲             actions, suggestions,  └───────────────┬──────────────┘
        │             needs, pending, ctx}                   │ calls MCP tools
   host-owned memory  (context echoed back)                  ▼
   (the chat thread)                          ┌──────────────────────────────┐
                                              │  expense_mcp tools (MCP layer)│
                                              │  forward bearer token ───────▶│  FastAPI backend
                                              └──────────────────────────────┘  (RBAC/SoD/audit)
```

**Why a bridge?** MCP servers speak **stdio** and have no LLM of their own — the *host* (Claude
Desktop/Cursor) is normally the agent runtime. A browser can't speak stdio, so the API hosts a
thin bridge that drives the same MCP tool layer on the user's behalf. This keeps one source of
truth for business operations (the MCP tools) and adds no new infrastructure.

**NL engine.** A transparent, deterministic router (keyword/intent → skill) plus guided flows
(slot-filling and confirmation). It runs fully offline today and **upgrades to an LLM** by
configuring Azure Foundry — without changing the tool/security contract. It is honest about its
limits: low-confidence asks fall back to suggestions rather than guessing.

## Request / response contract

`POST /assistant/chat` → `{ message, context }`

| Field | Meaning |
|---|---|
| `reply` | business-friendly markdown answer |
| `tools_used` | the MCP tools that ran (explainability) |
| `actions` | what was done, in plain language |
| `confidence` | high / medium / low |
| `needs` | missing fields for a guided flow (slot-filling) |
| `pending` | a queued action awaiting confirmation (human-in-the-loop) |
| `context` | **opaque state** the client echoes back next turn — pending action + last numbered list. This *is* the conversation memory; the server stays stateless. |
| `suggestions` | role/screen-aware follow-ups |

`POST /assistant/suggestions` → `{ screen }` → `{ suggestions[] }` (context-aware prompts).

## Supported intents → MCP tools

| Ask (examples) | MCP tool(s) | Roles |
|---|---|---|
| "show my expenses", "status of my sheet" | `list_my_expenses` | employee |
| "create a new expense sheet" (guided) | `create_expense` | employee |
| "submit 1" (confirm) | `submit_expense` | employee |
| "show pending approvals" | `get_pending_approvals` | manager |
| "approve 1" / "return 1 because …" (confirm) | `approve_sheet` / `return_to_employee` | manager |
| "show the finance queue" | `get_finance_queue` | finance |
| "spend by category", "finance kpis" | `get_spend_by_category`, `get_finance_kpis` | finance/admin |
| "show the spend dashboard" | `get_dashboard_metrics` | manager/finance/admin |
| "what is the per-meal limit?" (cited) | `ask_policy` | any |
| "list users", "system health" | `list_users`, `server_health` | admin |
| "my activity" | `my_activity` | any |
| "who am i" | `whoami` | any |

Unrecognized asks → low confidence + suggestions (never a fabricated action).

## Role-awareness & security

- The assistant inherits the **signed-in user's token**; the API returns 403 for anything outside
  their role/agency, which the bridge surfaces as a friendly "you don't have access" message.
- **Human-in-the-loop**: consequential actions (approve / reject / return / submit / withdraw)
  always **ask for confirmation** before the MCP tool runs.
- **No internal details leak**: replies use numbered lists and plain language — no DB IDs, UUIDs,
  version numbers, or stack traces. The token is never logged or returned.
- The assistant **only acts through MCP tools** and never claims an action it didn't take.

## Memory strategy

Conversation memory is **host-owned**: the chat thread holds the multi-turn history, and the
opaque `context` blob round-trips pending actions + the last numbered list so follow-ups
("approve 1", then "yes") resolve. The server keeps **no per-session store** — nothing to leak,
nothing to scale, and the token is isolated per request via a `ContextVar`.

## Error handling

| Condition | Behavior |
|---|---|
| API 401 | "Your session has expired. Please sign in again." |
| API 403 | "You don't have access to that — it's outside your role or agency." |
| API 404 | "Not found." |
| Network/timeout | friendly message; idempotent GETs are retried by the MCP client |
| Business rule (e.g. empty sheet) | the API's plain-language reason is shown |
| Unknown intent | low-confidence reply + suggestions |

## Frontend

- `frontend/src/features/assistant/assistant-widget.tsx` — floating launcher + chat panel:
  responsive (full-screen on mobile), light/dark theme, markdown, typing indicator, suggested
  prompts, copy, 👍/👎 feedback, conversation export. Mounted globally in `PortalShell`.
- `frontend/src/data/assistant-chat.ts` — typed client over `apiPost` (auto-attaches the bearer
  token). Gated on `NEXT_PUBLIC_USE_BACKEND`.

## Deployment

1. Run the API (`uvicorn app.main:app`) — it exposes `/assistant/chat` + `/assistant/suggestions`.
2. The `expense_mcp` package must be importable by the API process (it's installed editable in the
   monorepo venv). In the API process the MCP tools call the API over `EXPENSE_API_URL`
   (default `http://localhost:8000`).
3. Frontend: set `NEXT_PUBLIC_API_BASE_URL` + `NEXT_PUBLIC_USE_BACKEND=true`; the widget appears
   on every authenticated page.
4. To enable free-form NL later, configure Azure Foundry and swap the router for the LLM planner
   behind the same bridge contract.

## Tests

- `api/tests/test_assistant_chat.py` — integration tests that drive the real MCP tools (routed
  in-process to the seeded test DB): routing, explainability, role enforcement, guided create
  slot-filling, confirmation-before-destructive-action, no-ID-leakage, screen-aware suggestions.
- `api/tests/test_assistant_reliability.py` — the stabilization suite (see report below).
- Verified end-to-end in the browser (Playwright): launcher → panel → MCP-backed replies with
  explainability and cited policy answers.

---

# Stabilization Report (Production Readiness)

## Phase 7 — Intent → MCP tool → backend mapping

The assistant is the host; the orchestration is the deterministic router (no separate "agent
prompt" is invoked server-side — the agent *prompts* are for external MCP hosts). Every action
resolves to exactly one MCP tool, which calls one backend endpoint.

| Intent (examples) | MCP tool | Backend API | Result |
|---|---|---|---|
| "who am i" | `whoami` | `GET /auth/me` | identity |
| "what do I need to do next?" | `get_pending_approvals` / `get_finance_queue` / `list_my_expenses` | role-dependent | outstanding-work summary |
| "what's the per-meal limit?" | `ask_policy` | `POST /assistant/policy` | cited answer |
| "show my expenses" | `list_my_expenses` | `GET /sheets` | numbered list |
| "create … / Berlin / 2026-06" | `create_expense` | `POST /sheets` | draft (dup-guarded) |
| "submit 2" / "submit the latest" | `submit_expense` | `POST /sheets/{id}/submit` | → manager review |
| "withdraw 1" (draft) | `withdraw_expense` | `POST /sheets/{id}/withdraw` | → withdrawn |
| "resubmit the travel sheet" | `resubmit_expense` | `POST /sheets/{id}/resubmit` | → manager review |
| "show pending approvals" | `get_pending_approvals` | `GET /manager/queue` | numbered list |
| "approve 1" (manager) | `approve_sheet` | `POST /manager/sheets/{id}/approve` | → finance review |
| "return 1 because …" | `get_expense`+`return_to_employee` | `GET /sheets/{id}` + `POST /manager/sheets/{id}/action` | → returned |
| "show the finance queue" | `get_finance_queue` | `GET /finance/queue` | numbered list |
| "approve 1" / "reject 1 because …" (finance) | `finance_decision` | `POST /finance/sheets/{id}/decision` | → approved/rejected |
| "show the dashboard" | `get_dashboard_metrics` | `GET /reports/summary` | KPIs |
| "spend by category" | `get_spend_by_category` | `GET /reports/spend-by-category` | breakdown |
| "finance kpis" | `get_finance_kpis` | `GET /finance/kpis` | KPIs |
| "list users" | `list_users` | `GET /admin/users` | directory |
| "system health" | `server_health` | `GET /healthz` | status |
| "my activity" | `my_activity` | `GET /audit/me` | trail |
| "log out" | `logout` | (clears session token) | signed out |

No business logic bypasses MCP — verified by `test_*` asserting `tools_used` for each flow.

## Phase 10 — readiness summary

**Conversation flows implemented & passing (43/43 assistant tests, 126/126 API, 50/50 MCP):**
employee create→submit, withdraw (draft), resubmit-after-return; manager view-queue→approve /
return; finance view-queue→approve / reject; admin users / dashboard / health / reports; policy
Q&A; "what next"; cross-user decline; logout.

**State-management architecture:** stateless server; the client echoes one opaque `context` blob
holding `last_list`/`list_kind` (for references) and `pending` (the action awaiting
confirmation). The per-request token is a `ContextVar`, so **concurrent users never cross state**
(test: `test_concurrent_users_do_not_cross_context`).

**Confirmation workflow (Phase 3):** summarize → ask → fuzzy yes/no → run the MCP tool → **clear
pending** → success message. Ambiguous replies **preserve** pending; an explicit new command
switches away; a transient failure **keeps** pending so "yes" retries.

**References (Phase 4/6):** number ("submit 2"), ordinal ("the second one"), "latest/last",
and title ("the Barcelona sheet") — resolved from the last list or by fetching the relevant list.

**Duplicate prevention (Phase 5):** create checks for an existing same-title+period draft and
asks to confirm; the DB enforces a unique `(employee, receipt_datetime, receipt_total)` on
receipts; state-machine transitions reject double-submit/double-approve (surfaced friendly).

**Error recovery (Phase 8):** 401/403/404/409/422/5xx/timeout map to plain-language messages;
no IDs/UUIDs/stack traces leak; transient failures retain the pending action.

**Security validation:** all actions carry the signed-in user's token; RBAC/agency/SoD/audit
enforced by the API; employee→approvals returns a friendly "no access"; cross-user requests are
declined; tokens never logged or returned.

**Known limitations (by design):** NL is deterministic keyword routing + guided flows (upgrades
to an LLM via Azure Foundry behind the same contract); adding line items / uploading receipts is
done in the sheet UI, not via chat (file handling is out of the text bridge); context lives in
the client thread (no server-side TTL — it ends with the conversation).

**Performance:** each turn is 1–2 in-process MCP→API calls; reads ~single GET, guided actions add
one list fetch for reference resolution. No N+1; idempotent GETs retried by the MCP client.

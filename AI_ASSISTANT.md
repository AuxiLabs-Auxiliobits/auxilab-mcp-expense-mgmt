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
- Verified end-to-end in the browser (Playwright): launcher → panel → MCP-backed replies with
  explainability and cited policy answers.

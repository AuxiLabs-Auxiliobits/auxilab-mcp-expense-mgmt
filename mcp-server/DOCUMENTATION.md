# Expense Management MCP Server — Build Documentation

**Package:** `expense_mcp` (`auxilab-mcp-expense-mgmt`)
**Transport:** MCP over **stdio**, on the official Python MCP SDK (FastMCP)
**Surface:** 64 tools · 8 resources + 3 templates · 16 prompts

This document describes everything built for the MCP server: what it is, how it's structured, the
full capability catalog, security/hardening, API coverage, how to run/connect/test it, and the
design decisions behind it.

---

## 1. What it is

The MCP server exposes the expense-management platform to AI hosts (Claude Desktop, Cursor, VS
Code, Windsurf, …). It is a **thin authenticated adapter over the FastAPI backend** — every
business tool forwards the signed-in user's bearer token, so the API enforces JWT validation,
RBAC, agency-scope, segregation-of-duties (SoD), and audit. The MCP server holds **no business
logic of its own** and never touches the database directly.

> **Design principle:** the AI advises and *requests* actions; the API still decides and records.
> An AI can only do what the signed-in user is allowed to do.

---

## 2. Architecture

```
AI host (Claude / Cursor / …)
        │  MCP over stdio
        ▼
expense_mcp (FastMCP)
        │  business tools attach the user's bearer token (never logged)
        │  + correlation id (X-Request-Id), pooled httpx client, bounded retry
        ▼
FastAPI backend (api/)  ──▶  DB · RBAC · agency-scope · SoD · audit · Azure
```

**Request flow for a business tool**
1. Host calls a tool (e.g. `approve_sheet(sheet_id)`).
2. The adapter resolves the per-request token (ContextVar; set by `login` or the host env).
3. It issues one HTTP call to the API with `Authorization: Bearer …` + `X-Request-Id`.
4. The API authorizes, performs, audits, and returns; the adapter maps errors to friendly text.

**Package layout** (`mcp-server/src/expense_mcp/`)
```
instance.py            # the single FastMCP app
server.py              # imports every module to register tools/resources/prompts; main()
__main__.py            # `python -m expense_mcp`
config.py              # EXPENSE_API_URL / timeout / retries / bootstrap token (fail-fast)
auth.py                # per-request bearer token (ContextVar)
client.py              # httpx wrapper: token, retry/backoff, correlation id, friendly ApiError
annotations.py         # READ / COMPUTE / WRITE / DESTRUCTIVE annotation presets
tools/                 # the 64 tools (see §4)
  engine.py            #   5 stateless analysis tools
  auth_tools.py system.py meta.py notifications.py
  expenses.py receipts.py approvals.py finance.py dashboard.py
  users.py admin.py assistant.py ai_insights.py
resources/resources.py # read-only snapshots (expense://, approvals://, dashboard://…)
prompts/prompts.py     # reusable workflow prompts
agents/                # multi-agent layer (registry, router, definitions)
```

---

## 3. Two tool layers

1. **Engine tools (5, stateless)** — the pure `expense_core` analysis tools. No DB, no auth:
   `policy_checker`, `receipt_parser`, `category_classifier`, `duplicate_detector`,
   `report_summariser`. Marked `COMPUTE` (read-only, closed-world).
2. **Business tools (authenticated)** — adapters over the API that forward the user's token.

---

## 4. Tool catalog (64)

Annotation legend — **READ**: read-only · **COMPUTE**: pure analysis · **WRITE**: state-changing,
non-destructive · **DESTRUCTIVE**: consequential/irreversible (host should confirm). Totals: **28
READ · 6 COMPUTE · 19 WRITE · 11 DESTRUCTIVE**.

### Auth & System
| Tool | Ann. | Backend |
|---|---|---|
| `login` | WRITE | `POST /auth/login` |
| `whoami` | READ | `GET /auth/me` |
| `logout` | WRITE | (clears session token) |
| `server_health` | READ | `GET /healthz` |

### Reference data & Notifications
| Tool | Ann. | Backend |
|---|---|---|
| `get_value_sets` | READ | `GET /meta/value-sets` |
| `get_periods` | READ | `GET /meta/periods` |
| `list_notifications` | READ | `GET /notifications` |
| `mark_notifications_read` | WRITE | `POST /notifications/read` |

### Expenses (employee workflow)
| Tool | Ann. | Backend |
|---|---|---|
| `list_my_expenses` | READ | `GET /sheets` |
| `get_expense` | READ | `GET /sheets/{id}` |
| `search_expenses` | READ | `GET /sheets` (filtered) |
| `get_decisions` | READ | `GET /sheets/{id}/decisions` |
| `create_expense` | WRITE | `POST /sheets` |
| `add_line_item` | WRITE | `POST /sheets/{id}/line-items` |
| `update_expense` | WRITE | `PATCH /sheets/{id}` |
| `update_line_item` | WRITE | `PATCH /sheets/{id}/line-items/{li}` |
| `submit_expense` | WRITE | `POST /sheets/{id}/submit` |
| `resubmit_expense` | WRITE | `POST /sheets/{id}/resubmit` |
| `remove_line_item` | DESTRUCTIVE | `DELETE /sheets/{id}/line-items/{li}` |
| `discard_draft` | DESTRUCTIVE | `DELETE /sheets/{id}` |
| `withdraw_expense` | DESTRUCTIVE | `POST /sheets/{id}/withdraw` |

### Receipts
| Tool | Ann. | Backend |
|---|---|---|
| `list_receipts` | READ | `GET /sheets/{id}/receipts` |
| `get_receipt_details` | READ | `GET /attachments/{id}` |
| `upload_receipt` | WRITE | `POST /sheets/{id}/line-items/{li}/receipt` |
| `download_receipt` | WRITE | `GET /attachments/{id}/content` |

### Manager
| Tool | Ann. | Backend |
|---|---|---|
| `get_pending_approvals` | READ | `GET /manager/queue` |
| `approve_line_item` | DESTRUCTIVE | `POST /manager/sheets/{id}/action` |
| `reject_line_item` | DESTRUCTIVE | `POST /manager/sheets/{id}/action` |
| `return_to_employee` | DESTRUCTIVE | `POST /manager/sheets/{id}/action` |
| `approve_sheet` | DESTRUCTIVE | `POST /manager/sheets/{id}/approve` |

### Finance
| Tool | Ann. | Backend |
|---|---|---|
| `get_finance_queue` | READ | `GET /finance/queue` |
| `list_all_expenses` | READ | `GET /finance/sheets` |
| `get_finance_kpis` | READ | `GET /finance/kpis` |
| `get_finance_audit` | READ | `GET /finance/audit` |
| `list_agency_policies` | READ | `GET /finance/policies/{agency}` |
| `finance_decision` | DESTRUCTIVE | `POST /finance/sheets/{id}/decision` |
| `finance_override` | DESTRUCTIVE | `POST /finance/sheets/{id}/override` |
| `upload_agency_policy` | WRITE | `POST /finance/policies/{agency}` |
| `publish_agency_policy` | WRITE | `POST /finance/policies/{agency}/{id}/publish` |

### Dashboard / Reports
| Tool | Ann. | Backend |
|---|---|---|
| `get_dashboard_metrics` | READ | `GET /reports/summary` |
| `get_spend_by_category` | READ | `GET /reports/spend-by-category` |

### Admin (agencies & users)
| Tool | Ann. | Backend |
|---|---|---|
| `list_agencies` | READ | `GET /admin/agencies` |
| `get_agency` | READ | `GET /admin/agencies/{id}` |
| `list_users` | READ | `GET /admin/users` |
| `get_user` | READ | `GET /admin/users/{id}` |
| `create_agency` | WRITE | `POST /admin/agencies` |
| `update_agency` | WRITE | `PATCH /admin/agencies/{id}` |
| `create_user` | WRITE | `POST /admin/users` |
| `update_user` | WRITE | `PATCH /admin/users/{id}` |
| `assign_role` | WRITE | `POST /admin/users/assign-role` |
| `delete_agency` | DESTRUCTIVE | `DELETE /admin/agencies/{id}` |
| `deactivate_user` | DESTRUCTIVE | `DELETE /admin/users/{id}` |

### Audit & Policy
| Tool | Ann. | Backend |
|---|---|---|
| `my_activity` | READ | `GET /audit/me` |
| `ask_policy` | READ | `POST /assistant/policy` (agency RAG) |

### AI insights (advisory agentic layer)
| Tool | Ann. | Backend |
|---|---|---|
| `get_ai_recommendation` | COMPUTE | `GET /ai/sheets/{id}/recommendation` |
| `get_ai_workspace` | READ | `GET /ai/workspace` |
| `get_ai_analytics` | READ | `GET /ai/analytics` |
| `submit_ai_feedback` | WRITE | `POST /ai/recommendations/{id}/feedback` |

### Engine (stateless analysis) & routing
| Tool | Ann. |
|---|---|
| `policy_checker`, `receipt_parser`, `category_classifier`, `duplicate_detector`, `report_summariser` | COMPUTE |
| `recommend_agent` | READ |

Every tool validates inputs against a typed schema, logs the call (token never logged), and
surfaces a **friendly error** (never a stack trace). Authorization is delegated to the API — a
tool the user can't perform returns a clear "you don't have permission" message.

---

## 5. Human-in-the-loop (tool annotations)

The **11 DESTRUCTIVE** tools carry `destructiveHint`, so MCP hosts prompt the user to **confirm**
before an AI runs them: `approve_line_item`, `approve_sheet`, `reject_line_item`,
`return_to_employee`, `finance_decision`, `finance_override`, `withdraw_expense`, `discard_draft`,
`remove_line_item`, `delete_agency`, `deactivate_user`. Read-only tools are marked `readOnlyHint`
so hosts can run them freely.

---

## 6. Resources (8 + 3 templates)

Read-only, role-scoped snapshots the host can subscribe to / read:

`me://profile` · `expense://mine` · `approvals://pending` · `finance://queue` ·
`dashboard://summary` · `users://directory` · `activity://mine` · `agents://catalog`

Templates: `expense://{sheet_id}` · `expense://{sheet_id}/receipts` · `expense://{sheet_id}/history`

---

## 7. Prompts (16)

**Workflow prompts (8)** — each tells the AI which tools/resources to use so answers stay grounded:
`summarize_expense`, `explain_rejection`, `approval_summary`, `finance_report`,
`list_pending_approvals`, `find_duplicate_expenses`, `audit_report`, `suggest_policy_violations`.

**Multi-agent layer (8)** — see §8: `employee_agent`, `manager_agent`, `finance_agent`,
`admin_agent`, `policy_agent`, `audit_agent`, `reporting_agent`, `orchestrator`.

---

## 8. Multi-agent layer

In MCP, the **host is the agent runtime**, so agents are realized as **MCP prompts** the host's
LLM enacts using the tools above — no second LLM, no duplicated logic.

- **7 domain agents** — each prompt defines a role, its allowed tools, a workflow, security
  guardrails, and an explainability footer (actions · tools used · data sources · rationale ·
  confidence · next steps).
- **`orchestrator`** prompt routes intent and coordinates multi-agent work.
- **`recommend_agent`** tool — a deterministic intent → agent router returning
  `{agent, confidence, rationale, suggested_tools}`.
- **`agents://catalog`** resource — the agent roster + each agent's tools (for discovery).

The agent registry is the single source of truth; a test asserts every agent only references
**real, registered** tools (no phantom capabilities).

---

## 9. Security & hardening

- **Token safety** — forwarded to the API, **never logged** (logs are `cid=… METHOD path -> status`)
  and never returned by any tool. Resolved per request via a `ContextVar`, so the server can serve
  concurrent users without cross-talk.
- **Authorization delegated** — all RBAC / agency-scope / SoD / audit enforced by the API. 401 →
  "session expired"; 403 → "you don't have permission".
- **Resilience** — one pooled keep-alive `httpx` client; bounded **retry with backoff** on
  transient failures (connect errors / timeouts / 502-503-504) for **idempotent GETs only** —
  writes are never silently repeated.
- **Traceability** — every call carries a correlation id (`X-Request-Id`).
- **Fail-fast config** — bad `EXPENSE_API_URL` / non-positive timeout raise a clear error at start.
- **Health/readiness** — `server_health` reports version, configured API URL, auth state, backend
  reachability. Graceful shutdown closes the pooled client.

---

## 10. Full API coverage

The server covers **the entire user-facing backend API**: **54 / 60 endpoints** have tools. The
**6 excluded** are machine/UI/worker endpoints, intentionally not exposed as host tools:

| Excluded endpoint | Why |
|---|---|
| `POST /auth/token` | OAuth2 form sibling of `/auth/login` (covered by `login`) |
| `POST /assistant/chat` | the in-app web assistant (UI), not an MCP host tool |
| `POST /assistant/suggestions` | the in-app web assistant (UI) |
| `POST /finance/sheets/{id}/llm-decision` | AI-approver worker webhook (agent service principal) |
| `POST /finance/policies/{id}/indexed` | worker indexing callback |
| `GET /sheets/{id}/line-items/{li}/receipts` | redundant with sheet-level `list_receipts` |

A test (`tests/test_full_api_coverage.py`) asserts each new tool hits the correct `(method, path)`.

---

## 11. Configuration

Copy `.env.example` → `.env` (or set in the host config):

| Var | Purpose | Default |
|---|---|---|
| `EXPENSE_API_URL` | FastAPI backend base URL | `http://localhost:8000` |
| `EXPENSE_API_TOKEN` | bootstrap bearer (else use the `login` tool) | — |
| `EXPENSE_API_TIMEOUT` | per-request timeout (s) | `30` |
| `EXPENSE_API_MAX_RETRIES` | retries for transient failures (idempotent GETs) | `2` |

---

## 12. Running

```bash
python -m expense_mcp            # module entry point
auxilab-mcp-expense-mgmt         # installed console script
```
It speaks MCP over stdio, so it's normally launched **by** an MCP host, not run standalone.

---

## 13. Connecting a host

**Claude Desktop** — `%APPDATA%\Claude\claude_desktop_config.json` (see
`claude_desktop_config.example.json`):
```json
{
  "mcpServers": {
    "expense-mgmt": {
      "command": "<abs path>/.venv/Scripts/python.exe",
      "args": ["-m", "expense_mcp"],
      "env": { "EXPENSE_API_URL": "http://localhost:8000", "EXPENSE_API_TOKEN": "<JWT>" }
    }
  }
}
```
Omit `EXPENSE_API_TOKEN` and just tell the host *"log in as finance@demo.local"* — the `login`
tool holds the session token (avoids 8h expiry).

**MCP Inspector** (testing):
```bash
# interactive web UI
npx @modelcontextprotocol/inspector python -m expense_mcp
# non-interactive CLI
EXPENSE_API_URL=http://localhost:8000 EXPENSE_API_TOKEN=<JWT> \
  npx @modelcontextprotocol/inspector --cli python -m expense_mcp --method tools/list
```

> The backend API must be running for business tools to work.

---

## 14. Testing

**75 tests passing** (`cd mcp-server && pytest`):
- `test_tools.py`, `test_business_tools.py` — engine contracts + mocked-backend business tools.
- `test_hardening.py` — config validation, retry/no-retry, correlation id + token-not-logged,
  receipts up/down, health.
- `test_coverage.py` — all tools/resources/prompts + client error paths (~91% coverage).
- `test_agents.py` — agent registry integrity, routing, prompt contracts, catalog JSON.
- `test_full_api_coverage.py` — every new tool registered + hits the correct `(method, path)`.

Verified live with **MCP Inspector** against the running API: `tools/list` (64), `prompts/list`
(16), `resources/list` (8), and `tools/call` for reads + a `create_agency` write round-trip.

---

## 15. Build history (what was delivered)

1. **Business tools** over the API (auth, expenses, receipts, manager, finance, dashboard, users,
   policy) — thin adapters, zero duplicated logic.
2. **Enterprise hardening** — tool annotations, pooled client + retry, correlation ids, fail-fast
   config, `server_health`, token-safety; ~91% test coverage.
3. **Multi-agent layer** — 7 domain-agent prompts + orchestrator + `recommend_agent` +
   `agents://catalog`, generated from a single registry.
4. **Full API coverage** — +25 tools (admin agencies/users, meta, notifications, finance audit +
   policy docs, line-item edits, AI insights) → 64 tools; verified with MCP Inspector.
5. **Host integration** — `claude_desktop_config.example.json` + Inspector how-to.

---

## 16. Deliberate exclusions / deferred

- **No LLM in the server** — the "intelligence" lives in the MCP host's model; the server provides
  tools/resources/prompts. (The web app's in-app assistant and the agentic recommendation engine
  are separate systems in `api/`, because a browser can't speak stdio to this server.)
- **OAuth 2.1 / token refresh** belong at the API/IdP (Entra cutover), not in a stdio adapter.
- **Rate limiting / OpenTelemetry / circuit breaker / streaming** — out of scope for a
  single-client stdio adapter; correlation-id logging + bounded retry cover the practical need.

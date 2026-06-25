# auxilab-mcp-expense-mgmt (`expense_mcp`)

The **MCP server** for the expense-management platform — exposes the application to AI
assistants (Claude Desktop, Cursor, VS Code, Windsurf, …) over the official Python
[MCP SDK](https://pypi.org/project/mcp/) (FastMCP), speaking MCP over **stdio**.

It has **two tool layers**:

1. **Engine tools (stateless)** — the five `expense_core` analysis tools. No DB, no auth.
2. **Business tools (stateful)** — authenticated adapters over the FastAPI backend. Each call
   forwards the user's **bearer token**, so the API enforces **JWT validation, RBAC,
   agency-scope, segregation-of-duties, and audit**. The MCP server adds **no business logic**
   of its own (it never touches the database directly).

> Design principle: the AI advises and *requests* actions; the API still decides and records.
> An AI can only do what the signed-in user is allowed to do.

## Architecture

```
AI host (Claude/Cursor/…)  ──stdio──▶  expense_mcp (FastMCP)
                                          │  business tools forward the bearer token
                                          ▼
                                   FastAPI backend (api/)  ──▶  DB / RBAC / audit / Azure
```

```
src/expense_mcp/
├── instance.py        # the single FastMCP app
├── config.py          # EXPENSE_API_URL / timeout / bootstrap token
├── auth.py            # per-session bearer token (login tool or env)
├── client.py          # httpx wrapper: attaches token, friendly ApiError, logging
├── tools/
│   ├── engine.py      # 5 stateless engine tools
│   ├── auth_tools.py  # login · whoami · logout
│   ├── expenses.py    # list/get/create/update/submit/resubmit/withdraw/search + add_line_item
│   ├── receipts.py    # list/details/upload/download
│   ├── approvals.py   # pending · approve/reject/return · approve_sheet
│   ├── finance.py     # queue · decision · override · list_all
│   ├── dashboard.py   # metrics · spend-by-category · finance KPIs
│   ├── users.py       # list/get users (admin) · my_activity
│   └── assistant.py   # ask_policy (agency RAG)
├── resources/resources.py   # read-only snapshots (expense://, approvals://, dashboard://…)
├── prompts/prompts.py       # reusable workflows (summaries, reports, audits)
└── server.py          # imports modules to register, exposes main()
```

## Tools (64)

The business tools cover **the entire backend API** (every user-facing endpoint has a tool —
machine/UI/worker endpoints like the OAuth2 form login, the in-app web-assistant routes, and the
AI-approver webhook are intentionally excluded).

**System:** `server_health` · **Meta:** `get_value_sets`, `get_periods` ·
**Notifications:** `list_notifications`, `mark_notifications_read` ·

**Auth:** `login`, `whoami`, `logout` · **Expenses:** `list_my_expenses`, `get_expense`,
`create_expense`, `add_line_item`, `update_expense`, `submit_expense`, `resubmit_expense`,
`withdraw_expense`, `search_expenses`, `update_line_item`, `remove_line_item`, `discard_draft`,
`get_decisions` · **Receipts:** `list_receipts`, `get_receipt_details`,
`upload_receipt`, `download_receipt` · **Manager:** `get_pending_approvals`,
`approve_line_item`, `reject_line_item`, `return_to_employee`, `approve_sheet` ·
**Finance:** `get_finance_queue`, `list_all_expenses`, `finance_decision`, `finance_override`,
`get_finance_audit`, `list_agency_policies`, `upload_agency_policy`, `publish_agency_policy` ·
**Dashboard:** `get_dashboard_metrics`, `get_spend_by_category`, `get_finance_kpis` ·
**Admin:** `list_agencies`, `get_agency`, `create_agency`, `update_agency`, `delete_agency`,
`create_user`, `update_user`, `deactivate_user`, `assign_role` ·
**Users/Audit:** `list_users`, `get_user`, `my_activity` · **Policy:** `ask_policy` ·
**AI insights:** `get_ai_recommendation`, `get_ai_workspace`, `get_ai_analytics`, `submit_ai_feedback` ·
**Engine:** `policy_checker`, `receipt_parser`, `category_classifier`, `duplicate_detector`,
`report_summariser` · plus the agent router `recommend_agent`.

Every tool validates inputs (typed schema), logs the call, and surfaces a **friendly error**
(never a stack trace). Authorization is delegated to the API — a tool the user can't perform
returns a clear "you don't have permission" message.

### Verify with MCP Inspector

```bash
# from mcp-server/ — list everything, then call a tool against the running API
EXPENSE_API_URL=http://localhost:8000 EXPENSE_API_TOKEN=<JWT> \
  npx @modelcontextprotocol/inspector --cli python -m expense_mcp --method tools/list
EXPENSE_API_URL=http://localhost:8000 EXPENSE_API_TOKEN=<JWT> \
  npx @modelcontextprotocol/inspector --cli python -m expense_mcp \
  --method tools/call --tool-name get_value_sets
```

Drop `--cli` to open the interactive Inspector web UI instead.

## Resources

`me://profile` · `expense://mine` · `expense://{sheet_id}` · `expense://{sheet_id}/receipts` ·
`expense://{sheet_id}/history` · `approvals://pending` · `finance://queue` ·
`dashboard://summary` · `users://directory` · `activity://mine` — all role-scoped by the API.

## Prompts

`summarize_expense` · `explain_rejection` · `approval_summary` · `finance_report` ·
`list_pending_approvals` · `find_duplicate_expenses` · `audit_report` ·
`suggest_policy_violations` — each tells the AI which tools/resources to use so answers stay
grounded in real data.

## AI Agents (multi-agent layer)

In MCP, **the host is the agent runtime** — Claude Desktop / Cursor / ChatGPT do the LLM
reasoning and tool selection. So the agents here are **MCP prompts** (role + allowed tools +
workflow + guardrails) the host enacts using the tools above. No second LLM, no new
infrastructure, and **no duplicated business logic** — every action still flows through the
tools (RBAC/audit enforced by the API).

**7 domain agents + orchestrator** (registered as prompts; `agents://catalog` lists the roster):

| Agent | Does | Key tools |
|---|---|---|
| `employee_agent` | create/submit/track own expenses | create_expense, add_line_item, upload_receipt, submit/resubmit/withdraw |
| `manager_agent` | review/approve/reject/return | get_pending_approvals, list_receipts, approve/reject/return, approve_sheet |
| `finance_agent` | resolve routed sheets, KPIs | get_finance_queue, finance_decision/override, get_finance_kpis |
| `admin_agent` | users, dashboards, health | list_users, get_user, server_health, get_dashboard_metrics |
| `policy_agent` | policy Q&A + compliance | ask_policy, policy_checker, get_expense |
| `audit_agent` | history + unusual activity | expense://{id}/history, my_activity, duplicate_detector |
| `reporting_agent` | spend analytics + KPI reports | get_dashboard_metrics, get_spend_by_category, report_summariser |

- **Orchestrator** prompt routes intent and coordinates multi-agent work; the deterministic
  **`recommend_agent`** tool returns `{agent, confidence, rationale, suggested_tools}` for transparent routing.
- **Explainability**: every agent reply ends with *Actions taken · Tools used · Data sources ·
  Rationale · Confidence · Next steps*.
- **Memory** is **host-owned** (the chat thread is the multi-turn memory; prompts instruct the
  model to track pending actions and ask for clarification). The server stays stateless — no
  per-user store to leak or scale.
- **Human-in-the-loop**: the 7 destructive tools carry `destructiveHint`, so the host confirms
  before an agent approves/rejects/returns/withdraws.

### Use the agents from a client
Prompts appear as slash-commands / "prompt" entries in the host. In Claude Desktop, pick the
server's **`manager_agent`** prompt then say *“review my pending approvals”*; or start with
**`orchestrator`** and let it route. Cursor/VS Code/Windsurf expose the same prompts + tools.

## Install

From the monorepo root (the package depends on the sibling `expense-core`):

```bash
pip install -e ./core-engine
pip install -e ./mcp-server[dev]        # add [azure] for real Foundry on the engine tools
```

## Configure

Copy `.env.example` → `.env` (or set in the MCP host config):

| Var | Purpose | Default |
|---|---|---|
| `EXPENSE_API_URL` | FastAPI backend base URL | `http://localhost:8000` |
| `EXPENSE_API_TOKEN` | bootstrap bearer (else use the `login` tool) | — |
| `EXPENSE_API_TIMEOUT` | per-request timeout (s) | `30` |
| `EXPENSE_API_MAX_RETRIES` | retries for transient failures (idempotent GETs only) | `2` |

Config is **validated at startup** (bad URL / non-positive timeout fail fast with a clear message).

## Run (stdio)

```bash
auxilab-mcp-expense-mgmt        # console script
python -m expense_mcp           # module entry point
```

## Connect an AI host (Claude Desktop / Cursor / VS Code)

`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "expense-mgmt": {
      "command": "python",
      "args": ["-m", "expense_mcp"],
      "env": {
        "EXPENSE_API_URL": "http://localhost:8000",
        "EXPENSE_API_TOKEN": "<a JWT from POST /auth/login>"
      }
    }
  }
}
```

Without `EXPENSE_API_TOKEN`, ask the assistant to **“log in as finance@demo.local”** — it
calls the `login` tool and the session token is held in memory for subsequent calls.

### Example agent asks
- “Show my pending approvals and which look risky.” → `get_pending_approvals`
- “Approve sheet SH-… ” → `approve_sheet` (API enforces agency + SoD)
- “What’s the per-meal limit?” → `ask_policy` (cited)
- “Generate a finance report for 2026-06.” → `finance_report` prompt → dashboard tools

## Security & hardening
- **Tool annotations**: read-only tools are marked `readOnlyHint`; consequential actions
  (`approve_*`, `reject_*`, `return_to_employee`, `withdraw_expense`, `finance_decision`,
  `finance_override`) are `destructiveHint` so MCP clients **prompt for confirmation** before an
  AI runs them.
- **Token safety**: forwarded to the API, **never logged** (logs are `cid=… METHOD path -> status`)
  and never returned by any tool (incl. `server_health`).
- All RBAC / agency-scope / SoD / audit enforced by the API; 401→re-auth, 403→permission message.
- **Resilience**: one pooled keep-alive `httpx` client; bounded **retry with backoff** on transient
  failures (connect errors / timeouts / 502-503-504) for **idempotent GETs only** — writes are
  never silently repeated. Each call carries a **correlation id** (`X-Request-Id`) for tracing.
- Inputs validated by typed schemas; backend re-validates (defense in depth).
- **Health/readiness:** the `server_health` tool reports version, configured API URL, auth state,
  and backend reachability. Graceful shutdown closes the pooled client.
- Rate limiting and OAuth 2.1 / token refresh belong at the API/IdP (Entra cutover, ADR-001),
  not in this single-client stdio adapter.

## Test

```bash
cd mcp-server && pytest        # 17 tests: engine contracts + mocked-backend business tools
```

## Deployment
- **Dev:** run the backend (`uvicorn app.main:app`), then the MCP server via the host config above.
- **Prod:** distribute the wheel; the host launches `python -m expense_mcp` with
  `EXPENSE_API_URL` pointed at the deployed API and a per-user token (or SSO-minted JWT). The
  server is stdio + stateless aside from the in-memory session token, so it scales per host
  process; restart-safe (no local state to lose). Health = process up + a `whoami` call.

## Troubleshooting
- *“Not authenticated …”* → set `EXPENSE_API_TOKEN` or call `login`.
- *“Could not reach the Expense API …”* → check `EXPENSE_API_URL` / that the API is running.
- *“You don't have permission …”* → the signed-in user's role lacks that action (expected).

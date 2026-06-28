# Expense Management Platform

> **AI-powered expense compliance system with MCP integration, multi-role approval workflow, and agency-scoped policy enforcement.**

## What It Does

Enterprise expense approval is slow, inconsistent, and compliance-risky. Reviewers hunt for receipts, finance teams catch policy violations after the fact, and approval queues pile up with no intelligent routing.

This platform solves that with:

- **Deterministic compliance engine** — 5 pure-Python tools that check policy, parse receipts, classify spending categories, detect duplicates, and summarise reports. No LLM required for core decisions; math decides, LLM advises.
- **Multi-stage approval workflow** — Employee → Manager → AI Finance Approver → Finance Human review. Every state transition is audited and immutable.
- **Model Context Protocol (MCP) server** — 60+ tools exposing the full API surface to any MCP-compatible AI agent. Ask Claude Desktop "show my pending expense sheets" and it reads your live data.
- **Agency-scoped RBAC** — 5 roles (Employee, Manager, Finance, Admin, LLM Approver). Managers see only their own agency. Finance cannot override their own submissions.
- **In-app AI assistant** — natural language chat routed deterministically to API calls. Every response cites the rule it applied; no hallucination.
- **Pluggable backend** — runs fully offline (SQLite + local provider) or on Azure (PostgreSQL + Foundry + Document Intelligence + AI Search).

## Monorepo Layout

```
.
├── core-engine/    # Pure Python — the 5 tools, schemas, baseline policy, LLM gateway
├── mcp-server/     # MCP SDK wrapper → auxilab-mcp-expense-mgmt (60+ tools)
├── api/            # FastAPI + RBAC + workflow state machine + immutable audit log
├── workers/        # LangGraph LLM finance approver + Service Bus consumers + agency RAG
├── frontend/       # Next.js 15 — 4 role-scoped portals (Employee/Manager/Finance/Admin)
├── infra/          # Bicep IaC — Azure Container Apps, one-command deploy
├── demo.py         # Offline demo — runs all 5 engine tools with synthetic inputs
└── SCOPING.md      # Full product spec and architecture decision records
```

## Build Stages

| Stage | Deliverable | Status |
|---|---|---|
| S0 | Core engine (5 tools) + schemas + baseline policy + LLM gateway | ✅ Complete |
| S1 | MCP server — `auxilab-mcp-expense-mgmt` (60+ tools, 7 agent prompts) | ✅ Complete |
| S2 | FastAPI + RBAC + agency-scoped workflow + audit log | ✅ Complete |
| S3 | LangGraph finance approver + agency RAG + Azure guardrails | 🟡 Scaffolded (offline-runnable) |
| S4 | Next.js portal — 4 role UIs | 🟡 Reference scaffold |
| S5 | Hardening (VNet/PE, WAF/APIM, observability, DR) | ⬜ Optional flags |

> The entire backend runs locally **with zero Azure** — SQLite + local LLM provider. Azure is opt-in.

---

## Installation

**Requirements:** Python 3.12+, Node.js 18+ (frontend only)

### 1 — Install packages

```bash
git clone https://github.com/Parteek-git2813/expense-management-mcp-server.git
cd expense-management-mcp-server

# Core engine (the 5 tools — no web framework)
pip install -e ./core-engine[dev]

# API
pip install -e ./api[dev]

# MCP server
pip install -e ./mcp-server[dev]
```

### 2 — Configure the API

```bash
cd api
cp .env.example .env
# Default .env: SQLite, seeded demo data, console email — no Azure needed
```

### 3 — Start the backend

```bash
# Run from the repo root so uvicorn finds the seeded expense.db
uvicorn api.app.main:app --reload --app-dir .
# → http://localhost:8000/docs
```

Or use the Makefile shortcut:

```bash
make api
```

### 4 — Start the frontend (optional)

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
# → http://localhost:3000
```

### Demo credentials (password: `demo`)

| Email | Role | Portal |
|---|---|---|
| employee@demo.local | Employee | `/employee` |
| manager@demo.local | Manager | `/manager` |
| finance@demo.local | Finance | `/finance` |
| admin@demo.local | Admin | `/admin` |
| employee.skdk@demo.local | Employee (SKDK agency) | `/employee` |
| manager.skdk@demo.local | Manager (SKDK agency) | `/manager` |

---

## Usage Examples

### Run the offline demo script

No server needed. Demonstrates all 5 engine tools with synthetic inputs.

```bash
python demo.py
```

**Sample output:**

```
--------------------------------------------------------------
  Expense Management Platform -- Core Engine Demo
  (offline mode: no Azure, no LLM credentials needed)
--------------------------------------------------------------

--------------------------------------------------------------
  1. Policy Checker  (deterministic -- zero LLM)
--------------------------------------------------------------
  [PASS]  Valid client lunch $45.00, receipt matches
  [FAIL]  Prohibited category (Client Entertainment blocked by policy)
           Reason: Category 'Client Entertainment' is prohibited [PROHIBITED_CATEGORY]
  [FAIL]  Amount mismatch: entered $50.00, receipt says $47.50
           Reason: Entered amount does not match parsed receipt total [AMOUNT_MISMATCH]
  [FAIL]  Future-dated expense (date: 2025-01-01, today: 2024-06-15)
           Reason: Expense date is in the future [FUTURE_DATE]

--------------------------------------------------------------
  2. Receipt Parser  (regex offline fallback)
--------------------------------------------------------------
  Merchant   : NOODLE HOUSE
  Total      : $45.00
  Tax        : $8.625
  Reconciles : [PASS]  (sum of items + tax == total, delta=$0)
  Line items :
    * Receipt total less tax          $36.375

  Note: detailed line-item extraction requires Azure Document Intelligence.
  The offline regex extracts totals only.

--------------------------------------------------------------
  3. Category Classifier  (keyword fallback, no LLM needed)
--------------------------------------------------------------
  [PASS]  Team lunch at Noodle House                -> Meals & Entertainment  (94%)
  [PASS]  GitHub Copilot annual subscription        -> Software / Subscriptions  (94%)
  [PASS]  Delta Airlines JFK to LAX                 -> Travel - Air  (94%)
  [PASS]  Parking at SFO airport                    -> Travel - Ground  (94%)
  [PASS]  Marriott NYC -- 2 nights                  -> Travel - Hotel  (94%)
  [FAIL]  Unknown widget from AcmeCo                -> Other  (40%)

--------------------------------------------------------------
  4. Duplicate Detector  (deterministic -- zero LLM)
--------------------------------------------------------------
  First submission    risk=none    [PASS]
  Resubmit same rcpt  risk=high    [PASS] DUPLICATE DETECTED
           Reason: EXACT_KEY match on (employee, receipt_datetime, total)
  Different amount    risk=none    [PASS]

--------------------------------------------------------------
  5. Report Summariser  (deterministic aggregation + templated narrative)
--------------------------------------------------------------
  Total spend        : $416.38
  Line items         : 4
  Violations flagged : 1  ($28.50 at risk)
  Compliance rate    : 75.0%
  Top category       : Travel - Air  ($320.00)
  Narrative          : Reviewed 4 line item(s) totalling 416.38. Highest spend
                       category: Travel - Air. 1 item(s) flagged (28.50 at risk);
                       compliance rate 75.0%.
```

### Submit an expense via REST API

```bash
# 1. Get a token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -d "username=employee@demo.local&password=demo" | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Create a draft expense sheet
SHEET=$(curl -s -X POST http://localhost:8000/sheets \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"June client lunch","expense_period":"2024-06"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 3. Add a line item
curl -s -X POST "http://localhost:8000/sheets/$SHEET/line-items" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "merchant": "Noodle House",
    "description": "Team lunch — project kickoff",
    "amount": 45.00,
    "expense_date": "2024-06-01"
  }'

# 4. Submit for approval
curl -s -X POST "http://localhost:8000/sheets/$SHEET/submit" \
  -H "Authorization: Bearer $TOKEN"
```

### Connect to MCP in Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "expense-mgmt": {
      "command": "python",
      "args": ["-m", "expense_mcp"],
      "env": {
        "EXPENSE_API_URL": "http://localhost:8000",
        "EXPENSE_API_TOKEN": "paste-your-jwt-here"
      }
    }
  }
}
```

Then ask Claude: *"Show me my pending expense sheets"*, *"Is a $45 lunch at Noodle House policy-compliant?"*, or *"List all users in the system"* (admin token).

---

## Running Tests

```bash
# Core engine — offline, zero dependencies, no Azure
cd core-engine && pytest

# API integration tests (uses SQLite in-memory)
cd api && pytest

# MCP server contract tests
cd mcp-server && pytest

# Run all from repo root
make test
```

The test suite covers policy boundary checks, agency-scoped RBAC, full submit → approve → finance workflow, LLM finance approver decisions, duplicate detection, and MCP tool contracts.

---

## Architecture

```
┌──────────────────────────┐     ┌───────────────────────────┐
│   Next.js 15 Portal      │────▶│   FastAPI  (RBAC + audit) │
│   4 Role-Scoped UIs      │     │   + Workflow state machine  │
└──────────────────────────┘     └────────────┬──────────────┘
         │                                    │
         │  (in-app NL chat)                  │
┌──────────────────────────┐     ┌────────────▼──────────────┐
│  Assistant Bridge        │     │   Core Engine             │
│  NL → deterministic      │     │   5 pure-Python tools     │
│  API routing (no LLM)    │     │   (policy/receipt/cat/    │
└──────────────────────────┘     │    dup/report)            │
                                 └───────────────────────────┘
┌──────────────────────────┐
│  MCP Server              │     Key principle:
│  60+ tools               │     LLM advises.
│  7 agent prompts         │     Deterministic code decides.
│  (Claude Desktop / API)  │
└──────────────────────────┘
```

**Security:** RBAC enforced at API layer (never trust the client). Segregation of duties — managers cannot approve their own submissions. Finance cannot override their own sheets. All actions written to an immutable audit log.

---

## Known Limitations

1. **LLM finance approver is scaffolded** — requires Azure AI Foundry (or OpenAI endpoint) to run live LLM calls. Without it, the worker falls back to a deterministic echo provider that routes all uncertain cases to human review.

2. **Receipt OCR requires Azure Document Intelligence** — without `APP_DOC_INTEL_ENDPOINT`, image/PDF receipts skip OCR and are routed to Finance for manual entry. Plain-text receipts parse with the built-in regex extractor.

3. **Policy RAG requires Azure AI Search** — without `APP_SEARCH_ENDPOINT`, the Policy Assistant falls back to the uploaded agency policy document + the baseline ruleset. Still functional; just not vector-similarity-based retrieval.

4. **SQLite is single-writer** — fine for demo/development. Production should use PostgreSQL Flexible Server (`postgresql+psycopg://...` in `APP_DATABASE_URL`).

5. **SMTP email** — password reset emails are logged to the console in dev mode (`APP_EMAIL_BACKEND=console`). Production SMTP needs credentials set in `.env`.

6. **Frontend is a reference scaffold** — the Next.js portal implements all 4 role UIs with full read/write. Some advanced admin views (bulk policy document import, custom cap editor) are placeholders.

7. **No mobile optimisation** — the portal is a desktop-first web application.

---

## Demo Video

**[Watch the 3-minute demo](https://youtu.be/PLACEHOLDER)**

The video shows:
- Employee submitting a multi-item expense sheet with receipt upload and policy feedback
- Manager reviewing and approving line items in the review queue
- Finance AI assistant making policy-driven decisions with citations
- Admin managing users and agencies
- MCP server answering natural language queries in Claude Desktop

---

## Infrastructure

Provisioned with Bicep. See [infra/README.md](infra/README.md) for one-command Azure deployment.

## Identity

DB-backed identity for early build, behind a pluggable provider. Swapping to Microsoft Entra External ID is a single config change (`APP_AUTH_PROVIDER=entra`). See [docs/identity-strategy.md](docs/identity-strategy.md).

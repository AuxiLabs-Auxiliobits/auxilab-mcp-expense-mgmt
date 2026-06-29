# TripSense

AI-powered business travel expense management via MCP (Model Context Protocol).

TripSense provides 8 MCP tools for trip budgeting, policy compliance, receipt OCR, spend classification, duplicate detection, reconciliation, and manager reporting — backed by SQLite and a React dashboard.

## Stack

| Layer | Technology |
|-------|-----------|
| MCP Server | Python 3.11, MCP Python SDK |
| Chat agent | Anthropic API (`claude-sonnet-4-6`) with tool use over the 8 MCP tools |
| API | FastAPI + Uvicorn |
| Database | SQLite |
| OCR | pytesseract + Pillow |
| Frontend | React 18, Tailwind CSS, Vite |

## Project Structure

```
tripsense/
├── backend/
│   ├── mcp_server/
│   │   ├── server.py              # MCP server entry point
│   │   ├── policy_engine.py       # Company policy evaluation
│   │   └── tools/
│   │       ├── trip_tools.py      # plan_trip_budget, pre_approve_trip
│   │       ├── policy_tools.py    # check_policy_compliance
│   │       ├── receipt_tools.py   # parse_receipt, classify, duplicate
│   │       └── report_tools.py    # reconcile_trip, generate_trip_report
│   ├── api/main.py                # FastAPI REST endpoints
│   └── database/
│       ├── schema.sql
│       ├── db.py
│       └── company_policy.json
├── frontend/src/                  # React dashboard
├── demo_data/seed_claims.py       # 15 synthetic demo claims
└── pyproject.toml
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `plan_trip_budget` | Budget breakdown by category for destination/duration/purpose |
| `check_policy_compliance` | Returns compliant bool + violations list |
| `pre_approve_trip` | Issues approval_token, budget_cap, expiry |
| `parse_receipt` | OCR receipt → merchant, date, amount, line_items, reconciliation_flag |
| `classify_spend_category` | Merchant/description → category + confidence |
| `detect_duplicate_claim` | Checks SQLite for same merchant+amount within ±3 days |
| `reconcile_trip` | Match receipts to approval, overage per category, compliance % |
| `generate_trip_report` | Totals, violations, at-risk amount, manager narrative |

## Quick Start

### 1. Install dependencies

```bash
pip install -e ".[dev]"
```

> **OCR note:** Install [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) on your system for receipt parsing.

### 2. Seed demo data

```bash
python demo_data/seed_claims.py
```

This creates 15 synthetic claims: 8 compliant, 4 violations, 2 near-duplicates, 1 missing receipt.

### 3. Run the MCP server

```bash
tripsense-mcp
# or
python -m backend.mcp_server.server
```

### 4. Run the API

The chat interface drives Claude (`claude-sonnet-4-6`) via the Anthropic API, so
the API server needs an Anthropic API key in its environment:

```bash
export ANTHROPIC_API_KEY=sk-ant-...      # PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."
uvicorn backend.api.main:app --reload --port 8000
```

The key stays server-side — the browser only talks to `/api/chat`, never to Anthropic directly.

### 5. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The primary view is a **chat interface** — type natural-language
requests (e.g. "Plan a 3 day trip to Bangalore for a client meeting") and Claude autonomously
calls the relevant MCP tools, showing a per-message tool-call log. The form-based Trip Planner,
Claims, and Reports tabs remain available as secondary views. Use the 📎 button in the chat to
upload a receipt image — try `demo_data/sample_receipts/taj_hotel_receipt.png`, whose line items
intentionally don't match its total to demonstrate the reconciliation flag. Regenerate it with
`python demo_data/sample_receipts/generate_receipt.py`.

## MCP Configuration

Add to your MCP client config (e.g. Cursor):

```json
{
  "mcpServers": {
    "tripsense": {
      "command": "tripsense-mcp",
      "args": []
    }
  }
}
```

## Company Policy

Policy rules live in `backend/database/company_policy.json`:

- Daily limits: hotel $250, meals $75, transport $100, miscellaneous $50
- City overrides for New York, San Francisco, London, Tokyo, Paris
- Purpose multipliers for client_meeting, conference, training, etc.
- Prohibited categories: entertainment, personal
- Receipt required above $25

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/chat` | Chat with Claude; runs the tool-use loop over all 8 MCP tools |
| POST | `/api/budget/plan` | Plan trip budget |
| POST | `/api/policy/check` | Check compliance |
| POST | `/api/trip/pre-approve` | Pre-approve trip |
| POST | `/api/receipt/parse` | Parse receipt by file path (OCR) |
| POST | `/api/receipts/parse` | Parse an uploaded receipt image (multipart; used by the chat 📎 upload) |
| POST | `/api/spend/classify` | Classify spend |
| POST | `/api/claim/duplicate-check` | Detect duplicates |
| POST | `/api/trip/reconcile` | Reconcile trip |
| POST | `/api/trip/report` | Generate report |
| GET | `/api/dashboard/stats` | Dashboard statistics |
| GET | `/api/claims` | List expense claims |
| GET | `/api/trips` | List trip plans |

## License

MIT

## Setup
1. Install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
2. Copy .env.example to .env and set your Tesseract path

# Expense Management Platform

Enterprise expense compliance platform — MCP server + multi-role web portal + document RAG.
See [SCOPING.md](SCOPING.md) for the full product/architecture spec.

> **Governing principle:** the LLM advises; deterministic code decides.

## Monorepo layout

```
.
├── core-engine/      # Pure Python + Pydantic v2 — the 5 tools, baseline policy, LLM gateway
├── mcp-server/       # MCP SDK wrapper over the engine → published as auxilab-mcp-expense-mgmt
├── api/              # FastAPI web API — RBAC, agency-scoped workflow, auth, audit log
├── workers/          # LangGraph LLM finance approver + Service Bus consumers + agency RAG
├── frontend/         # Next.js 15 reference scaffold — 4 role-scoped UIs (reference only)
├── infra/            # Bicep IaC — all Azure resources, per-environment (DEPLOYED to dev)
├── docs/             # Architecture decision records & design notes
└── SCOPING.md        # Product spec
```

## Build stages (see SCOPING.md §16)

| Stage | Deliverable | Status |
|---|---|---|
| S0 | Core engine (5 tools) + schemas + baseline policy JSON + LLM gateway + evals | ✅ |
| S1 | 5 tools via MCP SDK (`auxilab-mcp-expense-mgmt`) | ✅ |
| S2 | FastAPI + RBAC + agency scope + sheet/line-item state machine + audit | ✅ |
| S3 | LangGraph finance approver + agency RAG + guardrails | 🟡 scaffolded (offline-runnable) |
| S4 | Next.js portal (4 role UIs) | 🟡 reference scaffold |
| S5 | Hardening (guardrails, VNet/PE, WAF/APIM, observability, DR) | ⬜ |

> Status reflects code structure, not production-readiness. The whole backend runs locally
> **with no Azure** (SQLite + offline LLM provider); Azure wiring is opt-in per package.

## Quickstart (no Azure needed)

```bash
pip install -e ./core-engine[dev] && pip install -e ./api[dev]
cd api && cp .env.example .env && uvicorn app.main:app --reload
# → http://localhost:8000/docs  (demo users: {employee,manager,finance,admin}@demo.local / "demo")
```

See [Makefile](Makefile) for `install` / `test` / `api` / `workers` / `mcp` targets, and each
package's README for details.

## Infrastructure

Provisioned with **Bicep**. See [infra/README.md](infra/README.md) for deployment.

## Identity

DB-backed identity for early build, behind a pluggable provider so the swap to
**Microsoft Entra External ID** is config-level. See [docs/identity-strategy.md](docs/identity-strategy.md).

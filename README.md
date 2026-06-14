# Expense Management Platform

Enterprise expense compliance platform — MCP server + multi-role web portal + document RAG.
See [SCOPING.md](SCOPING.md) for the full product/architecture spec.

> **Governing principle:** the LLM advises; deterministic code decides.

## Monorepo layout

```
.
├── core-engine/      # Pure Python + Pydantic v2 — the 5 tools, zero framework imports
├── mcp-server/       # MCP SDK wrapper over the engine → published as auxilab-mcp-expense-mgmt
├── api/              # FastAPI web API — RBAC, auth, three-line routing, audit log
├── portal/           # Next.js 15 portal — 4 role-scoped UIs
├── workers/          # Service Bus consumers — doc ingestion, batch claim processing
├── infra/            # Bicep IaC — all Azure resources, per-environment
├── docs/             # Architecture decision records & design notes
└── SCOPING.md        # Product spec
```

## Build stages (see SCOPING.md §14)

| Stage | Deliverable | Status |
|---|---|---|
| S0 | Core engine + schemas + policy JSON + Postgres + eval harness | ⬜ |
| S1 | 5 MCP tools, published package | ⬜ |
| S2 | FastAPI + RBAC + auth + audit + Service Bus | ⬜ |
| S3 | Next.js portal (4 role UIs) | ⬜ |
| S4 | Documents + RAG | ⬜ |
| S5 | Hardening (guardrails, VNet/PE, WAF/APIM, observability, DR) | ⬜ |

## Infrastructure

Provisioned with **Bicep**. See [infra/README.md](infra/README.md) for deployment.

## Identity

DB-backed identity for early build, behind a pluggable provider so the swap to
**Microsoft Entra External ID** is config-level. See [docs/identity-strategy.md](docs/identity-strategy.md).

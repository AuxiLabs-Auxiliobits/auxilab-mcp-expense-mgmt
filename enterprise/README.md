# Enterprise implementation (Azure)

**This directory is isolated reference material. Nothing here is installed, imported, linted, or
tested by the published open-source tool.**

If you came here looking for the five expense-compliance tools, they are at the repository root —
see [../README.md](../README.md). They run offline with no cloud account.

## What's in here

The original multi-tenant expense platform this project was extracted from.

| Directory | Contents |
|---|---|
| `api/` | FastAPI backend — Entra ID / OIDC / database auth, RBAC across five roles, approval state machine, immutable audit log, Alembic migrations |
| `workers/` | Azure Service Bus consumers, LangGraph finance approver, AI Search RAG retriever, Document Intelligence ingestion, Content Safety prompt shield |
| `core-engine/` | The original `expense_core` package, including the Azure AI Foundry LLM provider |
| `mcp-server/` | The 61-tool MCP server that proxies the authenticated API |
| `frontend/` | Next.js 15 portal — Employee, Manager, Finance and Admin views |
| `infra/` | Bicep infrastructure as code, subscription-scoped |
| `policy_docs/` | Example agency policy documents for the RAG pipeline |
| `docs/` | `SCOPING.md` (the original product spec and ADRs, cited by section throughout this code), hardening-sprint notes, assistant design notes, identity strategy, user schema |
| `deploy/` | Deployment workflow, Azure env bootstrap script, docker-compose for local Postgres/Redis |

## Relationship to the standalone tool

None, by design. There is no shared configuration, no shared credentials, and no import path between
them. The published package cannot reach this code, and
[../tests/test_offline_guarantee.py](../tests/test_offline_guarantee.py) fails the build if an Azure
import, cloud SDK, auth token or `AZURE_*` environment variable appears in the published files.

The five tools were rewritten for the standalone package rather than shared: `tools/` depends only
on `pydantic`, whereas `core-engine/` carries an Azure extra and enterprise workflow enums.

## Running it

See [../DEPLOYMENT.md](../DEPLOYMENT.md). You will need an Azure subscription — this is not a
free-tier deployment.

## Support status

Archived. Not maintained as part of the open-source project, not covered by CI. Treat it as a
starting point for your own deployment.

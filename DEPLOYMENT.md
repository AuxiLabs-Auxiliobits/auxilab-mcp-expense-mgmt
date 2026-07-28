# Enterprise Deployment (Azure)

> **You almost certainly do not need this file.**
>
> The standalone tool described in [README.md](README.md) runs offline with no cloud account:
> `pip install -r requirements.txt && python app.py`. Everything below concerns the separate
> Azure enterprise implementation archived under [enterprise/](enterprise/).

---

## What this is

`enterprise/` holds the original multi-tenant expense platform this project was extracted from. It
is a genuine enterprise system — SSO, role-based access control, an approval workflow, message
queues, a RAG pipeline and a web portal — and it needs an Azure subscription to run.

It is **not installed** by `requirements.txt`, **not imported** by any published module, and **not
required** for the five tools. A test in the published suite
([tests/test_offline_guarantee.py](tests/test_offline_guarantee.py)) fails the build if any of it
leaks back into the standalone package.

| | Standalone tool | Enterprise platform |
|---|---|---|
| Location | repository root | [enterprise/](enterprise/) |
| Setup | `pip install -r requirements.txt` | Azure subscription + Bicep deploy |
| Runs offline | Yes | No |
| Credentials | None | Entra ID, Key Vault, managed identities |
| Persistence | SQLite file | PostgreSQL Flexible Server |
| File storage | Local filesystem | Azure Blob Storage |
| Auth | None | Entra ID SSO + RBAC (5 roles) |
| MCP tools | 5 | 61 |
| Interface | Gradio / CLI | Next.js portal |

---

## Layout

```
enterprise/
├── api/           FastAPI backend — RBAC, approval state machine, audit log, Alembic migrations
├── workers/       Service Bus consumers, LangGraph finance approver, AI Search RAG, prompt shield
├── core-engine/   The original expense_core package (with the Azure LLM provider)
├── mcp-server/    The 61-tool MCP server that proxies the authenticated API
├── frontend/      Next.js 15 portal — Employee / Manager / Finance / Admin
├── infra/         Bicep IaC — subscription-scoped, one command to provision
├── policy_docs/   Example agency policy documents for the RAG pipeline
├── docs/          SCOPING.md (product spec + ADRs), hardening notes, identity strategy
├── deploy/        deploy-dev.yml workflow, set-azure-env.ps1, docker-compose.yml
└── Azure-Entra-SSO-*.{pdf,docx}   SSO setup guides
```

---

## Azure resources provisioned

`enterprise/infra/main.bicep` is subscription-scoped: it creates the resource group and deploys the
foundation modules.

| Module | Resource |
|---|---|
| `monitoring` | Log Analytics workspace + Application Insights |
| `keyvault` | Key Vault (RBAC mode) |
| `storage` | Storage account with `receipts` / `documents` containers, no public blob access |
| `acr` | Container Registry (managed-identity pull, admin disabled) |
| `redis` | Azure Managed Redis, TLS-only |
| `servicebus` | Service Bus namespace + `document-ingestion` / `claim-batch` queues, dead-lettering on |
| `postgres` | PostgreSQL Flexible Server + `expense` database (zone-redundant HA in prod) |
| `ai` | AI Foundry (gpt-4o + embeddings), AI Search, Document Intelligence, Content Safety |
| `containerapps` | Container Apps managed environment, wired to Log Analytics |
| `rbac` | User-assigned identities + least-privilege data-plane grants |
| `apps` | Container Apps: API (external ingress) + finance and ingestion workers (KEDA-scaled) |

### Optional hardening

Both default to `false` in dev; dev keeps the cheaper flat topology.

| Flag | Adds |
|---|---|
| `deployNetworking` | VNet with delegated subnets and NSGs, Private Endpoints and Private DNS zones for Postgres, Blob, Key Vault, AI Search and Cognitive Services. VNet-injects the Container Apps environment. |
| `deployEdge` | Front Door Standard/Premium with a WAF managed rule set, API Management with rate-limit and request-validation policies, an App Service plan hosting the Next.js portal, and metric alerts with an action group. |

---

## Prerequisites

- An Azure subscription with permission to create resource groups
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) with the Bicep extension
- Python 3.12+ and Node.js 20+ for local development

```powershell
az login
az account set --subscription "<your-subscription-id>"
az bicep upgrade

# Needed for adminObjectId in the parameters file.
az ad signed-in-user show --query id -o tsv

# Register resource providers once per subscription. Microsoft.AlertsManagement is required
# because Application Insights auto-creates a "Failure Anomalies" alert rule.
foreach ($rp in 'Microsoft.KeyVault','Microsoft.Storage','Microsoft.ContainerRegistry',
  'Microsoft.Cache','Microsoft.ServiceBus','Microsoft.DBforPostgreSQL',
  'Microsoft.CognitiveServices','Microsoft.Search','Microsoft.App',
  'Microsoft.OperationalInsights','Microsoft.Insights','Microsoft.AlertsManagement') {
  az provider register --namespace $rp
}
```

---

## Deploy

All commands run from the **repository root**.

### 1. Validate

```powershell
az bicep build --file enterprise/infra/main.bicep

az deployment sub validate `
  --location centralindia `
  --template-file enterprise/infra/main.bicep `
  --parameters enterprise/infra/main.dev.bicepparam
```

### 2. Preview

```powershell
az deployment sub what-if `
  --location centralindia `
  --template-file enterprise/infra/main.bicep `
  --parameters enterprise/infra/main.dev.bicepparam pgAdminPassword=$env:PG_PWD
```

### 3. Provision

```powershell
az deployment sub create `
  --location centralindia `
  --template-file enterprise/infra/main.bicep `
  --parameters enterprise/infra/main.dev.bicepparam pgAdminPassword=$env:PG_PWD
```

Set `adminObjectId` in the parameters file to your own object id. **Never commit
`pgAdminPassword`** — pass it at deploy time or source it from Key Vault.

Container images default to a public placeholder so the first infra deploy succeeds before any image
exists. The deploy workflow then builds the real images and rolls them in.

### 4. Build images, migrate, and roll out

[enterprise/deploy/deploy-dev.yml](enterprise/deploy/deploy-dev.yml) is a `workflow_dispatch`
GitHub Actions workflow that runs infra → build API image → migrate → build worker image → update
Container Apps. To use it, copy it into `.github/workflows/`.

It authenticates with **OIDC federated credentials** — no stored service-principal secret. Required
repository secrets:

| Secret | Purpose |
|---|---|
| `AZURE_CLIENT_ID` | App registration federated for OIDC login |
| `AZURE_TENANT_ID` | Entra tenant id |
| `AZURE_SUBSCRIPTION_ID` | Target subscription |
| `PG_ADMIN_PASSWORD` | PostgreSQL admin password, passed to the Bicep deploy |

The federated identity needs Contributor (or a scoped equivalent) on the resource group, plus
AcrPush on the registry.

---

## Local enterprise development

```bash
cd enterprise

# Postgres + Redis
docker compose -f deploy/docker-compose.yml up -d

# Engine first — the other packages depend on it.
pip install -e ./core-engine[dev]
pip install -e ./api[dev] -e ./workers[dev] -e ./mcp-server[dev]

cd api && alembic upgrade head && uvicorn app.main:app --reload
```

The frontend:

```bash
cd enterprise/frontend
npm ci
npm run dev
```

The enterprise packages ship their own `.env.example` files listing every setting. Nothing there is
read by the standalone tool.

---

## Single sign-on

Entra ID setup is documented in the guides bundled alongside the code:

- `enterprise/Azure-Entra-SSO-QuickStart.pdf` — the short version
- `enterprise/Azure-Entra-SSO-Setup-Guide.pdf` — full walkthrough, app registration to role mapping
- `enterprise/docs/identity-strategy.md` — why the identity model is shaped the way it is

The API supports database, OIDC, Entra and hybrid auth providers, selected with
`APP_AUTH_PROVIDER`. `enterprise/infra/keycloak/` has a local Keycloak realm for testing OIDC
without an Azure tenant.

---

## Cost note

The foundation layer provisions PostgreSQL Flexible Server, Azure Managed Redis, Service Bus, AI
Foundry, AI Search, Document Intelligence and Container Apps. Even in dev this is **not** a
free-tier deployment. Use `what-if` to preview, and delete the resource group when you're done:

```powershell
az group delete --name expmgmt-dev-rg --yes
```

---

## Support status

The enterprise implementation is archived reference material. It is not covered by the published
test suite, is not linted by CI, and is not maintained as part of the open-source project. Treat it
as a starting point for your own deployment rather than a supported product.

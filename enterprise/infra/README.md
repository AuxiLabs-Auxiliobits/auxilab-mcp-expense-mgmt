# Infrastructure (Bicep)

Per-environment Azure provisioning. `main.bicep` is subscription-scoped: it creates the
resource group and deploys the foundation modules.

## What's provisioned today (foundation layer)

| Module | Resource | Notes |
|---|---|---|
| `monitoring` | Log Analytics + App Insights | workspace-based |
| `keyvault` | Key Vault (RBAC) | admin role for bootstrap; MI access later |
| `storage` | Storage account + `receipts`/`documents` containers | no public blob access |
| `acr` | Container Registry | MI pull, admin disabled |
| `redis` | Azure Managed Redis (`redisEnterprise`, Balanced) | TLS-only, port 10000 |
| `servicebus` | Service Bus (`-bus` namespace) + `document-ingestion`/`claim-batch` queues | dead-letter on |
| `postgres` | PostgreSQL Flexible Server + `expense` db | ZR-HA in prod |
| `ai` | AI Foundry (gpt-4o + embeddings), Search, Doc Intelligence, Content Safety | deployed to `aiLocation` (eastus); toggle with `deployAi` |
| `containerapps` | Container Apps managed environment | log-wired to Log Analytics; VNet-injected when `deployNetworking` |
| `rbac` | User-assigned identities + data-plane grants (Blob/ServiceBus/KeyVault/AI) + **AcrPull** | least-privilege, scoped per resource |
| `apps` | Container Apps: **API** (external ingress), **finance** + **ingestion** workers | MI pull from ACR; workers scale on Service Bus queue length (KEDA) |

Images default to a public placeholder (`mcr.microsoft.com/k8se/quickstart:latest`) so the
first infra deploy succeeds before any image exists; the `deploy-dev` workflow then builds
the real images and runs `az containerapp update` to roll them in.

## Compute / app layer

The `apps` module deploys three Container Apps into the managed environment:

| App | Ingress | Identity | Notes |
|---|---|---|---|
| `${namePrefix}-${env}-api` | external (port 8000) | api MI | HTTP scale rule, env vars `APP_*` (DB/auth/KV/AppInsights/ServiceBus/blob/AI) |
| `${namePrefix}-${env}-worker-finance` | none | worker MI | `WORKER_CONSUMER=finance`, KEDA `azure-servicebus` scaler on `finance-approval` |
| `${namePrefix}-${env}-worker-ingestion` | none | worker MI | `WORKER_CONSUMER=ingestion`, KEDA scaler on `document-ingestion` |

KEDA scaling uses workload-identity (the worker user-assigned identity) — no connection
string or secret.

## S5 hardening (optional — gated by flags, default OFF in dev)

Two flags switch the hardened topology on; dev keeps the public/flat (cheap) configuration.

| Flag | Default | Adds |
|---|---|---|
| `deployNetworking` | `false` | `network` (VNet + container-apps `/23` subnet delegated to `Microsoft.App/environments`, private-endpoints + data subnets, NSGs) and `privateendpoints` (Private Endpoints + Private DNS zones + links for Postgres, Storage blob, Key Vault, AI Search, Cognitive Services). Also VNet-injects the Container Apps env. |
| `deployEdge` | `false` | `frontdoor` (Front Door Std/Premium + WAF managed rule set, origin = API app FQDN), `apim` (API Management with product + rate-limit / request-size / content-validation policy), `appservice` (Linux App Service plan + Node LTS Web App host for the Next.js portal), `alerts` (Action Group + metric alerts: failure rate, latency, availability). |

When `deployAi` is `false`, the AI-related private endpoints and AI env vars are skipped.

Enable in a non-dev params file:

```bicep
param deployNetworking = true
param deployEdge = true
```

## Prerequisites

```powershell
az login
az account set --subscription "<your-subscription-id>"
az bicep upgrade
$objectId = az ad signed-in-user show --query id -o tsv   # for adminObjectId

# Register resource providers once per subscription. Microsoft.AlertsManagement is
# required because App Insights auto-creates a "Failure Anomalies" alert rule.
foreach ($rp in 'Microsoft.KeyVault','Microsoft.Storage','Microsoft.ContainerRegistry',
  'Microsoft.Cache','Microsoft.ServiceBus','Microsoft.DBforPostgreSQL',
  'Microsoft.CognitiveServices','Microsoft.Search','Microsoft.App',
  'Microsoft.OperationalInsights','Microsoft.Insights','Microsoft.AlertsManagement') {
  az provider register --namespace $rp
}
```

## Validate (no deploy)

```powershell
az bicep build --file enterprise/infra/main.bicep
az deployment sub validate `
  --location centralindia `
  --template-file enterprise/infra/main.bicep `
  --parameters enterprise/infra/main.dev.bicepparam
```

## What-if (preview changes)

```powershell
az deployment sub what-if `
  --location centralindia `
  --template-file enterprise/infra/main.bicep `
  --parameters enterprise/infra/main.dev.bicepparam pgAdminPassword=$env:PG_PWD
```

## Deploy

```powershell
az deployment sub create `
  --location centralindia `
  --template-file enterprise/infra/main.bicep `
  --parameters enterprise/infra/main.dev.bicepparam pgAdminPassword=$env:PG_PWD
```

> Replace `adminObjectId` and never commit a real `pgAdminPassword` — pass it at deploy
> time or source it from Key Vault. Region defaults to `centralindia`; change in the
> `.bicepparam` if needed.

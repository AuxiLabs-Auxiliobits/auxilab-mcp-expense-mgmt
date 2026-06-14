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
| `containerapps` | Container Apps managed environment | log-wired to Log Analytics |

## Not yet authored (added incrementally)

- Compute/edge: App Service (portal), Front Door + WAF, APIM
- Networking: VNet, subnets, Private Endpoints (S5 hardening)
- Managed Identities + Key Vault Secrets User / ACR Pull role assignments per service

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
az bicep build --file infra/main.bicep
az deployment sub validate `
  --location centralindia `
  --template-file infra/main.bicep `
  --parameters infra/main.dev.bicepparam
```

## What-if (preview changes)

```powershell
az deployment sub what-if `
  --location centralindia `
  --template-file infra/main.bicep `
  --parameters infra/main.dev.bicepparam pgAdminPassword=$env:PG_PWD
```

## Deploy

```powershell
az deployment sub create `
  --location centralindia `
  --template-file infra/main.bicep `
  --parameters infra/main.dev.bicepparam pgAdminPassword=$env:PG_PWD
```

> Replace `adminObjectId` and never commit a real `pgAdminPassword` — pass it at deploy
> time or source it from Key Vault. Region defaults to `centralindia`; change in the
> `.bicepparam` if needed.

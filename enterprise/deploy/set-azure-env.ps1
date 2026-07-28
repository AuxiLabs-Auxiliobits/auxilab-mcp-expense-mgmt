# Populate all WORKERS_* / APP_* env vars for local-against-Azure runs.
# Dot-source it (note the leading dot) so the vars land in YOUR shell:
#
#     . .\set-azure-env.ps1
#
# Pulls keys/endpoints live from `az` (nothing secret is stored on disk). Run `az login` first.
$ErrorActionPreference = "Stop"
$RG = "expmgmt-dev-rg"

Write-Host "Fetching Azure endpoints/keys..." -ForegroundColor Cyan

# --- AI Search (RAG index) ---
$env:WORKERS_SEARCH_ENDPOINT   = "https://expmgmt-dev-search.search.windows.net"
$env:WORKERS_SEARCH_API_KEY    = (az search admin-key show -g $RG --service-name expmgmt-dev-search --query primaryKey -o tsv)
$env:WORKERS_SEARCH_INDEX_NAME = "agency-policies"

# --- Foundry (chat + embeddings) ---
$env:WORKERS_FOUNDRY_ENDPOINT      = (az cognitiveservices account show -n expmgmt-dev-aifoundry -g $RG --query properties.endpoint -o tsv)
$env:WORKERS_FOUNDRY_API_KEY       = (az cognitiveservices account keys list -n expmgmt-dev-aifoundry -g $RG --query key1 -o tsv)
$env:WORKERS_FOUNDRY_DEPLOYMENT    = "gpt-4o"
$env:WORKERS_EMBEDDING_DEPLOYMENT  = "text-embedding-3-large"

# --- Document Intelligence (PDF extraction) ---
$env:WORKERS_DOC_INTEL_ENDPOINT = (az cognitiveservices account show -n expmgmt-dev-docintel -g $RG --query properties.endpoint -o tsv)
$env:WORKERS_DOC_INTEL_API_KEY  = (az cognitiveservices account keys list -n expmgmt-dev-docintel -g $RG --query key1 -o tsv)

# --- Service Bus (ingestion queue) ---
$env:WORKERS_SERVICE_BUS_CONNECTION_STRING = (az servicebus namespace authorization-rule keys list -g $RG --namespace-name expmgmt-dev-bus --name RootManageSharedAccessKey --query primaryConnectionString -o tsv)
$env:WORKERS_REQUIRE_VIRUS_SCAN = "false"   # Defender for Storage not enabled in dev
$env:WORKERS_API_BASE_URL       = "http://localhost:8000"

# --- API (only needed in the terminal running uvicorn) ---
$env:APP_STORAGE_ACCOUNT_URL  = "https://expmgmtdevsa.blob.core.windows.net"
$env:APP_SERVICEBUS_NAMESPACE = "expmgmt-dev-bus"
$env:APP_ENVIRONMENT          = "dev"

Write-Host "Done. Search=$($env:WORKERS_SEARCH_ENDPOINT)  Foundry=$($env:WORKERS_FOUNDRY_DEPLOYMENT)" -ForegroundColor Green
Write-Host "Note: WORKERS_AGENT_TOKEN is NOT set here (it expires hourly) - mint it via /auth/login when needed." -ForegroundColor Yellow

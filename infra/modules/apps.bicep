// Container Apps for the API + the two Service Bus worker consumers (SCOPING §9, §11, §14).
//
// The managed environment and the user-assigned identities already exist (containerapps.bicep
// + rbac.bicep). This module deploys the three apps, attaching the right identity to each and
// pulling images from ACR via that identity (no admin creds). Image references default to a
// public placeholder so the FIRST infra deploy succeeds before any image exists in ACR; CI
// then runs `az containerapp update` to roll the real ACR images.
param namePrefix string
param env string
param location string
param tags object

@description('Resource id of the Container Apps managed environment.')
param environmentId string

@description('ACR login server, e.g. expmgmtdevacr.azurecr.io.')
param acrLoginServer string

// --- Identities ------------------------------------------------------------ //
@description('Resource id of the API user-assigned identity.')
param apiIdentityId string
@description('Client id of the API user-assigned identity (for Entra/MI SDK auth).')
param apiIdentityClientId string
@description('Resource id of the worker user-assigned identity.')
param workerIdentityId string
@description('Client id of the worker user-assigned identity.')
param workerIdentityClientId string

// --- Images (CI overwrites these with the real ACR tags after the first deploy) --- //
@description('API container image reference.')
param apiImage string = 'mcr.microsoft.com/k8se/quickstart:latest'
@description('Worker container image reference (shared by both worker apps).')
param workerImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

@description('Port the API listens on (Dockerfile EXPOSE / $PORT default).')
param apiTargetPort int = 8000

// --- Endpoints / config injected into the containers ----------------------- //
@description('PostgreSQL FQDN (the API builds its DATABASE_URL from this).')
param postgresFqdn string
@description('PostgreSQL admin login (for the API DATABASE_URL).')
param pgAdminLogin string
@description('PostgreSQL admin password — injected as a Container App secret, never plaintext env.')
@secure()
param pgAdminPassword string
@description('PostgreSQL database name.')
param pgDatabase string = 'expense'
@description('Key Vault URI (secret references resolve from here).')
param keyVaultUri string
@description('Application Insights connection string.')
param appInsightsConnectionString string
@description('Service Bus fully-qualified namespace, e.g. expmgmt-dev-bus.servicebus.windows.net.')
param serviceBusNamespace string
@description('Blob storage endpoint.')
param blobEndpoint string
@description('Auth provider for the API (db | entra).')
param authProvider string = 'db'

// --- AI endpoints (empty when deployAi is false) --------------------------- //
param deployAi bool = true
param foundryEndpoint string = ''
param searchEndpoint string = ''
param docIntelEndpoint string = ''
param contentSafetyEndpoint string = ''

// Service Bus FQDN namespace for MI auth: '<ns>.servicebus.windows.net'.
var serviceBusFqdn = '${serviceBusNamespace}.servicebus.windows.net'
// API base URL workers call back into (cluster-internal not exposed; use the public FQDN).
var apiBaseUrl = 'https://${api.properties.configuration.ingress.fqdn}'

var financeQueue = 'finance-approval'
var ingestionQueue = 'document-ingestion'

var minReplicas = env == 'prod' ? 1 : 0

// Full DB URL (with password) — stored as a Container App / Job secret, referenced via
// secretRef so the password is never a plaintext env var. The migrate job reuses the same.
var databaseUrl = 'postgresql://${pgAdminLogin}:${pgAdminPassword}@${postgresFqdn}:5432/${pgDatabase}?sslmode=require'

// --- API app --------------------------------------------------------------- //
resource api 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${namePrefix}-${env}-api'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${apiIdentityId}': {} }
  }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      secrets: [
        { name: 'database-url', value: databaseUrl }
      ]
      ingress: {
        external: true
        targetPort: apiTargetPort
        transport: 'auto'
        allowInsecure: false
        traffic: [ { latestRevision: true, weight: 100 } ]
      }
      registries: [
        {
          server: acrLoginServer
          identity: apiIdentityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: apiImage
          resources: { cpu: json('0.5'), memory: '1.0Gi' }
          env: [
            { name: 'APP_ENVIRONMENT', value: env }
            { name: 'APP_AUTH_PROVIDER', value: authProvider }
            { name: 'APP_DATABASE_URL', secretRef: 'database-url' }
            { name: 'APP_FOUNDRY_ENDPOINT', value: deployAi ? foundryEndpoint : '' }
            { name: 'APP_STORAGE_ACCOUNT_URL', value: blobEndpoint }
            { name: 'APP_SERVICEBUS_NAMESPACE', value: serviceBusFqdn }
            { name: 'AZURE_KEY_VAULT_URI', value: keyVaultUri }
            { name: 'AZURE_CLIENT_ID', value: apiIdentityClientId }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
          ]
        }
      ]
      scale: {
        minReplicas: env == 'prod' ? 1 : 0
        maxReplicas: 5
        rules: [
          {
            name: 'http-scale'
            http: { metadata: { concurrentRequests: '50' } }
          }
        ]
      }
    }
  }
}

// --- Finance worker app ---------------------------------------------------- //
resource workerFinance 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${namePrefix}-${env}-worker-finance'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${workerIdentityId}': {} }
  }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [
        {
          server: acrLoginServer
          identity: workerIdentityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: workerImage
          args: [ 'finance' ]
          resources: { cpu: json('0.5'), memory: '1.0Gi' }
          env: [
            { name: 'WORKER_CONSUMER', value: 'finance' }
            { name: 'WORKERS_SERVICE_BUS_NAMESPACE', value: serviceBusFqdn }
            { name: 'WORKERS_FINANCE_QUEUE_NAME', value: financeQueue }
            { name: 'WORKERS_SEARCH_ENDPOINT', value: deployAi ? searchEndpoint : '' }
            { name: 'WORKERS_FOUNDRY_ENDPOINT', value: deployAi ? foundryEndpoint : '' }
            { name: 'WORKERS_DOC_INTEL_ENDPOINT', value: deployAi ? docIntelEndpoint : '' }
            { name: 'WORKERS_CONTENT_SAFETY_ENDPOINT', value: deployAi ? contentSafetyEndpoint : '' }
            { name: 'WORKERS_STORAGE_ACCOUNT_URL', value: blobEndpoint }
            { name: 'WORKERS_API_BASE_URL', value: apiBaseUrl }
            { name: 'AZURE_CLIENT_ID', value: workerIdentityClientId }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: 10
        rules: [
          {
            name: 'finance-queue'
            custom: {
              type: 'azure-servicebus'
              metadata: {
                namespace: serviceBusNamespace
                queueName: financeQueue
                messageCount: '5'
              }
              // Workload-identity auth for the KEDA azure-servicebus scaler: KEDA reads
              // the queue length using the worker user-assigned identity (no connection
              // string / secret). The scaler resolves MI from the app's assigned identity.
              #disable-next-line BCP037
              identity: workerIdentityId
            }
          }
        ]
      }
    }
  }
}

// --- Ingestion worker app -------------------------------------------------- //
resource workerIngestion 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${namePrefix}-${env}-worker-ingestion'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${workerIdentityId}': {} }
  }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [
        {
          server: acrLoginServer
          identity: workerIdentityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: workerImage
          args: [ 'ingestion' ]
          resources: { cpu: json('0.5'), memory: '1.0Gi' }
          env: [
            { name: 'WORKER_CONSUMER', value: 'ingestion' }
            { name: 'WORKERS_SERVICE_BUS_NAMESPACE', value: serviceBusFqdn }
            { name: 'WORKERS_INGESTION_QUEUE_NAME', value: ingestionQueue }
            { name: 'WORKERS_SEARCH_ENDPOINT', value: deployAi ? searchEndpoint : '' }
            { name: 'WORKERS_FOUNDRY_ENDPOINT', value: deployAi ? foundryEndpoint : '' }
            { name: 'WORKERS_DOC_INTEL_ENDPOINT', value: deployAi ? docIntelEndpoint : '' }
            { name: 'WORKERS_CONTENT_SAFETY_ENDPOINT', value: deployAi ? contentSafetyEndpoint : '' }
            { name: 'WORKERS_STORAGE_ACCOUNT_URL', value: blobEndpoint }
            { name: 'WORKERS_API_BASE_URL', value: apiBaseUrl }
            { name: 'AZURE_CLIENT_ID', value: workerIdentityClientId }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: 10
        rules: [
          {
            name: 'ingestion-queue'
            custom: {
              type: 'azure-servicebus'
              metadata: {
                namespace: serviceBusNamespace
                queueName: ingestionQueue
                messageCount: '5'
              }
              // Workload-identity auth for the KEDA azure-servicebus scaler (see finance app).
              #disable-next-line BCP037
              identity: workerIdentityId
            }
          }
        ]
      }
    }
  }
}

// --- Migration job --------------------------------------------------------- //
// Runs `alembic upgrade head` against Postgres using the SAME image, identity and DB
// secret as the API. Manual trigger → CI starts it on deploy; re-runnable any time with
// `az containerapp job start`. This is why prod schema actually gets migrated (the API
// only create_all()s in dev).
resource migrate 'Microsoft.App/jobs@2024-03-01' = {
  name: '${namePrefix}-${env}-migrate'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${apiIdentityId}': {} }
  }
  properties: {
    environmentId: environmentId
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 600
      replicaRetryLimit: 1
      manualTriggerConfig: { parallelism: 1, replicaCompletionCount: 1 }
      secrets: [
        { name: 'database-url', value: databaseUrl }
      ]
      registries: [
        { server: acrLoginServer, identity: apiIdentityId }
      ]
    }
    template: {
      containers: [
        {
          name: 'migrate'
          image: apiImage
          command: [ 'alembic', 'upgrade', 'head' ]
          resources: { cpu: json('0.5'), memory: '1.0Gi' }
          env: [
            { name: 'APP_ENVIRONMENT', value: env }
            { name: 'APP_DATABASE_URL', secretRef: 'database-url' }
            { name: 'AZURE_CLIENT_ID', value: apiIdentityClientId }
          ]
        }
      ]
    }
  }
}

output apiFqdn string = api.properties.configuration.ingress.fqdn
output apiName string = api.name
output migrateJobName string = migrate.name
output workerFinanceName string = workerFinance.name
output workerIngestionName string = workerIngestion.name

// Azure Container Apps managed environment — hosts the FastAPI API, the MCP server,
// and the Service Bus worker consumers (SCOPING §9). The individual container apps
// are deployed by CI/CD once images exist in ACR; this stands up the environment
// and wires it to Log Analytics for centralized logs.
param namePrefix string
param env string
param location string
param tags object

@description('Name of the Log Analytics workspace to send container logs to')
param workspaceName string

@description('Customer (workspace) id of the Log Analytics workspace')
param workspaceCustomerId string

// Reference the already-deployed workspace to read its shared key at deploy time.
resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: workspaceName
}

resource cae 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${namePrefix}-${env}-cae'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: workspaceCustomerId
        sharedKey: law.listKeys().primarySharedKey
      }
    }
    zoneRedundant: env == 'prod'
  }
}

output environmentId string = cae.id
output defaultDomain string = cae.properties.defaultDomain

// Log Analytics workspace + Application Insights (workspace-based).
param namePrefix string
param env string
param location string
param tags object

resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${namePrefix}-${env}-law'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: env == 'prod' ? 90 : 30
  }
}

resource appi 'Microsoft.Insights/components@2020-02-02' = {
  name: '${namePrefix}-${env}-appi'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: law.id
  }
}

output workspaceId string = law.id
output workspaceName string = law.name
output workspaceCustomerId string = law.properties.customerId
output appInsightsConnectionString string = appi.properties.ConnectionString

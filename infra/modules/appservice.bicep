// Linux App Service plan + Web App (Node LTS) hosting the Next.js portal (S5 / edge).
// We only provision the host; the portal code is owned by a co-developer and deployed by
// their pipeline. Gated behind `deployEdge` in main.bicep.
param namePrefix string
param env string
param location string
param tags object

@description('Application Insights connection string for the portal.')
param appInsightsConnectionString string = ''

@description('API base URL the portal calls.')
param apiBaseUrl string = ''

var planSku = env == 'prod' ? 'P1v3' : 'B1'

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${namePrefix}-${env}-portal-plan'
  location: location
  tags: tags
  sku: { name: planSku }
  kind: 'linux'
  properties: {
    reserved: true // Linux
  }
}

resource portal 'Microsoft.Web/sites@2023-12-01' = {
  name: '${namePrefix}-${env}-portal'
  location: location
  tags: tags
  kind: 'app,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'NODE|20-lts'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      appSettings: [
        { name: 'WEBSITE_NODE_DEFAULT_VERSION', value: '~20' }
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
        { name: 'NEXT_PUBLIC_API_BASE_URL', value: apiBaseUrl }
      ]
    }
  }
}

output portalName string = portal.name
output portalDefaultHostName string = portal.properties.defaultHostName

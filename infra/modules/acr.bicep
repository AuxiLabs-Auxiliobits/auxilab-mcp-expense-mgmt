// Azure Container Registry for FastAPI + MCP server + worker images.
param namePrefix string
param env string
param location string
param tags object

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: toLower(replace('${namePrefix}${env}acr', '-', ''))
  location: location
  tags: tags
  sku: { name: env == 'prod' ? 'Premium' : 'Basic' }
  properties: {
    adminUserEnabled: false // pull via Managed Identity, not admin creds
  }
}

output name string = acr.name
output loginServer string = acr.properties.loginServer

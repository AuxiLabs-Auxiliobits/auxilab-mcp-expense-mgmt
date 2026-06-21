// Subscription-scoped entry point. Creates the resource group and deploys the
// foundation layer for one environment. Compute/edge/AI modules are added incrementally.
//
//   az deployment sub create \
//     --location centralindia \
//     --template-file infra/main.bicep \
//     --parameters infra/main.dev.bicepparam
targetScope = 'subscription'

@description('Short environment name: dev | staging | prod')
@allowed(['dev', 'staging', 'prod'])
param env string

@description('Azure region for all resources')
param location string

@description('Region for AI resources. Some (e.g. Content Safety) are not offered in every region; centralindia lacks ContentSafety, so default these to a supported region.')
param aiLocation string = 'eastus'

@description('Deploy the AI layer (Foundry/Search/DocIntel/ContentSafety). Turn off to bring up everything else first.')
param deployAi bool = true

@description('Deploy the networking hardening layer: VNet + subnets + NSGs + Private Endpoints, and VNet-inject the Container Apps env. Default OFF — dev stays public/flat.')
param deployNetworking bool = false

@description('Deploy the edge/ops hardening layer: Front Door + WAF, APIM, App Service portal host, and metric alerts. Default OFF for dev.')
param deployEdge bool = false

@description('Container image references. CI overwrites the apps with the real ACR tags; the defaults let the first infra deploy succeed before any image exists.')
param apiImage string = 'mcr.microsoft.com/k8se/quickstart:latest'
param workerImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

@description('Email for APIM publisher contact and metric-alert notifications (edge layer).')
param opsEmail string = 'operations@retinex.ai'

@description('Resource name prefix, e.g. "expmgmt"')
param namePrefix string

@description('Object ID of the deploying user/SP, granted Key Vault admin for bootstrap')
param adminObjectId string

@description('PostgreSQL administrator login')
param pgAdminLogin string

@description('PostgreSQL administrator password')
@secure()
param pgAdminPassword string

var rgName = '${namePrefix}-${env}-rg'
var tags = {
  application: 'expense-management'
  environment: env
  managedBy: 'bicep'
}

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: rgName
  location: location
  tags: tags
}

module monitoring 'modules/monitoring.bicep' = {
  scope: rg
  name: 'monitoring'
  params: { namePrefix: namePrefix, env: env, location: location, tags: tags }
}

module keyvault 'modules/keyvault.bicep' = {
  scope: rg
  name: 'keyvault'
  params: { namePrefix: namePrefix, env: env, location: location, tags: tags, adminObjectId: adminObjectId }
}

module storage 'modules/storage.bicep' = {
  scope: rg
  name: 'storage'
  params: { namePrefix: namePrefix, env: env, location: location, tags: tags }
}

module acr 'modules/acr.bicep' = {
  scope: rg
  name: 'acr'
  params: { namePrefix: namePrefix, env: env, location: location, tags: tags }
}

module redis 'modules/redis.bicep' = {
  scope: rg
  name: 'redis'
  params: { namePrefix: namePrefix, env: env, location: location, tags: tags }
}

module servicebus 'modules/servicebus.bicep' = {
  scope: rg
  name: 'servicebus'
  params: { namePrefix: namePrefix, env: env, location: location, tags: tags }
}

module postgres 'modules/postgres.bicep' = {
  scope: rg
  name: 'postgres'
  params: {
    namePrefix: namePrefix
    env: env
    location: location
    tags: tags
    adminLogin: pgAdminLogin
    adminPassword: pgAdminPassword
  }
}

module ai 'modules/ai.bicep' = if (deployAi) {
  scope: rg
  name: 'ai'
  params: { namePrefix: namePrefix, env: env, location: aiLocation, tags: tags }
}

// --- Networking hardening (S5) — VNet + subnets + NSGs, gated OFF for dev ---- //
module network 'modules/network.bicep' = if (deployNetworking) {
  scope: rg
  name: 'network'
  params: { namePrefix: namePrefix, env: env, location: location, tags: tags }
}

module containerapps 'modules/containerapps.bicep' = {
  scope: rg
  name: 'containerapps'
  params: {
    namePrefix: namePrefix
    env: env
    location: location
    tags: tags
    workspaceName: monitoring.outputs.workspaceName
    workspaceCustomerId: monitoring.outputs.workspaceCustomerId
    infrastructureSubnetId: network.?outputs.infrastructureSubnetId ?? ''
  }
}

// Managed identities + least-privilege data-plane grants for the API and workers.
module rbac 'modules/rbac.bicep' = {
  scope: rg
  name: 'rbac'
  params: {
    namePrefix: namePrefix
    env: env
    location: location
    tags: tags
    storageName: storage.outputs.name
    serviceBusNamespace: servicebus.outputs.namespace
    keyVaultName: keyvault.outputs.name
    acrName: acr.outputs.name
    deployAi: deployAi
    foundryName: ai.?outputs.foundryName ?? ''
    searchName: ai.?outputs.searchName ?? ''
    docIntelName: ai.?outputs.docIntelName ?? ''
  }
}

// --- Container Apps (API + workers) ---------------------------------------- //
module apps 'modules/apps.bicep' = {
  scope: rg
  name: 'apps'
  params: {
    namePrefix: namePrefix
    env: env
    location: location
    tags: tags
    environmentId: containerapps.outputs.environmentId
    acrLoginServer: acr.outputs.loginServer
    apiIdentityId: rbac.outputs.apiIdentityId
    apiIdentityClientId: rbac.outputs.apiIdentityClientId
    workerIdentityId: rbac.outputs.workerIdentityId
    workerIdentityClientId: rbac.outputs.workerIdentityClientId
    apiImage: apiImage
    workerImage: workerImage
    postgresFqdn: postgres.outputs.fqdn
    pgAdminLogin: pgAdminLogin
    pgAdminPassword: pgAdminPassword
    keyVaultUri: keyvault.outputs.uri
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    serviceBusNamespace: servicebus.outputs.namespace
    blobEndpoint: storage.outputs.blobEndpoint
    deployAi: deployAi
    foundryEndpoint: ai.?outputs.foundryEndpoint ?? ''
    searchEndpoint: ai.?outputs.searchEndpoint ?? ''
    docIntelEndpoint: ai.?outputs.docIntelEndpoint ?? ''
    contentSafetyEndpoint: ai.?outputs.contentSafetyEndpoint ?? ''
  }
}

// --- Private Endpoints (S5) — only when the networking layer is on ---------- //
module privateEndpoints 'modules/privateendpoints.bicep' = if (deployNetworking) {
  scope: rg
  name: 'privateEndpoints'
  params: {
    namePrefix: namePrefix
    env: env
    tags: tags
    vnetId: network.?outputs.vnetId ?? ''
    subnetId: network.?outputs.privateEndpointsSubnetId ?? ''
    storageName: storage.outputs.name
    keyVaultName: keyvault.outputs.name
    postgresServerName: postgres.outputs.serverName
    deployAi: deployAi
    searchName: ai.?outputs.searchName ?? ''
    foundryName: ai.?outputs.foundryName ?? ''
    docIntelName: ai.?outputs.docIntelName ?? ''
    contentSafetyName: ai.?outputs.contentSafetyName ?? ''
  }
}

// --- Edge / ops hardening (S5): Front Door + WAF, APIM, portal host, alerts -- //
module frontdoor 'modules/frontdoor.bicep' = if (deployEdge) {
  scope: rg
  name: 'frontdoor'
  params: {
    namePrefix: namePrefix
    env: env
    tags: tags
    originHostName: apps.outputs.apiFqdn
  }
}

module apim 'modules/apim.bicep' = if (deployEdge) {
  scope: rg
  name: 'apim'
  params: {
    namePrefix: namePrefix
    env: env
    location: location
    tags: tags
    publisherEmail: opsEmail
    apiBackendUrl: 'https://${apps.outputs.apiFqdn}'
  }
}

module appservice 'modules/appservice.bicep' = if (deployEdge) {
  scope: rg
  name: 'appservice'
  params: {
    namePrefix: namePrefix
    env: env
    location: location
    tags: tags
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    apiBaseUrl: 'https://${apps.outputs.apiFqdn}'
  }
}

module alerts 'modules/alerts.bicep' = if (deployEdge) {
  scope: rg
  name: 'alerts'
  params: {
    namePrefix: namePrefix
    env: env
    tags: tags
    appInsightsName: monitoring.outputs.appInsightsName
    alertEmail: opsEmail
  }
}

output resourceGroup string = rg.name
output keyVaultName string = keyvault.outputs.name
output acrLoginServer string = acr.outputs.loginServer
output postgresFqdn string = postgres.outputs.fqdn
output foundryEndpoint string = ai.?outputs.foundryEndpoint ?? ''
output searchEndpoint string = ai.?outputs.searchEndpoint ?? ''
output containerAppsEnvId string = containerapps.outputs.environmentId
output apiIdentityId string = rbac.outputs.apiIdentityId
output apiIdentityClientId string = rbac.outputs.apiIdentityClientId
output workerIdentityId string = rbac.outputs.workerIdentityId
output workerIdentityClientId string = rbac.outputs.workerIdentityClientId
output apiAppName string = apps.outputs.apiName
output migrateJobName string = apps.outputs.migrateJobName
output apiAppFqdn string = apps.outputs.apiFqdn
output apiAppUrl string = 'https://${apps.outputs.apiFqdn}'
output frontDoorHostName string = frontdoor.?outputs.endpointHostName ?? ''
output apimGatewayUrl string = apim.?outputs.gatewayUrl ?? ''
output portalHostName string = appservice.?outputs.portalDefaultHostName ?? ''

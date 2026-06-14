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
  }
}

output resourceGroup string = rg.name
output keyVaultName string = keyvault.outputs.name
output acrLoginServer string = acr.outputs.loginServer
output postgresFqdn string = postgres.outputs.fqdn
output foundryEndpoint string = ai.?outputs.foundryEndpoint ?? ''
output searchEndpoint string = ai.?outputs.searchEndpoint ?? ''
output containerAppsEnvId string = containerapps.outputs.environmentId

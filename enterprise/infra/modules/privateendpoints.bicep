// Private Endpoints + Private DNS zones + zone links for the data/AI plane (S5 hardening).
// Gated behind `deployNetworking` in main.bicep. Each AI endpoint is additionally gated on
// `deployAi`. Resources are referenced as `existing`; only the PE + DNS plumbing is created.
param namePrefix string
param env string
param location string = 'global'
param tags object

@description('Resource id of the VNet (for DNS zone links).')
param vnetId string
@description('Resource id of the private-endpoints subnet.')
param subnetId string

@description('Names of the already-deployed resources to wire privately.')
param storageName string
param keyVaultName string
param postgresServerName string

param deployAi bool = true
param searchName string = ''
param foundryName string = ''
param docIntelName string = ''
param contentSafetyName string = ''

// --- Private DNS zone names (Azure public cloud) --------------------------- //
var zones = {
  blob: 'privatelink.blob.${environment().suffixes.storage}'
  vault: 'privatelink.vaultcore.azure.net'
  postgres: 'privatelink.postgres.database.azure.com'
  search: 'privatelink.search.windows.net'
  cognitive: 'privatelink.cognitiveservices.azure.com'
}

// --- Existing target resources --------------------------------------------- //
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageName
}
resource kv 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}
resource pg 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' existing = {
  name: postgresServerName
}
resource search 'Microsoft.Search/searchServices@2024-06-01-preview' existing = if (deployAi) {
  name: searchName
}
resource foundry 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = if (deployAi) {
  name: foundryName
}
resource docIntel 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = if (deployAi) {
  name: docIntelName
}
resource contentSafety 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = if (deployAi) {
  name: contentSafetyName
}

// --- Private DNS zones ------------------------------------------------------ //
resource zBlob 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: zones.blob
  location: location
  tags: tags
}
resource zVault 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: zones.vault
  location: location
  tags: tags
}
resource zPostgres 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: zones.postgres
  location: location
  tags: tags
}
resource zSearch 'Microsoft.Network/privateDnsZones@2020-06-01' = if (deployAi) {
  name: zones.search
  location: location
  tags: tags
}
resource zCognitive 'Microsoft.Network/privateDnsZones@2020-06-01' = if (deployAi) {
  name: zones.cognitive
  location: location
  tags: tags
}

// --- VNet links ------------------------------------------------------------- //
resource linkBlob 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: zBlob
  name: 'link'
  location: location
  properties: { registrationEnabled: false, virtualNetwork: { id: vnetId } }
}
resource linkVault 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: zVault
  name: 'link'
  location: location
  properties: { registrationEnabled: false, virtualNetwork: { id: vnetId } }
}
resource linkPostgres 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: zPostgres
  name: 'link'
  location: location
  properties: { registrationEnabled: false, virtualNetwork: { id: vnetId } }
}
resource linkSearch 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = if (deployAi) {
  parent: zSearch
  name: 'link'
  location: location
  properties: { registrationEnabled: false, virtualNetwork: { id: vnetId } }
}
resource linkCognitive 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = if (deployAi) {
  parent: zCognitive
  name: 'link'
  location: location
  properties: { registrationEnabled: false, virtualNetwork: { id: vnetId } }
}

// --- Private endpoints (+ DNS zone groups) --------------------------------- //
resource peBlob 'Microsoft.Network/privateEndpoints@2023-11-01' = {
  name: '${namePrefix}-${env}-pe-blob'
  location: az.resourceGroup().location
  tags: tags
  properties: {
    subnet: { id: subnetId }
    privateLinkServiceConnections: [
      {
        name: 'blob'
        properties: {
          privateLinkServiceId: storage.id
          groupIds: [ 'blob' ]
        }
      }
    ]
  }
}
resource peBlobDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = {
  parent: peBlob
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      { name: 'blob', properties: { privateDnsZoneId: zBlob.id } }
    ]
  }
}

resource peVault 'Microsoft.Network/privateEndpoints@2023-11-01' = {
  name: '${namePrefix}-${env}-pe-kv'
  location: az.resourceGroup().location
  tags: tags
  properties: {
    subnet: { id: subnetId }
    privateLinkServiceConnections: [
      {
        name: 'vault'
        properties: {
          privateLinkServiceId: kv.id
          groupIds: [ 'vault' ]
        }
      }
    ]
  }
}
resource peVaultDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = {
  parent: peVault
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      { name: 'vault', properties: { privateDnsZoneId: zVault.id } }
    ]
  }
}

resource pePostgres 'Microsoft.Network/privateEndpoints@2023-11-01' = {
  name: '${namePrefix}-${env}-pe-pg'
  location: az.resourceGroup().location
  tags: tags
  properties: {
    subnet: { id: subnetId }
    privateLinkServiceConnections: [
      {
        name: 'postgres'
        properties: {
          privateLinkServiceId: pg.id
          groupIds: [ 'postgresqlServer' ]
        }
      }
    ]
  }
}
resource pePostgresDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = {
  parent: pePostgres
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      { name: 'postgres', properties: { privateDnsZoneId: zPostgres.id } }
    ]
  }
}

resource peSearch 'Microsoft.Network/privateEndpoints@2023-11-01' = if (deployAi) {
  name: '${namePrefix}-${env}-pe-search'
  location: az.resourceGroup().location
  tags: tags
  properties: {
    subnet: { id: subnetId }
    privateLinkServiceConnections: [
      {
        name: 'search'
        properties: {
          privateLinkServiceId: deployAi ? search.id : ''
          groupIds: [ 'searchService' ]
        }
      }
    ]
  }
}
resource peSearchDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = if (deployAi) {
  parent: peSearch
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      { name: 'search', properties: { privateDnsZoneId: zSearch.id } }
    ]
  }
}

resource peFoundry 'Microsoft.Network/privateEndpoints@2023-11-01' = if (deployAi) {
  name: '${namePrefix}-${env}-pe-foundry'
  location: az.resourceGroup().location
  tags: tags
  properties: {
    subnet: { id: subnetId }
    privateLinkServiceConnections: [
      {
        name: 'foundry'
        properties: {
          privateLinkServiceId: deployAi ? foundry.id : ''
          groupIds: [ 'account' ]
        }
      }
    ]
  }
}
resource peFoundryDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = if (deployAi) {
  parent: peFoundry
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      { name: 'cognitive', properties: { privateDnsZoneId: zCognitive.id } }
    ]
  }
}

resource peDocIntel 'Microsoft.Network/privateEndpoints@2023-11-01' = if (deployAi) {
  name: '${namePrefix}-${env}-pe-docintel'
  location: az.resourceGroup().location
  tags: tags
  properties: {
    subnet: { id: subnetId }
    privateLinkServiceConnections: [
      {
        name: 'docintel'
        properties: {
          privateLinkServiceId: deployAi ? docIntel.id : ''
          groupIds: [ 'account' ]
        }
      }
    ]
  }
}
resource peDocIntelDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = if (deployAi) {
  parent: peDocIntel
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      { name: 'cognitive', properties: { privateDnsZoneId: zCognitive.id } }
    ]
  }
}

resource peSafety 'Microsoft.Network/privateEndpoints@2023-11-01' = if (deployAi) {
  name: '${namePrefix}-${env}-pe-safety'
  location: az.resourceGroup().location
  tags: tags
  properties: {
    subnet: { id: subnetId }
    privateLinkServiceConnections: [
      {
        name: 'safety'
        properties: {
          privateLinkServiceId: deployAi ? contentSafety.id : ''
          groupIds: [ 'account' ]
        }
      }
    ]
  }
}
resource peSafetyDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = if (deployAi) {
  parent: peSafety
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      { name: 'cognitive', properties: { privateDnsZoneId: zCognitive.id } }
    ]
  }
}

// Key Vault with RBAC authorization. Admin object id gets Key Vault Administrator
// for bootstrap; services read secrets via Managed Identity + Key Vault Secrets User.
param namePrefix string
param env string
param location string
param tags object
param adminObjectId string

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: '${namePrefix}-${env}-kv'
  location: location
  tags: tags
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: env == 'prod' ? 90 : 7
    enablePurgeProtection: env == 'prod' ? true : null
    publicNetworkAccess: 'Enabled' // tighten to private endpoint in S5 hardening
  }
}

// Key Vault Administrator role
var kvAdminRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '00482a5a-887f-4fb3-b363-3b7fe8e74483')

resource adminRa 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: kv
  name: guid(kv.id, adminObjectId, kvAdminRole)
  properties: {
    roleDefinitionId: kvAdminRole
    principalId: adminObjectId
    principalType: 'User'
  }
}

output name string = kv.name
output uri string = kv.properties.vaultUri

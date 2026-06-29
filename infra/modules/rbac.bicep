// Managed identities + data-plane role assignments (SCOPING §3.3, §7, §9, §13).
//
// The API and the workers authenticate to Azure data services with NO keys — only
// Managed Identity. Because the container apps themselves are deployed later by CI/CD,
// we create two *user-assigned* identities here and grant them least-privilege data-plane
// roles now; the container apps simply reference these identities once their images exist.
//
//   API identity    → write policy/receipt blobs, enqueue ingestion messages, read secrets
//   Worker identity → read blobs, run Doc Intelligence + Foundry embeddings, write the
//                     AI Search index, receive Service Bus messages
//
// Scope each assignment to the specific resource (never the whole RG) so the grant is
// exactly the surface the workload needs.
param namePrefix string
param env string
param location string
param tags object

@description('Storage account name (from storage module output).')
param storageName string

@description('Service Bus namespace name (from servicebus module output).')
param serviceBusNamespace string

@description('Key Vault name (from keyvault module output).')
param keyVaultName string

@description('Container Registry name (from acr module output) — for AcrPull grants.')
param acrName string

@description('Whether the AI layer (Foundry/Search/DocIntel) was deployed — gates those grants.')
param deployAi bool = true

@description('AI resource names (from ai module). Ignored when deployAi is false.')
param foundryName string = ''
param searchName string = ''
param docIntelName string = ''

// --- Built-in role definition IDs (stable GUIDs) --------------------------- //
var roles = {
  blobContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor
  blobReader: '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1' // Storage Blob Data Reader
  sbSender: '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39' // Azure Service Bus Data Sender
  sbReceiver: '4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0' // Azure Service Bus Data Receiver
  searchIndexContributor: '8ebe5a00-799e-43f5-93ac-243d3dce84a7' // Search Index Data Contributor
  cognitiveUser: 'a97b65f3-24c7-4388-baec-2e87135dc908' // Cognitive Services User
  kvSecretsUser: '4633458b-17de-408a-b874-0445c86b69e6' // Key Vault Secrets User
  acrPull: '7f951dda-4ed3-4680-a7ca-43fe172d538d' // AcrPull
}

// --- User-assigned managed identities -------------------------------------- //
resource apiId 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${namePrefix}-${env}-api-id'
  location: location
  tags: tags
}

resource workerId 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${namePrefix}-${env}-worker-id'
  location: location
  tags: tags
}

// --- Existing target resources (referenced for scoping the grants) --------- //
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageName
}

resource bus 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' existing = {
  name: serviceBusNamespace
}

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' existing = {
  name: acrName
}

resource foundry 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = if (deployAi) {
  name: foundryName
}

resource docIntel 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = if (deployAi) {
  name: docIntelName
}

resource search 'Microsoft.Search/searchServices@2024-06-01-preview' existing = if (deployAi) {
  name: searchName
}

// --- API identity grants --------------------------------------------------- //
resource apiBlob 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, apiId.id, roles.blobContributor)
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.blobContributor)
    principalId: apiId.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource apiSbSend 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(bus.id, apiId.id, roles.sbSender)
  scope: bus
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.sbSender)
    principalId: apiId.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource apiKv 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kv.id, apiId.id, roles.kvSecretsUser)
  scope: kv
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.kvSecretsUser)
    principalId: apiId.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// --- ACR pull grants (both identities pull their images from ACR) ---------- //
resource apiAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, apiId.id, roles.acrPull)
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.acrPull)
    principalId: apiId.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource workerAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, workerId.id, roles.acrPull)
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.acrPull)
    principalId: workerId.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// --- Worker identity grants ------------------------------------------------ //
resource workerBlob 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, workerId.id, roles.blobReader)
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.blobReader)
    principalId: workerId.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource workerSbReceive 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(bus.id, workerId.id, roles.sbReceiver)
  scope: bus
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.sbReceiver)
    principalId: workerId.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource workerKv 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kv.id, workerId.id, roles.kvSecretsUser)
  scope: kv
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.kvSecretsUser)
    principalId: workerId.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// --- Worker AI grants (only when the AI layer is deployed) ----------------- //
resource workerSearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployAi) {
  name: guid(search.id, workerId.id, roles.searchIndexContributor)
  scope: search
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.searchIndexContributor)
    principalId: workerId.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource workerFoundry 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployAi) {
  name: guid(foundry.id, workerId.id, roles.cognitiveUser)
  scope: foundry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.cognitiveUser)
    principalId: workerId.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource workerDocIntel 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployAi) {
  name: guid(docIntel.id, workerId.id, roles.cognitiveUser)
  scope: docIntel
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.cognitiveUser)
    principalId: workerId.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// --- Outputs (CI/CD attaches these identities to the container apps) ------- //
output apiIdentityId string = apiId.id
output apiIdentityClientId string = apiId.properties.clientId
output apiIdentityPrincipalId string = apiId.properties.principalId
output workerIdentityId string = workerId.id
output workerIdentityClientId string = workerId.properties.clientId
output workerIdentityPrincipalId string = workerId.properties.principalId

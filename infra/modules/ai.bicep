// AI layer (SCOPING §11): Azure AI Foundry (chat + embedding deployments),
// Document Intelligence (prebuilt receipt model), Content Safety (Prompt Shields),
// and Azure AI Search (security-trimmed RAG index). Keys are disabled where the
// SDK supports Entra/Managed-Identity auth; everything is referenced by endpoint.
param namePrefix string
param env string
param location string
param tags object

@description('Chat model + version to deploy in Foundry (pin per SCOPING §11.2)')
param chatModel object = { name: 'gpt-4o', version: '2024-11-20', capacity: 20 }

@description('Embedding model + version to deploy in Foundry')
param embeddingModel object = { name: 'text-embedding-3-large', version: '1', capacity: 20 }

// ---------------------------------------------------------------------------
// Azure AI Foundry — multi-service AIServices account hosting model deployments.
// "No training on your data" is the platform default for these resources.
resource foundry 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: '${namePrefix}-${env}-aifoundry'
  location: location
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: '${namePrefix}-${env}-aifoundry'
    publicNetworkAccess: 'Enabled' // tighten to private endpoint in S5 hardening
    disableLocalAuth: false        // flip to true once all callers use Managed Identity
  }
}

// Model deployments must serialize (control-plane allows one mutation at a time).
resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: foundry
  name: chatModel.name
  sku: { name: 'Standard', capacity: chatModel.capacity }
  properties: {
    model: { format: 'OpenAI', name: chatModel.name, version: chatModel.version }
  }
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: foundry
  name: embeddingModel.name
  dependsOn: [ chatDeployment ]
  sku: { name: 'Standard', capacity: embeddingModel.capacity }
  properties: {
    model: { format: 'OpenAI', name: embeddingModel.name, version: embeddingModel.version }
  }
}

// ---------------------------------------------------------------------------
// Document Intelligence — prebuilt receipt/invoice extraction (SCOPING §4.2).
resource docIntel 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: '${namePrefix}-${env}-docintel'
  location: location
  tags: tags
  kind: 'FormRecognizer'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: '${namePrefix}-${env}-docintel'
    publicNetworkAccess: 'Enabled'
  }
}

// ---------------------------------------------------------------------------
// Content Safety — Prompt Shields / jailbreak detection on LLM I/O (SCOPING §12).
resource contentSafety 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: '${namePrefix}-${env}-safety'
  location: location
  tags: tags
  kind: 'ContentSafety'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: '${namePrefix}-${env}-safety'
    publicNetworkAccess: 'Enabled'
  }
}

// ---------------------------------------------------------------------------
// Azure AI Search — vector + keyword index for document RAG. Security-trimming
// fields (owner/role-scope) are enforced at query time, not just stored.
resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: '${namePrefix}-${env}-search'
  location: location
  tags: tags
  sku: { name: env == 'prod' ? 'standard' : 'basic' }
  identity: { type: 'SystemAssigned' }
  properties: {
    replicaCount: env == 'prod' ? 2 : 1
    partitionCount: 1
    hostingMode: 'default'
    semanticSearch: 'standard'
    publicNetworkAccess: 'Enabled'
    authOptions: { aadOrApiKey: { aadAuthFailureMode: 'http401WithBearerChallenge' } }
  }
}

output foundryEndpoint string = foundry.properties.endpoint
output foundryName string = foundry.name
output chatDeploymentName string = chatDeployment.name
output embeddingDeploymentName string = embeddingDeployment.name
output docIntelEndpoint string = docIntel.properties.endpoint
output docIntelName string = docIntel.name
output contentSafetyEndpoint string = contentSafety.properties.endpoint
output searchEndpoint string = 'https://${search.name}.search.windows.net'
output searchName string = search.name

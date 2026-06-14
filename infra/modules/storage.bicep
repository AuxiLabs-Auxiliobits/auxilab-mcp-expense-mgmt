// Blob storage for uploaded receipts/documents. Containers are ACL-tagged at the app
// layer (owner/role-scope); blobs are virus-scanned before processing (SCOPING §4.2).
param namePrefix string
param env string
param location string
param tags object

resource sa 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: toLower(replace('${namePrefix}${env}sa', '-', ''))
  location: location
  tags: tags
  sku: { name: env == 'prod' ? 'Standard_ZRS' : 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: 'Enabled' // tighten to private endpoint in S5 hardening
  }
}

resource blob 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: sa
  name: 'default'
  properties: {
    deleteRetentionPolicy: { enabled: true, days: 14 }
  }
}

resource receipts 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blob
  name: 'receipts'
  properties: { publicAccess: 'None' }
}

resource documents 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blob
  name: 'documents'
  properties: { publicAccess: 'None' }
}

// Agency finance-policy documents uploaded by Finance, ingested into the RAG index
// (SCOPING §7). Read by the ingestion worker (Blob Data Reader), written by the API
// (Blob Data Contributor) — both via Managed Identity.
resource agencyPolicies 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blob
  name: 'agency-policies'
  properties: { publicAccess: 'None' }
}

output name string = sa.name
output blobEndpoint string = sa.properties.primaryEndpoints.blob

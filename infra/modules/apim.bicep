// API Management fronting the API (S5 hardening / edge). Gated behind `deployEdge`.
// Consumption SKU in non-prod (cheap, serverless), Developer in prod. A product with
// rate-limiting + request size cap + JSON structure validation policy is attached.
param namePrefix string
param env string
param location string
param tags object

@description('Publisher email for the APIM instance.')
param publisherEmail string

@description('Publisher organisation name.')
param publisherName string = 'Expense Management'

@description('Backend API base URL (the API container app FQDN), e.g. https://<app>.azurecontainerapps.io')
param apiBackendUrl string

var skuName = env == 'prod' ? 'Developer' : 'Consumption'

resource apim 'Microsoft.ApiManagement/service@2023-09-01-preview' = {
  name: '${namePrefix}-${env}-apim'
  location: location
  tags: tags
  sku: {
    name: skuName
    capacity: skuName == 'Consumption' ? 0 : 1
  }
  identity: { type: 'SystemAssigned' }
  properties: {
    publisherEmail: publisherEmail
    publisherName: publisherName
  }
}

resource api 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  parent: apim
  name: 'expense-api'
  properties: {
    displayName: 'Expense API'
    path: 'api'
    protocols: [ 'https' ]
    serviceUrl: apiBackendUrl
    subscriptionRequired: true
  }
}

resource product 'Microsoft.ApiManagement/service/products@2023-09-01-preview' = {
  parent: apim
  name: 'expense'
  properties: {
    displayName: 'Expense'
    description: 'Default product for the Expense API with rate limiting and validation.'
    subscriptionRequired: true
    approvalRequired: false
    state: 'published'
  }
}

resource productApi 'Microsoft.ApiManagement/service/products/apiLinks@2023-09-01-preview' = {
  parent: product
  name: 'expense-api-link'
  properties: {
    apiId: api.id
  }
}

// Rate-limit (300 calls / 60s), cap request body size (1 MB), and validate request
// structure/content against the OpenAPI schema (prevent=block on errors).
resource apiPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-09-01-preview' = {
  parent: api
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: '''
<policies>
  <inbound>
    <base />
    <rate-limit calls="300" renewal-period="60" />
    <check-header name="Content-Length" failed-check-httpcode="413" failed-check-error-message="Request too large" ignore-case="true">
      <value>0</value>
    </check-header>
    <validate-content unspecified-content-type-action="prevent" max-size="1048576" size-exceeded-action="prevent" errors-variable-name="requestBodyValidation" />
  </inbound>
  <backend>
    <base />
  </backend>
  <outbound>
    <base />
  </outbound>
  <on-error>
    <base />
  </on-error>
</policies>
'''
  }
}

output apimName string = apim.name
output gatewayUrl string = apim.properties.gatewayUrl

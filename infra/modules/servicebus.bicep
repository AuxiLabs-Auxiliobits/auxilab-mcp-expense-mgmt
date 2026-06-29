// Azure Service Bus — async ingestion & batch claim processing, with dead-letter.
param namePrefix string
param env string
param location string
param tags object

// Note: namespace names ending in '-sb' are reserved by Azure, so we use '-bus'.
resource sb 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: '${namePrefix}-${env}-bus'
  location: location
  tags: tags
  sku: { name: env == 'prod' ? 'Standard' : 'Basic' }
}

resource ingestion 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: sb
  name: 'document-ingestion'
  properties: {
    maxDeliveryCount: 5
    deadLetteringOnMessageExpiration: true
    lockDuration: 'PT5M'
  }
}

resource batch 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: sb
  name: 'claim-batch'
  properties: {
    maxDeliveryCount: 5
    deadLetteringOnMessageExpiration: true
    lockDuration: 'PT5M'
  }
}

// Finance-approval queue consumed by the finance worker (SCOPING §11, §14). The worker
// scales on this queue's length (KEDA azure-servicebus scaler).
resource financeApproval 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: sb
  name: 'finance-approval'
  properties: {
    maxDeliveryCount: 5
    deadLetteringOnMessageExpiration: true
    lockDuration: 'PT5M'
  }
}

output namespace string = sb.name

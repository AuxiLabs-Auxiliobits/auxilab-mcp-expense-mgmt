// Azure Managed Redis (redisEnterprise) — caching, sessions, broker (SCOPING §8).
// Classic "Azure Cache for Redis" (Microsoft.Cache/redis) is retired for new creates,
// so we use the Managed Redis Balanced tier (B0 in dev, larger in prod).
param namePrefix string
param env string
param location string
param tags object

resource redis 'Microsoft.Cache/redisEnterprise@2024-10-01' = {
  name: '${namePrefix}-${env}-redis'
  location: location
  tags: tags
  sku: {
    name: env == 'prod' ? 'Balanced_B3' : 'Balanced_B0'
  }
  properties: {
    minimumTlsVersion: '1.2'
  }
}

resource db 'Microsoft.Cache/redisEnterprise/databases@2024-10-01' = {
  parent: redis
  name: 'default'
  properties: {
    clientProtocol: 'Encrypted'      // TLS-only
    clusteringPolicy: 'OSSCluster'
    evictionPolicy: 'NoEviction'
    port: 10000
  }
}

output hostName string = redis.properties.hostName

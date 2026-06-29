// Azure Database for PostgreSQL Flexible Server. Zone-redundant HA in prod.
// Private networking + PITR tuning land in S5 hardening.
param namePrefix string
param env string
param location string
param tags object
param adminLogin string
@secure()
param adminPassword string

resource pg 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: '${namePrefix}-${env}-pg'
  location: location
  tags: tags
  sku: {
    name: env == 'prod' ? 'Standard_D2ds_v5' : 'Standard_B1ms'
    tier: env == 'prod' ? 'GeneralPurpose' : 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: adminLogin
    administratorLoginPassword: adminPassword
    storage: { storageSizeGB: 32 }
    backup: {
      backupRetentionDays: env == 'prod' ? 35 : 7
      geoRedundantBackup: env == 'prod' ? 'Enabled' : 'Disabled'
    }
    highAvailability: {
      mode: env == 'prod' ? 'ZoneRedundant' : 'Disabled'
    }
  }
}

resource db 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: pg
  name: 'expense'
  properties: { charset: 'UTF8', collation: 'en_US.utf8' }
}

output fqdn string = pg.properties.fullyQualifiedDomainName
output serverName string = pg.name

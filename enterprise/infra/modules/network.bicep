// VNet + subnets + NSGs for the hardened (S5) topology. Gated behind `deployNetworking`
// in main.bicep — dev stays public/flat by default. Subnets:
//   - container-apps infrastructure subnet (/23, delegated to Microsoft.App/environments)
//   - private-endpoints subnet (for Storage/KV/PG/Search/Cognitive private endpoints)
//   - data subnet (PostgreSQL flexible-server delegation reserve)
param namePrefix string
param env string
param location string
param tags object

@description('VNet address space.')
param addressPrefix string = '10.20.0.0/16'

var caeSubnetPrefix = '10.20.0.0/23' // /23 required by Container Apps managed env
var peSubnetPrefix = '10.20.2.0/24'
var dataSubnetPrefix = '10.20.3.0/24'

resource nsgApps 'Microsoft.Network/networkSecurityGroups@2023-11-01' = {
  name: '${namePrefix}-${env}-nsg-apps'
  location: location
  tags: tags
  properties: {
    securityRules: []
  }
}

resource nsgData 'Microsoft.Network/networkSecurityGroups@2023-11-01' = {
  name: '${namePrefix}-${env}-nsg-data'
  location: location
  tags: tags
  properties: {
    securityRules: []
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2023-11-01' = {
  name: '${namePrefix}-${env}-vnet'
  location: location
  tags: tags
  properties: {
    addressSpace: { addressPrefixes: [ addressPrefix ] }
    subnets: [
      {
        name: 'container-apps'
        properties: {
          addressPrefix: caeSubnetPrefix
          networkSecurityGroup: { id: nsgApps.id }
          delegations: [
            {
              name: 'cae-delegation'
              properties: { serviceName: 'Microsoft.App/environments' }
            }
          ]
        }
      }
      {
        name: 'private-endpoints'
        properties: {
          addressPrefix: peSubnetPrefix
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
      {
        name: 'data'
        properties: {
          addressPrefix: dataSubnetPrefix
          networkSecurityGroup: { id: nsgData.id }
        }
      }
    ]
  }
}

output vnetId string = vnet.id
output vnetName string = vnet.name
output infrastructureSubnetId string = vnet.properties.subnets[0].id
output privateEndpointsSubnetId string = vnet.properties.subnets[1].id
output dataSubnetId string = vnet.properties.subnets[2].id

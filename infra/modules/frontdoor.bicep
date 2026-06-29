// Azure Front Door Standard/Premium + WAF (managed rule set) fronting the API container app
// (S5 hardening / edge). Gated behind `deployEdge` in main.bicep.
param namePrefix string
param env string
param tags object

@description('FQDN of the API container app to use as the Front Door origin.')
param originHostName string

var profileName = '${namePrefix}-${env}-afd'
var skuName = env == 'prod' ? 'Premium_AzureFrontDoor' : 'Standard_AzureFrontDoor'

resource profile 'Microsoft.Cdn/profiles@2024-02-01' = {
  name: profileName
  location: 'global'
  tags: tags
  sku: { name: skuName }
}

resource waf 'Microsoft.Network/FrontDoorWebApplicationFirewallPolicies@2024-02-01' = {
  name: toLower(replace('${namePrefix}${env}wafpolicy', '-', ''))
  location: 'global'
  tags: tags
  sku: { name: skuName }
  properties: {
    policySettings: {
      enabledState: 'Enabled'
      mode: env == 'prod' ? 'Prevention' : 'Detection'
    }
    managedRules: {
      managedRuleSets: [
        {
          ruleSetType: 'Microsoft_DefaultRuleSet'
          ruleSetVersion: '2.1'
        }
      ]
    }
  }
}

resource endpoint 'Microsoft.Cdn/profiles/afdEndpoints@2024-02-01' = {
  parent: profile
  name: '${namePrefix}-${env}-api'
  location: 'global'
  tags: tags
  properties: { enabledState: 'Enabled' }
}

resource originGroup 'Microsoft.Cdn/profiles/originGroups@2024-02-01' = {
  parent: profile
  name: 'api-origin-group'
  properties: {
    loadBalancingSettings: {
      sampleSize: 4
      successfulSamplesRequired: 3
      additionalLatencyInMilliseconds: 50
    }
    healthProbeSettings: {
      probePath: '/health'
      probeRequestType: 'GET'
      probeProtocol: 'Https'
      probeIntervalInSeconds: 60
    }
  }
}

resource origin 'Microsoft.Cdn/profiles/originGroups/origins@2024-02-01' = {
  parent: originGroup
  name: 'api-origin'
  properties: {
    hostName: originHostName
    originHostHeader: originHostName
    httpPort: 80
    httpsPort: 443
    priority: 1
    weight: 1000
    enabledState: 'Enabled'
  }
}

resource route 'Microsoft.Cdn/profiles/afdEndpoints/routes@2024-02-01' = {
  parent: endpoint
  name: 'api-route'
  dependsOn: [ origin ]
  properties: {
    originGroup: { id: originGroup.id }
    supportedProtocols: [ 'Https' ]
    patternsToMatch: [ '/*' ]
    forwardingProtocol: 'HttpsOnly'
    httpsRedirect: 'Enabled'
    linkToDefaultDomain: 'Enabled'
  }
}

resource securityPolicy 'Microsoft.Cdn/profiles/securityPolicies@2024-02-01' = {
  parent: profile
  name: 'waf-policy'
  properties: {
    parameters: {
      type: 'WebApplicationFirewall'
      wafPolicy: { id: waf.id }
      associations: [
        {
          domains: [ { id: endpoint.id } ]
          patternsToMatch: [ '/*' ]
        }
      ]
    }
  }
}

output endpointHostName string = endpoint.properties.hostName
output profileName string = profile.name

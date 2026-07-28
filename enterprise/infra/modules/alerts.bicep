// Action Group + metric alerts on the API's Application Insights component (S5 / ops).
// Gated behind `deployEdge` in main.bicep. Alerts: server failure rate, high latency,
// and low availability.
param namePrefix string
param env string
param tags object

@description('Name of the Application Insights component to alert on.')
param appInsightsName string

@description('Email address that receives alert notifications.')
param alertEmail string

resource appi 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: '${namePrefix}-${env}-ag'
  location: 'global'
  tags: tags
  properties: {
    groupShortName: 'expmgmt'
    enabled: true
    emailReceivers: [
      {
        name: 'ops'
        emailAddress: alertEmail
        useCommonAlertSchema: true
      }
    ]
  }
}

resource failureRate 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${namePrefix}-${env}-alert-failures'
  location: 'global'
  tags: tags
  properties: {
    severity: 2
    enabled: true
    scopes: [ appi.id ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'FailedRequests'
          metricNamespace: 'microsoft.insights/components'
          metricName: 'requests/failed'
          operator: 'GreaterThan'
          threshold: 10
          timeAggregation: 'Count'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [ { actionGroupId: actionGroup.id } ]
  }
}

resource highLatency 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${namePrefix}-${env}-alert-latency'
  location: 'global'
  tags: tags
  properties: {
    severity: 3
    enabled: true
    scopes: [ appi.id ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'ServerResponseTime'
          metricNamespace: 'microsoft.insights/components'
          metricName: 'requests/duration'
          operator: 'GreaterThan'
          threshold: 3000
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [ { actionGroupId: actionGroup.id } ]
  }
}

resource lowAvailability 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${namePrefix}-${env}-alert-availability'
  location: 'global'
  tags: tags
  properties: {
    severity: 1
    enabled: true
    scopes: [ appi.id ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'AvailabilityPercentage'
          metricNamespace: 'microsoft.insights/components'
          metricName: 'availabilityResults/availabilityPercentage'
          operator: 'LessThan'
          threshold: 99
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [ { actionGroupId: actionGroup.id } ]
  }
}

output actionGroupId string = actionGroup.id

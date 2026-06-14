using './main.bicep'

param env = 'dev'
param location = 'centralindia'
param namePrefix = 'expmgmt'

// Content Safety (and some models) aren't offered in centralindia — keep AI in a supported region.
param aiLocation = 'eastus'
// Set to false to deploy everything EXCEPT the AI layer (useful for a first run / quota checks).
param deployAi = true

// Object ID of the user/service principal running the deployment (az ad signed-in-user).
param adminObjectId = 'cd178d64-97c2-4d46-89a4-f3313ac8e287'

param pgAdminLogin = 'pgadmin'
// Do NOT commit a real password. Pass at deploy time:
//   --parameters pgAdminPassword=$(...)  or pull from Key Vault.
param pgAdminPassword = '<REPLACE-or-pass-at-deploy-time>'

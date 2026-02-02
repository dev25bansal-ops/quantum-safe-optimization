# Azure Key Vault for secrets management
# Stores PQC signing keys, API secrets, and Cosmos DB credentials

# Key Vault
resource "azurerm_key_vault" "main" {
  name                = "${var.resource_prefix}-${var.environment}-kv"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  # Enable soft delete and purge protection for production
  soft_delete_retention_days = 90
  purge_protection_enabled   = var.environment == "prod"

  # Enable RBAC authorization
  enable_rbac_authorization = true

  # Network rules
  network_acls {
    default_action = var.environment == "prod" ? "Deny" : "Allow"
    bypass         = "AzureServices"
  }

  tags = local.tags
}

# Data source for current client
data "azurerm_client_config" "current" {}

# Store Cosmos DB primary key in Key Vault
resource "azurerm_key_vault_secret" "cosmos_key" {
  name         = "cosmos-primary-key"
  value        = azurerm_cosmosdb_account.main.primary_key
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [
    azurerm_role_assignment.kv_secrets_officer
  ]
}

# Store Cosmos DB connection string
resource "azurerm_key_vault_secret" "cosmos_connection" {
  name         = "cosmos-connection-string"
  value        = azurerm_cosmosdb_account.main.primary_sql_connection_string
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [
    azurerm_role_assignment.kv_secrets_officer
  ]
}

# Role assignment for Terraform to manage secrets
resource "azurerm_role_assignment" "kv_secrets_officer" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

# JWT secret for token signing (backup to PQC)
resource "azurerm_key_vault_secret" "jwt_secret" {
  name         = "jwt-secret"
  value        = random_password.jwt_secret.result
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [
    azurerm_role_assignment.kv_secrets_officer
  ]
}

resource "random_password" "jwt_secret" {
  length  = 64
  special = true
}

# Outputs
output "key_vault_uri" {
  description = "Key Vault URI"
  value       = azurerm_key_vault.main.vault_uri
}

output "key_vault_name" {
  description = "Key Vault name"
  value       = azurerm_key_vault.main.name
}

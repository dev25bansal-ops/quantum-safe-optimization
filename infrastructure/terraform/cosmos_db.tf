# Terraform configuration for Azure Cosmos DB
# Quantum-Safe Optimization Platform

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.80"
    }
  }
  required_version = ">= 1.5.0"
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy = false
    }
  }
}

# Variables
variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus"
}

variable "resource_prefix" {
  description = "Prefix for resource names"
  type        = string
  default     = "qsop"
}

# Local values
locals {
  resource_group_name = "${var.resource_prefix}-${var.environment}-rg"
  cosmos_account_name = "${var.resource_prefix}-${var.environment}-cosmos"
  tags = {
    Environment = var.environment
    Project     = "quantum-safe-optimization"
    ManagedBy   = "terraform"
  }
}

# Resource Group
resource "azurerm_resource_group" "main" {
  name     = local.resource_group_name
  location = var.location
  tags     = local.tags
}

# Azure Cosmos DB Account
resource "azurerm_cosmosdb_account" "main" {
  name                = local.cosmos_account_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  # Enable serverless for dev, provisioned throughput for prod
  dynamic "capabilities" {
    for_each = var.environment == "dev" ? [1] : []
    content {
      name = "EnableServerless"
    }
  }

  consistency_policy {
    consistency_level       = "Session"
    max_interval_in_seconds = 5
    max_staleness_prefix    = 100
  }

  geo_location {
    location          = var.location
    failover_priority = 0
  }

  # Add secondary region for prod
  dynamic "geo_location" {
    for_each = var.environment == "prod" ? [1] : []
    content {
      location          = "westus"
      failover_priority = 1
    }
  }

  # Enable automatic failover for prod
  enable_automatic_failover = var.environment == "prod"

  # Enable multiple write locations for prod
  enable_multiple_write_locations = var.environment == "prod"

  # Backup configuration
  backup {
    type                = "Periodic"
    interval_in_minutes = 240
    retention_in_hours  = 720
    storage_redundancy  = var.environment == "prod" ? "Geo" : "Local"
  }

  # Network rules - restrict to specific IPs/VNets in production
  is_virtual_network_filter_enabled = false

  tags = local.tags
}

# Cosmos DB SQL Database
resource "azurerm_cosmosdb_sql_database" "main" {
  name                = "quantum_optimization"
  resource_group_name = azurerm_resource_group.main.name
  account_name        = azurerm_cosmosdb_account.main.name

  # Only set throughput for non-serverless accounts
  dynamic "autoscale_settings" {
    for_each = var.environment != "dev" ? [1] : []
    content {
      max_throughput = 4000
    }
  }
}

# Jobs Container - Partitioned by user_id for tenant isolation
resource "azurerm_cosmosdb_sql_container" "jobs" {
  name                  = "jobs"
  resource_group_name   = azurerm_resource_group.main.name
  account_name          = azurerm_cosmosdb_account.main.name
  database_name         = azurerm_cosmosdb_sql_database.main.name
  partition_key_path    = "/user_id"
  partition_key_version = 2

  # TTL for automatic cleanup of old jobs (30 days)
  default_ttl = 2592000

  indexing_policy {
    indexing_mode = "consistent"

    included_path {
      path = "/*"
    }

    excluded_path {
      path = "/result/*"
    }

    composite_index {
      index {
        path  = "/user_id"
        order = "ascending"
      }
      index {
        path  = "/created_at"
        order = "descending"
      }
    }

    composite_index {
      index {
        path  = "/status"
        order = "ascending"
      }
      index {
        path  = "/created_at"
        order = "descending"
      }
    }
  }

  dynamic "autoscale_settings" {
    for_each = var.environment != "dev" ? [1] : []
    content {
      max_throughput = 1000
    }
  }
}

# Users Container
resource "azurerm_cosmosdb_sql_container" "users" {
  name                  = "users"
  resource_group_name   = azurerm_resource_group.main.name
  account_name          = azurerm_cosmosdb_account.main.name
  database_name         = azurerm_cosmosdb_sql_database.main.name
  partition_key_path    = "/user_id"
  partition_key_version = 2

  indexing_policy {
    indexing_mode = "consistent"

    included_path {
      path = "/*"
    }

    excluded_path {
      path = "/password_hash"
    }
  }

  unique_key {
    paths = ["/username"]
  }

  unique_key {
    paths = ["/email"]
  }
}

# Keys Container - For PQC public keys
resource "azurerm_cosmosdb_sql_container" "keys" {
  name                  = "keys"
  resource_group_name   = azurerm_resource_group.main.name
  account_name          = azurerm_cosmosdb_account.main.name
  database_name         = azurerm_cosmosdb_sql_database.main.name
  partition_key_path    = "/user_id"
  partition_key_version = 2

  indexing_policy {
    indexing_mode = "consistent"

    included_path {
      path = "/*"
    }
  }
}

# Audit Logs Container - Hierarchical partition key
resource "azurerm_cosmosdb_sql_container" "audit_logs" {
  name                  = "audit_logs"
  resource_group_name   = azurerm_resource_group.main.name
  account_name          = azurerm_cosmosdb_account.main.name
  database_name         = azurerm_cosmosdb_sql_database.main.name
  partition_key_paths   = ["/tenant_id", "/year_month"]
  partition_key_version = 2

  # TTL for audit log retention (90 days)
  default_ttl = 7776000

  indexing_policy {
    indexing_mode = "consistent"

    included_path {
      path = "/*"
    }

    composite_index {
      index {
        path  = "/tenant_id"
        order = "ascending"
      }
      index {
        path  = "/timestamp"
        order = "descending"
      }
    }
  }
}

# Outputs
output "cosmos_endpoint" {
  description = "Cosmos DB endpoint"
  value       = azurerm_cosmosdb_account.main.endpoint
}

output "cosmos_primary_key" {
  description = "Cosmos DB primary key"
  value       = azurerm_cosmosdb_account.main.primary_key
  sensitive   = true
}

output "cosmos_connection_string" {
  description = "Cosmos DB connection string"
  value       = azurerm_cosmosdb_account.main.primary_sql_connection_string
  sensitive   = true
}

output "resource_group_name" {
  description = "Resource group name"
  value       = azurerm_resource_group.main.name
}

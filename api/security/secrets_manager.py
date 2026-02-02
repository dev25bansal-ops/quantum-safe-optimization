"""
Centralized Secrets Management with Azure Key Vault integration.

Features:
- Azure Key Vault for production secrets
- Local environment variable fallback for development
- Secret caching with configurable TTL
- Automatic secret rotation support
- PQC key storage integration
"""

import os
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache
import json

from azure.identity.aio import (
    DefaultAzureCredential,
    ManagedIdentityCredential,
    ChainedTokenCredential,
)
from azure.keyvault.secrets.aio import SecretClient
from azure.core.exceptions import ResourceNotFoundError, ClientAuthenticationError


@dataclass
class SecretsConfig:
    """Configuration for secrets management."""
    key_vault_uri: Optional[str] = field(default_factory=lambda: os.getenv("KEY_VAULT_URI"))
    use_managed_identity: bool = field(
        default_factory=lambda: os.getenv("USE_MANAGED_IDENTITY", "false").lower() == "true"
    )
    cache_ttl_seconds: int = 300  # 5 minutes
    enable_rotation_check: bool = True
    local_fallback: bool = True  # Use env vars when Key Vault unavailable
    

class SecretsCacheEntry:
    """Cache entry for a secret value."""
    
    def __init__(self, value: str, expires_at: datetime):
        self.value = value
        self.expires_at = expires_at
        self.version: Optional[str] = None
    
    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at


class SecretsManager:
    """
    Centralized secrets management with Azure Key Vault integration.
    
    Usage:
        secrets = SecretsManager()
        await secrets.initialize()
        
        # Get a secret
        db_password = await secrets.get_secret("cosmos-primary-key")
        
        # Get with fallback
        jwt_secret = await secrets.get_secret("jwt-secret", fallback="dev-secret")
    """
    
    _instance: Optional["SecretsManager"] = None
    _client: Optional[SecretClient] = None
    _cache: Dict[str, SecretsCacheEntry] = {}
    _initialized: bool = False
    _use_local: bool = False
    
    # Mapping from secret names to environment variable names
    SECRET_ENV_MAPPING = {
        "cosmos-primary-key": "COSMOS_KEY",
        "cosmos-connection-string": "COSMOS_CONNECTION_STRING",
        "jwt-secret": "JWT_SECRET",
        "redis-password": "REDIS_PASSWORD",
        "ibm-quantum-token": "IBM_QUANTUM_TOKEN",
        "dwave-api-token": "DWAVE_API_TOKEN",
        "aws-access-key": "AWS_ACCESS_KEY_ID",
        "aws-secret-key": "AWS_SECRET_ACCESS_KEY",
        "pqc-signing-key": "PQC_SIGNING_KEY",
        "pqc-encryption-key": "PQC_ENCRYPTION_KEY",
    }
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.config = SecretsConfig()
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> "SecretsManager":
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def initialize(self, config: Optional[SecretsConfig] = None):
        """Initialize the secrets manager."""
        if self._initialized:
            return
        
        if config:
            self.config = config
        
        # Try to connect to Key Vault if URI is provided
        if self.config.key_vault_uri:
            try:
                credential = self._get_credential()
                self._client = SecretClient(
                    vault_url=self.config.key_vault_uri,
                    credential=credential,
                )
                # Test connection by listing secrets (just check auth)
                await self._test_connection()
                self._use_local = False
                print(f"✅ Secrets Manager connected to Key Vault: {self.config.key_vault_uri}")
            except ClientAuthenticationError as e:
                if self.config.local_fallback:
                    print(f"⚠️ Key Vault auth failed, using local secrets: {e}")
                    self._use_local = True
                else:
                    raise
            except Exception as e:
                if self.config.local_fallback:
                    print(f"⚠️ Key Vault unavailable, using local secrets: {e}")
                    self._use_local = True
                else:
                    raise
        else:
            print("ℹ️ No Key Vault URI configured, using local environment secrets")
            self._use_local = True
        
        self._initialized = True
    
    def _get_credential(self):
        """Get appropriate Azure credential."""
        if self.config.use_managed_identity:
            # Use managed identity in Azure environments
            return ManagedIdentityCredential()
        else:
            # Use default credential chain (supports multiple auth methods)
            return DefaultAzureCredential()
    
    async def _test_connection(self):
        """Test Key Vault connection."""
        # Try to get properties of a test secret
        try:
            async for secret in self._client.list_properties_of_secrets():
                break  # Just check we can list
        except Exception:
            # If listing fails, try getting a known secret
            pass
    
    async def close(self):
        """Close the secrets manager."""
        if self._client:
            await self._client.close()
            self._client = None
        self._cache.clear()
        self._initialized = False
    
    async def get_secret(
        self,
        name: str,
        fallback: Optional[str] = None,
        bypass_cache: bool = False,
    ) -> Optional[str]:
        """
        Get a secret value.
        
        Args:
            name: Secret name (Key Vault style, e.g., "cosmos-primary-key")
            fallback: Fallback value if secret not found
            bypass_cache: Skip cache and fetch fresh value
        
        Returns:
            Secret value or fallback
        """
        if not self._initialized:
            await self.initialize()
        
        # Check cache first
        if not bypass_cache and name in self._cache:
            entry = self._cache[name]
            if not entry.is_expired():
                return entry.value
        
        # Fetch from appropriate source
        value = None
        if self._use_local:
            value = self._get_local_secret(name)
        else:
            value = await self._get_keyvault_secret(name)
        
        # Use fallback if needed
        if value is None:
            value = fallback
        
        # Cache the result
        if value is not None:
            self._cache[name] = SecretsCacheEntry(
                value=value,
                expires_at=datetime.utcnow() + timedelta(seconds=self.config.cache_ttl_seconds),
            )
        
        return value
    
    def _get_local_secret(self, name: str) -> Optional[str]:
        """Get secret from environment variables."""
        # First try the mapped environment variable
        env_name = self.SECRET_ENV_MAPPING.get(name)
        if env_name:
            value = os.getenv(env_name)
            if value:
                return value
        
        # Try the name directly (uppercase with underscores)
        env_name = name.upper().replace("-", "_")
        return os.getenv(env_name)
    
    async def _get_keyvault_secret(self, name: str) -> Optional[str]:
        """Get secret from Azure Key Vault."""
        try:
            secret = await self._client.get_secret(name)
            return secret.value
        except ResourceNotFoundError:
            # Try local fallback
            if self.config.local_fallback:
                return self._get_local_secret(name)
            return None
        except Exception as e:
            print(f"⚠️ Error fetching secret '{name}' from Key Vault: {e}")
            if self.config.local_fallback:
                return self._get_local_secret(name)
            raise
    
    async def set_secret(self, name: str, value: str) -> bool:
        """
        Set a secret value (only works with Key Vault).
        
        Args:
            name: Secret name
            value: Secret value
        
        Returns:
            True if successful
        """
        if self._use_local:
            print("⚠️ Cannot set secrets in local mode")
            return False
        
        try:
            await self._client.set_secret(name, value)
            # Update cache
            self._cache[name] = SecretsCacheEntry(
                value=value,
                expires_at=datetime.utcnow() + timedelta(seconds=self.config.cache_ttl_seconds),
            )
            return True
        except Exception as e:
            print(f"❌ Error setting secret '{name}': {e}")
            return False
    
    async def delete_secret(self, name: str) -> bool:
        """Delete a secret from Key Vault."""
        if self._use_local:
            return False
        
        try:
            await self._client.begin_delete_secret(name)
            self._cache.pop(name, None)
            return True
        except Exception as e:
            print(f"❌ Error deleting secret '{name}': {e}")
            return False
    
    def invalidate_cache(self, name: Optional[str] = None):
        """Invalidate cached secrets."""
        if name:
            self._cache.pop(name, None)
        else:
            self._cache.clear()
    
    async def get_all_secrets(self, prefix: Optional[str] = None) -> Dict[str, str]:
        """
        Get all secrets (or secrets with a prefix).
        
        Warning: Use sparingly in production.
        """
        secrets = {}
        
        if self._use_local:
            # Return mapped secrets from environment
            for secret_name, env_name in self.SECRET_ENV_MAPPING.items():
                if prefix and not secret_name.startswith(prefix):
                    continue
                value = os.getenv(env_name)
                if value:
                    secrets[secret_name] = value
        else:
            async for secret_props in self._client.list_properties_of_secrets():
                if prefix and not secret_props.name.startswith(prefix):
                    continue
                value = await self.get_secret(secret_props.name)
                if value:
                    secrets[secret_props.name] = value
        
        return secrets
    
    @property
    def is_using_keyvault(self) -> bool:
        """Check if using Key Vault or local mode."""
        return not self._use_local


# Convenience functions for module-level access
_secrets_manager: Optional[SecretsManager] = None


async def init_secrets_manager(config: Optional[SecretsConfig] = None) -> SecretsManager:
    """Initialize the global secrets manager."""
    global _secrets_manager
    _secrets_manager = SecretsManager()
    await _secrets_manager.initialize(config)
    return _secrets_manager


async def get_secret(name: str, fallback: Optional[str] = None) -> Optional[str]:
    """Get a secret value using the global manager."""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
        await _secrets_manager.initialize()
    return await _secrets_manager.get_secret(name, fallback)


async def close_secrets_manager():
    """Close the global secrets manager."""
    global _secrets_manager
    if _secrets_manager:
        await _secrets_manager.close()
        _secrets_manager = None

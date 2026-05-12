"""Async secrets manager abstraction.

The production path can be backed by Azure Key Vault when configured. Local and
test runs use environment variables plus explicit fallbacks, which keeps app
startup deterministic without hard-coding production secrets.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


def _env_candidates(name: str) -> list[str]:
    normalized = name.replace("-", "_").replace(".", "_").upper()
    return [name, normalized, f"QSOP_{normalized}"]


@dataclass
class SecretsManager:
    """Resolve secrets from environment variables or Azure Key Vault."""

    vault_url: str | None = None
    _client: Any | None = field(default=None, init=False, repr=False)
    _initialized: bool = field(default=False, init=False)

    async def initialize(self) -> None:
        """Initialize the optional Key Vault client."""
        self.vault_url = self.vault_url or os.getenv("KEY_VAULT_URI")
        if not self.vault_url:
            self._initialized = True
            return

        try:
            from azure.identity.aio import DefaultAzureCredential
            from azure.keyvault.secrets.aio import SecretClient

            credential = DefaultAzureCredential()
            self._client = SecretClient(vault_url=self.vault_url, credential=credential)
        except Exception:
            self._client = None
        finally:
            self._initialized = True

    async def close(self) -> None:
        """Close any async client resources."""
        if self._client and hasattr(self._client, "close"):
            await self._client.close()
        self._client = None
        self._initialized = False

    async def get_secret(self, name: str, fallback: str | None = None) -> str | None:
        """Return a secret by name, checking environment before Key Vault."""
        for env_name in _env_candidates(name):
            value = os.getenv(env_name)
            if value:
                return value

        if self._client:
            try:
                secret = await self._client.get_secret(name)
                return secret.value
            except Exception:
                pass

        return fallback

    async def set_secret(self, name: str, value: str) -> None:
        """Store a secret when a writable backing store is configured."""
        if self._client:
            await self._client.set_secret(name, value)
            return
        os.environ[_env_candidates(name)[1]] = value

    def status(self) -> dict[str, Any]:
        """Return non-sensitive manager status."""
        return {
            "initialized": self._initialized,
            "backend": "azure_key_vault" if self._client else "environment",
            "vault_configured": bool(self.vault_url),
        }


_secrets_manager: SecretsManager | None = None


def get_secrets_manager() -> SecretsManager:
    """Get the process-wide secrets manager."""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager


async def init_secrets_manager() -> SecretsManager:
    """Initialize and return the process-wide secrets manager."""
    manager = get_secrets_manager()
    await manager.initialize()
    return manager


async def close_secrets_manager() -> None:
    """Close the process-wide secrets manager."""
    global _secrets_manager
    if _secrets_manager is not None:
        await _secrets_manager.close()
    _secrets_manager = None

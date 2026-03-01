"""
HashiCorp Vault keystore adapter.

Production-ready key management using Vault.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ...domain.errors import KeyStoreError
from ...domain.ports.keystore import KeyMetadata, KeyStatus, KeyType

logger = logging.getLogger(__name__)


@dataclass
class VaultKeyStore:
    """
    HashiCorp Vault keystore adapter.

    Uses Vault's KV V2 engine for key storage.
    """

    vault_addr: str = "http://localhost:8200"
    vault_token: str | None = None
    vault_namespace: str | None = None
    kv_mount_point: str = "secret"
    _client: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Initialize Vault client."""
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Set up the Vault client."""
        try:
            import hvac

            self._client = hvac.Client(
                url=self.vault_addr,
                token=self.vault_token,
                namespace=self.vault_namespace,
            )

            if not self._client.is_authenticated():
                logger.warning("Vault client not authenticated")

        except ImportError:
            logger.warning("hvac not installed. Install with: pip install hvac")
            self._client = None

    def _check_client(self) -> None:
        """Check if client is initialized and authenticated."""
        if self._client is None:
            raise KeyStoreError("Vault client not initialized. Ensure hvac is installed.")
        if not self._client.is_authenticated():
            raise KeyStoreError("Vault client not authenticated.")

    def store_key(
        self,
        key_type: KeyType,
        algorithm: str,
        public_key: bytes,
        secret_key: bytes,
        key_id: str | None = None,
        expires_at: datetime | None = None,
        owner_id: str | None = None,
        tags: tuple[str, ...] = (),
        **metadata: Any,
    ) -> str:
        """Store a new key pair in Vault."""
        self._check_client()

        actual_key_id = key_id or f"key-{uuid.uuid4().hex[:16]}"

        key_data = {
            "key_id": actual_key_id,
            "key_type": key_type.value,
            "algorithm": algorithm,
            "owner_id": owner_id,
            "created_at": datetime.now(UTC).isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "status": KeyStatus.ACTIVE.value,
            "tags": list(tags),
            "usage_count": 0,
            "last_used_at": None,
            "public_key": public_key.hex(),
            "secret_key": secret_key.hex(),
            "custom_data": metadata,
        }

        try:
            self._client.secrets.kv.v2.create_or_update_secret(
                mount_point=self.kv_mount_point,
                path=f"qsop/keys/{actual_key_id}",
                secret=key_data,
            )
            return actual_key_id
        except Exception as e:
            raise KeyStoreError(
                f"Failed to store key in Vault: {e}", key_id=actual_key_id, operation="store_key"
            ) from e

    def get_public_key(self, key_id: str) -> bytes:
        """Retrieve a public key from Vault."""
        self._check_client()
        try:
            response = self._client.secrets.kv.v2.read_secret_version(
                mount_point=self.kv_mount_point,
                path=f"qsop/keys/{key_id}",
            )
            data = response["data"]["data"]
            return bytes.fromhex(data["public_key"])
        except Exception as e:
            raise KeyStoreError(
                f"Key not found in Vault: {key_id}", key_id=key_id, operation="get_public_key"
            ) from e

    def get_secret_key(self, key_id: str) -> bytes:
        """Retrieve a secret key from Vault."""
        self._check_client()
        try:
            response = self._client.secrets.kv.v2.read_secret_version(
                mount_point=self.kv_mount_point,
                path=f"qsop/keys/{key_id}",
            )
            data = response["data"]["data"]

            if data["status"] != KeyStatus.ACTIVE.value:
                raise KeyStoreError(
                    f"Key {key_id} is not active (status: {data['status']})", key_id=key_id
                )

            return bytes.fromhex(data["secret_key"])
        except KeyStoreError:
            raise
        except Exception as e:
            raise KeyStoreError(
                f"Key not found or access denied in Vault: {key_id}",
                key_id=key_id,
                operation="get_secret_key",
            ) from e

    def get_metadata(self, key_id: str) -> KeyMetadata:
        """Retrieve key metadata from Vault."""
        self._check_client()
        try:
            response = self._client.secrets.kv.v2.read_secret_version(
                mount_point=self.kv_mount_point,
                path=f"qsop/keys/{key_id}",
            )
            kd = response["data"]["data"]
            return KeyMetadata(
                key_id=kd["key_id"],
                key_type=KeyType(kd["key_type"]),
                algorithm=kd["algorithm"],
                status=KeyStatus(kd["status"]),
                created_at=datetime.fromisoformat(kd["created_at"]),
                expires_at=datetime.fromisoformat(kd["expires_at"])
                if kd.get("expires_at")
                else None,
                rotated_from=kd.get("rotated_from"),
                rotated_to=kd.get("rotated_to"),
                owner_id=kd.get("owner_id"),
                usage_count=kd.get("usage_count", 0),
                last_used_at=datetime.fromisoformat(kd["last_used_at"])
                if kd.get("last_used_at")
                else None,
                tags=tuple(kd.get("tags", [])),
                custom_data=kd.get("custom_data", {}),
            )
        except Exception as e:
            raise KeyStoreError(
                f"Key metadata not found in Vault: {key_id}",
                key_id=key_id,
                operation="get_metadata",
            ) from e

    def list_keys(
        self,
        key_type: KeyType | None = None,
        status: KeyStatus | None = None,
        owner_id: str | None = None,
        tags: tuple[str, ...] | None = None,
    ) -> list[KeyMetadata]:
        """List keys matching criteria from Vault."""
        self._check_client()
        results = []
        try:
            response = self._client.secrets.kv.v2.list_secrets(
                mount_point=self.kv_mount_point,
                path="qsop/keys",
            )

            for key_id in response["data"]["keys"]:
                key_id = key_id.rstrip("/")
                try:
                    meta = self.get_metadata(key_id)
                    if key_type and meta.key_type != key_type:
                        continue
                    if status and meta.status != status:
                        continue
                    if owner_id and meta.owner_id != owner_id:
                        continue
                    if tags and not all(t in meta.tags for t in tags):
                        continue
                    results.append(meta)
                except KeyStoreError:
                    continue

        except Exception as e:
            logger.error(f"Failed to list keys in Vault: {e}")

        return results

    def rotate_key(
        self,
        key_id: str,
        new_public_key: bytes,
        new_secret_key: bytes,
        new_key_id: str | None = None,
    ) -> str:
        """Rotate a key in Vault."""
        self._check_client()
        old_meta = self.get_metadata(key_id)

        # Mark old key as inactive
        try:
            response = self._client.secrets.kv.v2.read_secret_version(
                mount_point=self.kv_mount_point,
                path=f"qsop/keys/{key_id}",
            )
            old_data = response["data"]["data"]
            old_data["status"] = KeyStatus.INACTIVE.value

            # Store new key
            new_id = self.store_key(
                key_type=old_meta.key_type,
                algorithm=old_meta.algorithm,
                public_key=new_public_key,
                secret_key=new_secret_key,
                key_id=new_key_id,
                owner_id=old_meta.owner_id,
                tags=old_meta.tags,
                rotated_from=key_id,
                **old_meta.custom_data,
            )

            old_data["rotated_to"] = new_id
            self._client.secrets.kv.v2.create_or_update_secret(
                mount_point=self.kv_mount_point,
                path=f"qsop/keys/{key_id}",
                secret=old_data,
            )

            return new_id
        except Exception as e:
            raise KeyStoreError(
                f"Failed to rotate key in Vault: {e}", key_id=key_id, operation="rotate_key"
            ) from e

    def revoke_key(self, key_id: str, reason: str = "") -> None:
        """Revoke a key in Vault."""
        self._check_client()
        try:
            response = self._client.secrets.kv.v2.read_secret_version(
                mount_point=self.kv_mount_point,
                path=f"qsop/keys/{key_id}",
            )
            data = response["data"]["data"]
            data["status"] = KeyStatus.REVOKED.value
            data["custom_data"]["revocation_reason"] = reason

            self._client.secrets.kv.v2.create_or_update_secret(
                mount_point=self.kv_mount_point,
                path=f"qsop/keys/{key_id}",
                secret=data,
            )
        except Exception as e:
            raise KeyStoreError(
                f"Failed to revoke key in Vault: {e}", key_id=key_id, operation="revoke_key"
            ) from e

    def delete_key(self, key_id: str) -> None:
        """Permanently delete a key from Vault."""
        self._check_client()
        try:
            self._client.secrets.kv.v2.delete_metadata_and_all_versions(
                mount_point=self.kv_mount_point,
                path=f"qsop/keys/{key_id}",
            )
        except Exception as e:
            raise KeyStoreError(
                f"Failed to delete key in Vault: {e}", key_id=key_id, operation="delete_key"
            ) from e

    def record_usage(self, key_id: str) -> None:
        """Record key usage in Vault."""
        self._check_client()
        try:
            response = self._client.secrets.kv.v2.read_secret_version(
                mount_point=self.kv_mount_point,
                path=f"qsop/keys/{key_id}",
            )
            data = response["data"]["data"]
            data["usage_count"] = data.get("usage_count", 0) + 1
            data["last_used_at"] = datetime.now(UTC).isoformat()

            self._client.secrets.kv.v2.create_or_update_secret(
                mount_point=self.kv_mount_point,
                path=f"qsop/keys/{key_id}",
                secret=data,
            )
        except Exception as e:
            raise KeyStoreError(
                f"Failed to record usage in Vault: {e}", key_id=key_id, operation="record_usage"
            ) from e

"""
AWS KMS keystore adapter.

Production-ready key management using AWS KMS.
"""

from __future__ import annotations

import base64
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ...domain.errors import KeyStoreError
from ...domain.ports.keystore import KeyMetadata, KeyStatus, KeyStore, KeyType

logger = logging.getLogger(__name__)


@dataclass
class AWSKMSKeyStore:
    """
    AWS KMS keystore adapter.
    
    Manages cryptographic keys using AWS KMS.
    Secret keys are encrypted using a Master Key (CMK) before storage.
    """
    
    region: str = "us-east-1"
    cmk_id: str | None = None  # AWS KMS Customer Master Key ID/Alias
    table_name: str = "qsop-keys"  # DynamoDB table for metadata and encrypted keys
    _kms: Any = field(default=None, repr=False)
    _ddb: Any = field(default=None, repr=False)
    
    def __post_init__(self) -> None:
        """Initialize AWS clients."""
        self._initialize_clients()
    
    def _initialize_clients(self) -> None:
        """Set up AWS clients."""
        try:
            import boto3
            
            self._kms = boto3.client("kms", region_name=self.region)
            self._ddb = boto3.resource("dynamodb", region_name=self.region)
            
        except ImportError:
            logger.warning("boto3 not installed. Install with: pip install boto3")
            self._kms = None
            self._ddb = None

    def _check_clients(self) -> None:
        """Check if clients are initialized."""
        if self._kms is None or self._ddb is None:
            raise KeyStoreError("AWS clients not initialized. Ensure boto3 is installed.")
        if not self.cmk_id:
            raise KeyStoreError("AWS KMS CMK ID not configured.")

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
        """Store a new key pair, encrypting the secret key with AWS KMS."""
        self._check_clients()
        
        actual_key_id = key_id or f"key-{uuid.uuid4().hex[:16]}"
        
        # Encrypt secret key with KMS
        try:
            encrypt_response = self._kms.encrypt(
                KeyId=self.cmk_id,
                Plaintext=secret_key,
                EncryptionContext={"KeyId": actual_key_id}
            )
            encrypted_secret = encrypt_response["CiphertextBlob"]
        except Exception as e:
            raise KeyStoreError(f"Failed to encrypt secret key with AWS KMS: {e}", key_id=actual_key_id) from e
        
        # Store in DynamoDB
        item = {
            "key_id": actual_key_id,
            "key_type": key_type.value,
            "algorithm": algorithm,
            "owner_id": owner_id or "system",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "status": KeyStatus.ACTIVE.value,
            "tags": list(tags),
            "usage_count": 0,
            "last_used_at": None,
            "public_key": base64.b64encode(public_key).decode("utf-8"),
            "encrypted_secret_key": base64.b64encode(encrypted_secret).decode("utf-8"),
            "custom_data": json.dumps(metadata),
        }
        
        try:
            table = self._ddb.Table(self.table_name)
            table.put_item(Item=item)
            return actual_key_id
        except Exception as e:
            raise KeyStoreError(f"Failed to store key metadata in DynamoDB: {e}", key_id=actual_key_id) from e

    def get_public_key(self, key_id: str) -> bytes:
        """Retrieve a public key from DynamoDB."""
        self._check_clients()
        try:
            table = self._ddb.Table(self.table_name)
            response = table.get_item(Key={"key_id": key_id})
            if "Item" not in response:
                raise KeyStoreError(f"Key not found: {key_id}", key_id=key_id)
            
            return base64.b64decode(response["Item"]["public_key"])
        except KeyStoreError:
            raise
        except Exception as e:
            raise KeyStoreError(f"Failed to retrieve public key from AWS: {e}", key_id=key_id) from e

    def get_secret_key(self, key_id: str) -> bytes:
        """Retrieve and decrypt a secret key using AWS KMS."""
        self._check_clients()
        try:
            table = self._ddb.Table(self.table_name)
            response = table.get_item(Key={"key_id": key_id})
            if "Item" not in response:
                raise KeyStoreError(f"Key not found: {key_id}", key_id=key_id)
            
            item = response["Item"]
            if item["status"] != KeyStatus.ACTIVE.value:
                raise KeyStoreError(f"Key {key_id} is not active (status: {item['status']})", key_id=key_id)
            
            encrypted_secret = base64.b64decode(item["encrypted_secret_key"])
            
            # Decrypt with KMS
            decrypt_response = self._kms.decrypt(
                CiphertextBlob=encrypted_secret,
                EncryptionContext={"KeyId": key_id}
            )
            return decrypt_response["Plaintext"]
            
        except KeyStoreError:
            raise
        except Exception as e:
            raise KeyStoreError(f"Failed to decrypt secret key with AWS KMS: {e}", key_id=key_id) from e

    def get_metadata(self, key_id: str) -> KeyMetadata:
        """Retrieve key metadata from DynamoDB."""
        self._check_clients()
        try:
            table = self._ddb.Table(self.table_name)
            response = table.get_item(Key={"key_id": key_id})
            if "Item" not in response:
                raise KeyStoreError(f"Key not found: {key_id}", key_id=key_id)
            
            kd = response["Item"]
            return KeyMetadata(
                key_id=kd["key_id"],
                key_type=KeyType(kd["key_type"]),
                algorithm=kd["algorithm"],
                status=KeyStatus(kd["status"]),
                created_at=datetime.fromisoformat(kd["created_at"]),
                expires_at=datetime.fromisoformat(kd["expires_at"]) if kd.get("expires_at") else None,
                rotated_from=kd.get("rotated_from"),
                rotated_to=kd.get("rotated_to"),
                owner_id=kd.get("owner_id"),
                usage_count=int(kd.get("usage_count", 0)),
                last_used_at=datetime.fromisoformat(kd["last_used_at"]) if kd.get("last_used_at") else None,
                tags=tuple(kd.get("tags", [])),
                custom_data=json.loads(kd.get("custom_data", "{}")),
            )
        except Exception as e:
            raise KeyStoreError(f"Failed to retrieve key metadata from AWS: {e}", key_id=key_id) from e

    def list_keys(
        self,
        key_type: KeyType | None = None,
        status: KeyStatus | None = None,
        owner_id: str | None = None,
        tags: tuple[str, ...] | None = None,
    ) -> list[KeyMetadata]:
        """List keys matching criteria from DynamoDB."""
        self._check_clients()
        results = []
        try:
            table = self._ddb.Table(self.table_name)
            # Simple scan (not efficient for large datasets, but good for now)
            response = table.scan()
            
            for item in response.get("Items", []):
                try:
                    meta = self.get_metadata(item["key_id"])
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
            logger.error(f"Failed to list keys in AWS: {e}")
            
        return results

    def rotate_key(
        self,
        key_id: str,
        new_public_key: bytes,
        new_secret_key: bytes,
        new_key_id: str | None = None,
    ) -> str:
        """Rotate a key using AWS KMS for encryption."""
        self._check_clients()
        old_meta = self.get_metadata(key_id)
        
        # Mark old key as inactive in DynamoDB
        try:
            table = self._ddb.Table(self.table_name)
            table.update_item(
                Key={"key_id": key_id},
                UpdateExpression="SET #s = :s",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":s": KeyStatus.INACTIVE.value}
            )
            
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
                **old_meta.custom_data
            )
            
            # Link old key to new key
            table.update_item(
                Key={"key_id": key_id},
                UpdateExpression="SET rotated_to = :r",
                ExpressionAttributeValues={":r": new_id}
            )
            
            return new_id
        except Exception as e:
            raise KeyStoreError(f"Failed to rotate key in AWS: {e}", key_id=key_id) from e

    def revoke_key(self, key_id: str, reason: str = "") -> None:
        """Revoke a key in DynamoDB."""
        self._check_clients()
        try:
            table = self._ddb.Table(self.table_name)
            table.update_item(
                Key={"key_id": key_id},
                UpdateExpression="SET #s = :s, revocation_reason = :r",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":s": KeyStatus.REVOKED.value,
                    ":r": reason
                }
            )
        except Exception as e:
            raise KeyStoreError(f"Failed to revoke key in AWS: {e}", key_id=key_id) from e

    def delete_key(self, key_id: str) -> None:
        """Permanently delete a key from DynamoDB."""
        self._check_clients()
        try:
            table = self._ddb.Table(self.table_name)
            table.delete_item(Key={"key_id": key_id})
        except Exception as e:
            raise KeyStoreError(f"Failed to delete key in AWS: {e}", key_id=key_id) from e

    def record_usage(self, key_id: str) -> None:
        """Record key usage in DynamoDB."""
        self._check_clients()
        try:
            table = self._ddb.Table(self.table_name)
            table.update_item(
                Key={"key_id": key_id},
                UpdateExpression="ADD usage_count :inc SET last_used_at = :now",
                ExpressionAttributeValues={
                    ":inc": 1,
                    ":now": datetime.now(timezone.utc).isoformat()
                }
            )
        except Exception as e:
            raise KeyStoreError(f"Failed to record usage in AWS: {e}", key_id=key_id) from e

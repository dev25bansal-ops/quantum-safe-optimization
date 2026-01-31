"""
Local development keystore.

WARNING: For development only. Do not use in production.
"""

from __future__ import annotations

import json
import os
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...domain.ports.keystore import KeyStore, KeyMetadata, KeyType, KeyStatus

logger = logging.getLogger(__name__)


class LocalDevKeyStore:
    """
    Local file-based keystore for development.
    
    Stores keys in a local directory. NOT SECURE - for development only.
    """
    
    def __init__(self, storage_path: Path | None = None):
        self.storage_path = storage_path or Path.home() / ".qsop" / "keys"
        self._keys: dict[str, dict] = {}
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._load_keys()
        logger.warning(
            "LocalDevKeyStore is for development only. "
            "Use VaultKeyStore or cloud KMS in production."
        )
    
    def _load_keys(self) -> None:
        """Load keys from storage."""
        metadata_file = self.storage_path / "metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file, "r") as f:
                    self._keys = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load key metadata: {e}")
                self._keys = {}
    
    def _save_metadata(self) -> None:
        """Save key metadata."""
        metadata_file = self.storage_path / "metadata.json"
        # Don't save private keys in metadata summary
        safe_metadata = {
            k: {kk: vv for kk, vv in v.items() if kk != "secret_key"}
            for k, v in self._keys.items()
        }
        with open(metadata_file, "w") as f:
            json.dump(safe_metadata, f, indent=2)
    
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
        """Store a new key pair."""
        actual_key_id = key_id or f"key-{uuid.uuid4().hex[:16]}"
        
        # Store key data
        key_data = {
            "key_id": actual_key_id,
            "key_type": key_type.value,
            "algorithm": algorithm,
            "owner_id": owner_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "status": KeyStatus.ACTIVE.value,
            "tags": list(tags),
            "usage_count": 0,
            "last_used_at": None,
            "custom_data": metadata,
            "public_key": public_key.hex(),
            "secret_key": secret_key.hex(),
        }
        
        self._keys[actual_key_id] = key_data
        self._save_metadata()
        
        # Save full key data to individual file
        key_file = self.storage_path / f"{actual_key_id}.key"
        with open(key_file, "w") as f:
            json.dump(key_data, f)
            
        return actual_key_id
    
    def get_public_key(self, key_id: str) -> bytes:
        """Retrieve a public key."""
        if key_id not in self._keys:
            self._load_key_from_file(key_id)
            
        return bytes.fromhex(self._keys[key_id]["public_key"])
    
    def get_secret_key(self, key_id: str) -> bytes:
        """Retrieve a secret key."""
        if key_id not in self._keys:
            self._load_key_from_file(key_id)
            
        key_data = self._keys[key_id]
        if key_data["status"] != KeyStatus.ACTIVE.value:
            raise ValueError(f"Key {key_id} is not active (status: {key_data['status']})")
            
        return bytes.fromhex(key_data["secret_key"])
    
    def get_metadata(self, key_id: str) -> KeyMetadata:
        """Retrieve key metadata."""
        if key_id not in self._keys:
            self._load_key_from_file(key_id)
            
        kd = self._keys[key_id]
        return KeyMetadata(
            key_id=kd["key_id"],
            key_type=KeyType(kd["key_type"]),
            algorithm=kd["algorithm"],
            status=KeyStatus(kd["status"]),
            created_at=datetime.fromisoformat(kd["created_at"]),
            expires_at=datetime.fromisoformat(kd["expires_at"]) if kd["expires_at"] else None,
            rotated_from=kd.get("rotated_from") or kd.get("custom_data", {}).get("rotated_from"),
            rotated_to=kd.get("rotated_to"),
            owner_id=kd.get("owner_id"),
            usage_count=kd.get("usage_count", 0),
            last_used_at=datetime.fromisoformat(kd["last_used_at"]) if kd.get("last_used_at") else None,
            tags=tuple(kd.get("tags", [])),
            custom_data=kd.get("custom_data", {}),
        )
    
    def list_keys(
        self,
        key_type: KeyType | None = None,
        status: KeyStatus | None = None,
        owner_id: str | None = None,
        tags: tuple[str, ...] | None = None,
    ) -> list[KeyMetadata]:
        """List keys matching criteria."""
        results = []
        for kid in self._keys:
            meta = self.get_metadata(kid)
            
            if key_type and meta.key_type != key_type:
                continue
            if status and meta.status != status:
                continue
            if owner_id and meta.owner_id != owner_id:
                continue
            if tags and not all(t in meta.tags for t in tags):
                continue
                
            results.append(meta)
            
        return results
    
    def rotate_key(
        self,
        key_id: str,
        new_public_key: bytes,
        new_secret_key: bytes,
        new_key_id: str | None = None,
    ) -> str:
        """Rotate a key."""
        old_meta = self.get_metadata(key_id)
        
        # Mark old key as inactive/rotated
        self._keys[key_id]["status"] = KeyStatus.INACTIVE.value
        
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
        
        self._keys[key_id]["rotated_to"] = new_id
        self._save_metadata()
        
        return new_id
    
    def revoke_key(self, key_id: str, reason: str = "") -> None:
        """Revoke a key."""
        if key_id not in self._keys:
            self._load_key_from_file(key_id)
            
        self._keys[key_id]["status"] = KeyStatus.REVOKED.value
        self._keys[key_id]["custom_data"]["revocation_reason"] = reason
        self._save_metadata()
    
    def delete_key(self, key_id: str) -> None:
        """Permanently delete a key."""
        if key_id in self._keys:
            del self._keys[key_id]
            
        key_file = self.storage_path / f"{key_id}.key"
        if key_file.exists():
            key_file.unlink()
            
        self._save_metadata()
    
    def record_usage(self, key_id: str) -> None:
        """Record key usage."""
        if key_id not in self._keys:
            self._load_key_from_file(key_id)
            
        self._keys[key_id]["usage_count"] = self._keys[key_id].get("usage_count", 0) + 1
        self._keys[key_id]["last_used_at"] = datetime.now(timezone.utc).isoformat()
        self._save_metadata()

    def _load_key_from_file(self, key_id: str) -> None:
        """Helper to load a specific key from disk if not in memory."""
        key_file = self.storage_path / f"{key_id}.key"
        if key_file.exists():
            with open(key_file, "r") as f:
                self._keys[key_id] = json.load(f)
        else:
            raise KeyError(f"Key not found: {key_id}")

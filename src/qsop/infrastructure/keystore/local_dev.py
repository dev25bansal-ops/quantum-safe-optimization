"""
Local development keystore.

WARNING: For development only. Do not use in production.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import logging

from ...domain.ports.keystore import KeyStore, KeyMetadata

logger = logging.getLogger(__name__)


@dataclass
class LocalDevKeyStore:
    """
    Local file-based keystore for development.
    
    Stores keys in a local directory. NOT SECURE - for development only.
    """
    
    storage_path: Path = field(default_factory=lambda: Path.home() / ".qsop" / "keys")
    _keys: dict[str, dict] = field(default_factory=dict, repr=False)
    
    def __post_init__(self) -> None:
        """Initialize storage directory."""
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
            with open(metadata_file, "r") as f:
                self._keys = json.load(f)
    
    def _save_metadata(self) -> None:
        """Save key metadata."""
        metadata_file = self.storage_path / "metadata.json"
        # Don't save private keys in metadata
        safe_metadata = {
            k: {kk: vv for kk, vv in v.items() if kk != "private_key"}
            for k, v in self._keys.items()
        }
        with open(metadata_file, "w") as f:
            json.dump(safe_metadata, f, indent=2)
    
    def create_key(
        self,
        *,
        key_type: str,
        algorithm: str,
        owner: str,
        metadata: dict | None = None,
    ) -> str:
        """Create a new key pair."""
        import uuid
        from ...crypto.pqc import KEMAlgorithm, SignatureAlgorithm, get_kem, get_signature_scheme
        
        key_id = f"key-{uuid.uuid4().hex[:16]}"
        
        # Generate keys based on type
        if key_type == "kem":
            alg = KEMAlgorithm(algorithm)
            kem = get_kem(alg)
            public_key, private_key = kem.keygen()
        elif key_type == "signature":
            alg = SignatureAlgorithm(algorithm)
            sig = get_signature_scheme(alg)
            public_key, private_key = sig.keygen()
        else:
            raise ValueError(f"Unknown key type: {key_type}")
        
        # Store key data
        key_data = {
            "key_id": key_id,
            "key_type": key_type,
            "algorithm": algorithm,
            "owner": owner,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "active",
            "metadata": metadata or {},
            "public_key": public_key.hex(),
            "private_key": private_key.hex(),  # In real implementation, encrypt this
        }
        
        self._keys[key_id] = key_data
        
        # Save to files
        self._save_metadata()
        key_file = self.storage_path / f"{key_id}.key"
        with open(key_file, "w") as f:
            json.dump(key_data, f)
        
        return key_id
    
    def get_public_key(self, key_id: str) -> bytes:
        """Get public key by ID."""
        if key_id not in self._keys:
            # Try to load from file
            key_file = self.storage_path / f"{key_id}.key"
            if key_file.exists():
                with open(key_file, "r") as f:
                    self._keys[key_id] = json.load(f)
            else:
                raise KeyError(f"Key not found: {key_id}")
        
        return bytes.fromhex(self._keys[key_id]["public_key"])
    
    def use_private_key(self, key_id: str, purpose: str) -> PrivateKeyHandle:
        """Get a handle to use a private key."""
        if key_id not in self._keys:
            key_file = self.storage_path / f"{key_id}.key"
            if key_file.exists():
                with open(key_file, "r") as f:
                    self._keys[key_id] = json.load(f)
            else:
                raise KeyError(f"Key not found: {key_id}")
        
        key_data = self._keys[key_id]
        
        if key_data["status"] != "active":
            raise ValueError(f"Key {key_id} is not active")
        
        return LocalPrivateKeyHandle(
            key_id=key_id,
            private_key=bytes.fromhex(key_data["private_key"]),
            algorithm=key_data["algorithm"],
            key_type=key_data["key_type"],
        )
    
    def rotate_key(self, key_id: str) -> str:
        """Rotate a key, returning new key ID."""
        old_key = self._keys.get(key_id)
        if old_key is None:
            raise KeyError(f"Key not found: {key_id}")
        
        # Create new key with same parameters
        new_key_id = self.create_key(
            key_type=old_key["key_type"],
            algorithm=old_key["algorithm"],
            owner=old_key["owner"],
            metadata={
                **old_key.get("metadata", {}),
                "rotated_from": key_id,
            },
        )
        
        # Mark old key as rotated
        self._keys[key_id]["status"] = "rotated"
        self._keys[key_id]["rotated_to"] = new_key_id
        self._save_metadata()
        
        return new_key_id
    
    def revoke_key(self, key_id: str, reason: str) -> None:
        """Revoke a key."""
        if key_id not in self._keys:
            raise KeyError(f"Key not found: {key_id}")
        
        self._keys[key_id]["status"] = "revoked"
        self._keys[key_id]["revoked_at"] = datetime.now(timezone.utc).isoformat()
        self._keys[key_id]["revoke_reason"] = reason
        self._save_metadata()
        
        # Securely delete private key file
        key_file = self.storage_path / f"{key_id}.key"
        if key_file.exists():
            # Overwrite with zeros before deleting
            size = key_file.stat().st_size
            with open(key_file, "wb") as f:
                f.write(b"\x00" * size)
            key_file.unlink()
    
    def list_keys(self, owner: str | None = None) -> list[KeyMetadata]:
        """List all keys, optionally filtered by owner."""
        result = []
        for key_id, key_data in self._keys.items():
            if owner and key_data.get("owner") != owner:
                continue
            
            result.append(KeyMetadata(
                key_id=key_id,
                key_type=key_data["key_type"],
                algorithm=key_data["algorithm"],
                owner=key_data["owner"],
                status=key_data["status"],
                created_at=datetime.fromisoformat(key_data["created_at"]),
            ))
        
        return result


@dataclass
class LocalPrivateKeyHandle:
    """Handle to a private key for operations."""
    
    key_id: str
    private_key: bytes
    algorithm: str
    key_type: str
    
    def decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypt using this key (for KEM keys)."""
        if self.key_type != "kem":
            raise ValueError("Decrypt only available for KEM keys")
        
        from ...crypto.pqc import KEMAlgorithm, get_kem
        
        alg = KEMAlgorithm(self.algorithm)
        kem = get_kem(alg)
        return kem.decapsulate(ciphertext, self.private_key)
    
    def sign(self, message: bytes) -> bytes:
        """Sign using this key (for signature keys)."""
        if self.key_type != "signature":
            raise ValueError("Sign only available for signature keys")
        
        from ...crypto.pqc import SignatureAlgorithm, get_signature_scheme
        
        alg = SignatureAlgorithm(self.algorithm)
        sig = get_signature_scheme(alg)
        return sig.sign(message, self.private_key)
    
    def __del__(self) -> None:
        """Attempt to clear private key from memory."""
        if hasattr(self, 'private_key'):
            # This is best-effort; Python doesn't guarantee memory clearing
            try:
                import ctypes
                ctypes.memset(id(self.private_key), 0, len(self.private_key))
            except Exception:
                pass

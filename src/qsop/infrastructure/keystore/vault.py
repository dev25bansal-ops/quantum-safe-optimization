"""
HashiCorp Vault keystore adapter.

Production-ready key management using Vault.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import logging

from ...domain.ports.keystore import KeyStore, KeyMetadata

logger = logging.getLogger(__name__)


@dataclass
class VaultKeyStore:
    """
    HashiCorp Vault keystore adapter.
    
    Uses Vault's Transit secrets engine for key operations.
    """
    
    vault_addr: str = "http://localhost:8200"
    vault_token: str | None = None
    vault_namespace: str | None = None
    mount_point: str = "transit"
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
    
    def create_key(
        self,
        *,
        key_type: str,
        algorithm: str,
        owner: str,
        metadata: dict | None = None,
    ) -> str:
        """Create a new key in Vault."""
        if self._client is None:
            raise RuntimeError("Vault client not initialized")
        
        import uuid
        key_id = f"key-{uuid.uuid4().hex[:16]}"
        
        # Generate key locally and store in Vault
        from ...crypto.pqc import KEMAlgorithm, SignatureAlgorithm, get_kem, get_signature_scheme
        
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
        
        # Store in Vault KV
        key_data = {
            "key_id": key_id,
            "key_type": key_type,
            "algorithm": algorithm,
            "owner": owner,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "active",
            "metadata": metadata or {},
            "public_key": public_key.hex(),
            "private_key": private_key.hex(),
        }
        
        self._client.secrets.kv.v2.create_or_update_secret(
            mount_point=self.kv_mount_point,
            path=f"qsop/keys/{key_id}",
            secret=key_data,
        )
        
        # Store public key separately for easy access
        self._client.secrets.kv.v2.create_or_update_secret(
            mount_point=self.kv_mount_point,
            path=f"qsop/public-keys/{key_id}",
            secret={
                "public_key": public_key.hex(),
                "algorithm": algorithm,
                "key_type": key_type,
            },
        )
        
        return key_id
    
    def get_public_key(self, key_id: str) -> bytes:
        """Get public key from Vault."""
        if self._client is None:
            raise RuntimeError("Vault client not initialized")
        
        try:
            response = self._client.secrets.kv.v2.read_secret_version(
                mount_point=self.kv_mount_point,
                path=f"qsop/public-keys/{key_id}",
            )
            
            data = response["data"]["data"]
            return bytes.fromhex(data["public_key"])
            
        except Exception as e:
            raise KeyError(f"Key not found: {key_id}") from e
    
    def use_private_key(self, key_id: str, purpose: str) -> PrivateKeyHandle:
        """Get a handle to use a private key."""
        if self._client is None:
            raise RuntimeError("Vault client not initialized")
        
        try:
            response = self._client.secrets.kv.v2.read_secret_version(
                mount_point=self.kv_mount_point,
                path=f"qsop/keys/{key_id}",
            )
            
            data = response["data"]["data"]
            
            if data["status"] != "active":
                raise ValueError(f"Key {key_id} is not active")
            
            # Log access for audit
            logger.info(f"Private key access: key={key_id}, purpose={purpose}")
            
            return VaultPrivateKeyHandle(
                key_id=key_id,
                private_key=bytes.fromhex(data["private_key"]),
                algorithm=data["algorithm"],
                key_type=data["key_type"],
            )
            
        except Exception as e:
            raise KeyError(f"Key not found: {key_id}") from e
    
    def rotate_key(self, key_id: str) -> str:
        """Rotate a key."""
        if self._client is None:
            raise RuntimeError("Vault client not initialized")
        
        # Get old key data
        response = self._client.secrets.kv.v2.read_secret_version(
            mount_point=self.kv_mount_point,
            path=f"qsop/keys/{key_id}",
        )
        old_data = response["data"]["data"]
        
        # Create new key
        new_key_id = self.create_key(
            key_type=old_data["key_type"],
            algorithm=old_data["algorithm"],
            owner=old_data["owner"],
            metadata={
                **old_data.get("metadata", {}),
                "rotated_from": key_id,
            },
        )
        
        # Mark old key as rotated
        old_data["status"] = "rotated"
        old_data["rotated_to"] = new_key_id
        old_data["rotated_at"] = datetime.now(timezone.utc).isoformat()
        
        self._client.secrets.kv.v2.create_or_update_secret(
            mount_point=self.kv_mount_point,
            path=f"qsop/keys/{key_id}",
            secret=old_data,
        )
        
        return new_key_id
    
    def revoke_key(self, key_id: str, reason: str) -> None:
        """Revoke a key."""
        if self._client is None:
            raise RuntimeError("Vault client not initialized")
        
        try:
            response = self._client.secrets.kv.v2.read_secret_version(
                mount_point=self.kv_mount_point,
                path=f"qsop/keys/{key_id}",
            )
            data = response["data"]["data"]
            
            # Update status
            data["status"] = "revoked"
            data["revoked_at"] = datetime.now(timezone.utc).isoformat()
            data["revoke_reason"] = reason
            # Remove private key
            data["private_key"] = ""
            
            self._client.secrets.kv.v2.create_or_update_secret(
                mount_point=self.kv_mount_point,
                path=f"qsop/keys/{key_id}",
                secret=data,
            )
            
            logger.info(f"Key revoked: key={key_id}, reason={reason}")
            
        except Exception as e:
            raise KeyError(f"Key not found: {key_id}") from e
    
    def list_keys(self, owner: str | None = None) -> list[KeyMetadata]:
        """List all keys."""
        if self._client is None:
            raise RuntimeError("Vault client not initialized")
        
        result = []
        
        try:
            response = self._client.secrets.kv.v2.list_secrets(
                mount_point=self.kv_mount_point,
                path="qsop/keys",
            )
            
            for key_id in response["data"]["keys"]:
                key_id = key_id.rstrip("/")
                
                key_response = self._client.secrets.kv.v2.read_secret_version(
                    mount_point=self.kv_mount_point,
                    path=f"qsop/keys/{key_id}",
                )
                data = key_response["data"]["data"]
                
                if owner and data.get("owner") != owner:
                    continue
                
                result.append(KeyMetadata(
                    key_id=key_id,
                    key_type=data["key_type"],
                    algorithm=data["algorithm"],
                    owner=data["owner"],
                    status=data["status"],
                    created_at=datetime.fromisoformat(data["created_at"]),
                ))
                
        except Exception as e:
            logger.error(f"Failed to list keys: {e}")
        
        return result


@dataclass
class VaultPrivateKeyHandle:
    """Handle to a private key from Vault."""
    
    key_id: str
    private_key: bytes
    algorithm: str
    key_type: str
    
    def decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypt using this key."""
        if self.key_type != "kem":
            raise ValueError("Decrypt only available for KEM keys")
        
        from ...crypto.pqc import KEMAlgorithm, get_kem
        
        alg = KEMAlgorithm(self.algorithm)
        kem = get_kem(alg)
        return kem.decapsulate(ciphertext, self.private_key)
    
    def sign(self, message: bytes) -> bytes:
        """Sign using this key."""
        if self.key_type != "signature":
            raise ValueError("Sign only available for signature keys")
        
        from ...crypto.pqc import SignatureAlgorithm, get_signature_scheme
        
        alg = SignatureAlgorithm(self.algorithm)
        sig = get_signature_scheme(alg)
        return sig.sign(message, self.private_key)
    
    def __del__(self) -> None:
        """Clear private key from memory."""
        if hasattr(self, 'private_key'):
            try:
                import ctypes
                ctypes.memset(id(self.private_key), 0, len(self.private_key))
            except Exception:
                pass

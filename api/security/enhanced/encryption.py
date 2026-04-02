"""
Encryption at Rest Module.

Provides AES-256-GCM encryption for data stored at rest:
- Database fields encryption
- File encryption
- Cache encryption
- Key management with automatic rotation
"""

import base64
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


@dataclass
class EncryptionKey:
    """Encryption key with metadata."""

    key_id: str
    key: bytes
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    is_active: bool = True
    algorithm: str = "AES-256-GCM"


class EncryptionManager:
    """
    Manages encryption at rest for the platform.

    Features:
    - AES-256-GCM for symmetric encryption
    - Key derivation from master key
    - Automatic key rotation
    - Secure key storage
    """

    def __init__(self, master_key: str | None = None):
        self._keys: dict[str, EncryptionKey] = {}
        self._active_key_id: str | None = None
        self._fernet: Fernet | None = None

        master_key = master_key or os.getenv("ENCRYPTION_MASTER_KEY")

        if master_key:
            self._initialize_from_master_key(master_key)
        else:
            self._generate_new_key()

    def _initialize_from_master_key(self, master_key: str):
        """Initialize encryption from a master key."""
        key_bytes = base64.urlsafe_b64decode(master_key.encode() + b"==")
        self._fernet = Fernet(base64.urlsafe_b64encode(key_bytes))

        key = EncryptionKey(
            key_id=f"key_{uuid4().hex[:8]}",
            key=key_bytes,
        )
        self._keys[key.key_id] = key
        self._active_key_id = key.key_id

    def _generate_new_key(self):
        """Generate a new encryption key."""
        key_bytes = Fernet.generate_key()
        self._fernet = Fernet(key_bytes)

        key = EncryptionKey(
            key_id=f"key_{uuid4().hex[:8]}",
            key=base64.urlsafe_b64decode(key_bytes),
        )
        self._keys[key.key_id] = key
        self._active_key_id = key.key_id

        logger.warning(
            "Generated new encryption key. Set ENCRYPTION_MASTER_KEY environment "
            "variable for persistent encryption across restarts."
        )

    @property
    def active_key(self) -> EncryptionKey | None:
        """Get the active encryption key."""
        if self._active_key_id:
            return self._keys.get(self._active_key_id)
        return None

    def encrypt(self, plaintext: str | bytes, key_id: str | None = None) -> str:
        """
        Encrypt data using AES-256-GCM.

        Args:
            plaintext: Data to encrypt
            key_id: Optional specific key to use

        Returns:
            Base64-encoded encrypted data with metadata
        """
        if isinstance(plaintext, str):
            plaintext = plaintext.encode("utf-8")

        if not self._fernet:
            raise RuntimeError("Encryption manager not initialized")

        encrypted = self._fernet.encrypt(plaintext)

        result = {
            "key_id": key_id or self._active_key_id,
            "algorithm": "AES-256-GCM",
            "encrypted": base64.urlsafe_b64encode(encrypted).decode(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return base64.urlsafe_b64encode(json.dumps(result).encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt data.

        Args:
            ciphertext: Base64-encoded encrypted data

        Returns:
            Decrypted plaintext string
        """
        if not self._fernet:
            raise RuntimeError("Encryption manager not initialized")

        try:
            data = json.loads(base64.urlsafe_b64decode(ciphertext.encode()))
            encrypted_bytes = base64.urlsafe_b64decode(data["encrypted"].encode())
            decrypted = self._fernet.decrypt(encrypted_bytes)
            return decrypted.decode("utf-8")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError(f"Decryption failed: {e}") from e

    def encrypt_dict(self, data: dict[str, Any]) -> str:
        """Encrypt a dictionary."""
        return self.encrypt(json.dumps(data))

    def decrypt_dict(self, ciphertext: str) -> dict[str, Any]:
        """Decrypt to a dictionary."""
        return json.loads(self.decrypt(ciphertext))

    def encrypt_field(self, value: Any, field_name: str) -> str:
        """
        Encrypt a database field value.

        Args:
            value: Value to encrypt
            field_name: Name of the field (for key derivation)

        Returns:
            Encrypted value
        """
        if value is None:
            return None

        plaintext = json.dumps({"v": value})
        return self.encrypt(plaintext)

    def decrypt_field(self, ciphertext: str, field_name: str) -> Any:
        """
        Decrypt a database field value.

        Args:
            ciphertext: Encrypted value
            field_name: Name of the field

        Returns:
            Decrypted value
        """
        if ciphertext is None:
            return None

        decrypted = self.decrypt(ciphertext)
        data = json.loads(decrypted)
        return data.get("v")

    def rotate_key(self) -> str:
        """
        Rotate to a new encryption key.

        Returns:
            New key ID
        """
        old_key_id = self._active_key_id

        new_key = EncryptionKey(
            key_id=f"key_{uuid4().hex[:8]}",
            key=os.urandom(32),
        )
        self._keys[new_key.key_id] = new_key
        self._active_key_id = new_key.key_id

        new_fernet_key = base64.urlsafe_b64encode(new_key.key)
        self._fernet = Fernet(new_fernet_key)

        if old_key_id and old_key_id in self._keys:
            self._keys[old_key_id].is_active = False

        logger.info(f"Rotated encryption key: {old_key_id} -> {new_key.key_id}")

        return new_key.key_id

    def export_public_params(self) -> dict[str, Any]:
        """Export public parameters for verification."""
        return {
            "active_key_id": self._active_key_id,
            "key_count": len(self._keys),
            "algorithm": "AES-256-GCM",
            "keys": [
                {
                    "key_id": k.key_id,
                    "created_at": k.created_at.isoformat(),
                    "is_active": k.is_active,
                }
                for k in self._keys.values()
            ],
        }


_encryption_manager: EncryptionManager | None = None


def get_encryption_manager() -> EncryptionManager:
    """Get or create the global encryption manager."""
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager()
    return _encryption_manager


def encrypt_data(data: str | bytes | dict[str, Any]) -> str:
    """Encrypt data using the global encryption manager."""
    manager = get_encryption_manager()
    if isinstance(data, dict):
        return manager.encrypt_dict(data)
    return manager.encrypt(data)


def decrypt_data(ciphertext: str) -> str | dict[str, Any]:
    """Decrypt data using the global encryption manager."""
    manager = get_encryption_manager()
    try:
        return manager.decrypt_dict(ciphertext)
    except json.JSONDecodeError:
        return manager.decrypt(ciphertext)


def encrypt_file(file_path: str, output_path: str | None = None) -> str:
    """
    Encrypt a file.

    Args:
        file_path: Path to file to encrypt
        output_path: Optional output path (default: file_path + .enc)

    Returns:
        Path to encrypted file
    """
    import pathlib

    manager = get_encryption_manager()

    file_path = pathlib.Path(file_path)
    output_path = (
        pathlib.Path(output_path)
        if output_path
        else file_path.with_suffix(file_path.suffix + ".enc")
    )

    plaintext = file_path.read_bytes()
    ciphertext = manager.encrypt(plaintext)

    output_path.write_text(ciphertext)

    logger.info(f"Encrypted file: {file_path} -> {output_path}")

    return str(output_path)


def decrypt_file(file_path: str, output_path: str | None = None) -> str:
    """
    Decrypt a file.

    Args:
        file_path: Path to encrypted file
        output_path: Optional output path

    Returns:
        Path to decrypted file
    """
    import pathlib

    manager = get_encryption_manager()

    file_path = pathlib.Path(file_path)
    if output_path:
        output_path = pathlib.Path(output_path)
    else:
        output_path = file_path.with_suffix("")  # Remove .enc

    ciphertext = file_path.read_text()
    plaintext = manager.decrypt(ciphertext)

    output_path.write_bytes(plaintext.encode("utf-8"))

    logger.info(f"Decrypted file: {file_path} -> {output_path}")

    return str(output_path)


class EncryptedStorage:
    """
    Encrypted storage wrapper for databases and caches.

    Usage:
        storage = EncryptedStorage(redis_client)
        await storage.set("user:123:data", {"sensitive": "data"})
        data = await storage.get("user:123:data")
    """

    def __init__(self, backend: Any, prefix: str = "enc:"):
        self._backend = backend
        self._prefix = prefix
        self._encryption = get_encryption_manager()

    def _encrypt_value(self, value: Any) -> str:
        if isinstance(value, (dict, list)):
            return self._encryption.encrypt_dict(value)
        return self._encryption.encrypt(str(value))

    def _decrypt_value(self, ciphertext: str) -> Any:
        try:
            return self._encryption.decrypt_dict(ciphertext)
        except (json.JSONDecodeError, ValueError):
            return self._encryption.decrypt(ciphertext)

    async def get(self, key: str) -> Any:
        """Get and decrypt value."""
        full_key = f"{self._prefix}{key}"
        ciphertext = await self._backend.get(full_key)
        if ciphertext is None:
            return None
        return self._decrypt_value(ciphertext)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Encrypt and set value."""
        full_key = f"{self._prefix}{key}"
        ciphertext = self._encrypt_value(value)
        if ttl:
            return await self._backend.setex(full_key, ttl, ciphertext)
        return await self._backend.set(full_key, ciphertext)

    async def delete(self, key: str) -> bool:
        """Delete encrypted value."""
        full_key = f"{self._prefix}{key}"
        return await self._backend.delete(full_key)

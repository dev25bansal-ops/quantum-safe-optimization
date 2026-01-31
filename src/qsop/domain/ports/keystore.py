"""
Key store port definition.

Defines the protocol for cryptographic key lifecycle management
including storage, retrieval, rotation, and revocation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class KeyType(Enum):
    """Types of cryptographic keys."""

    KEM = "kem"
    SIGNATURE = "signature"
    SYMMETRIC = "symmetric"


class KeyStatus(Enum):
    """Status of a cryptographic key."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    COMPROMISED = "compromised"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING_ROTATION = "pending_rotation"


@dataclass(frozen=True)
class KeyMetadata:
    """
    Metadata about a stored key.

    Attributes:
        key_id: Unique identifier for the key.
        key_type: Type of key (KEM, signature, symmetric).
        algorithm: Algorithm name (e.g., 'ML-KEM-768').
        status: Current key status.
        created_at: When the key was created.
        expires_at: When the key expires (if applicable).
        rotated_from: ID of the key this was rotated from.
        rotated_to: ID of the key this was rotated to.
        owner_id: ID of the key owner.
        usage_count: Number of times the key has been used.
        last_used_at: When the key was last used.
        tags: Tags for key categorization.
        custom_data: Additional custom metadata.
    """

    key_id: str
    key_type: KeyType
    algorithm: str
    status: KeyStatus = KeyStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    rotated_from: str | None = None
    rotated_to: str | None = None
    owner_id: str | None = None
    usage_count: int = 0
    last_used_at: datetime | None = None
    tags: tuple[str, ...] = ()
    custom_data: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        """Check if the key is currently active."""
        return self.status == KeyStatus.ACTIVE

    @property
    def is_expired(self) -> bool:
        """Check if the key has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def is_usable(self) -> bool:
        """Check if the key can be used for new operations."""
        return self.is_active and not self.is_expired


@runtime_checkable
class KeyStore(Protocol):
    """
    Protocol for cryptographic key storage and management.

    Provides secure storage, retrieval, rotation, and lifecycle
    management for cryptographic keys.
    """

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
        """
        Store a new key pair.

        Args:
            key_type: Type of the key.
            algorithm: Algorithm name.
            public_key: The public key bytes.
            secret_key: The secret key bytes (stored encrypted).
            key_id: Optional key ID (generated if not provided).
            expires_at: Optional expiration time.
            owner_id: Optional owner identifier.
            tags: Optional tags for categorization.
            **metadata: Additional metadata.

        Returns:
            The key ID.

        Raises:
            KeyStoreError: If storage fails.
        """
        ...

    def get_public_key(self, key_id: str) -> bytes:
        """
        Retrieve a public key.

        Args:
            key_id: The key identifier.

        Returns:
            The public key bytes.

        Raises:
            KeyStoreError: If key not found or retrieval fails.
        """
        ...

    def get_secret_key(self, key_id: str) -> bytes:
        """
        Retrieve a secret key.

        Args:
            key_id: The key identifier.

        Returns:
            The secret key bytes.

        Raises:
            KeyStoreError: If key not found, access denied, or retrieval fails.
        """
        ...

    def get_metadata(self, key_id: str) -> KeyMetadata:
        """
        Retrieve key metadata.

        Args:
            key_id: The key identifier.

        Returns:
            The key metadata.

        Raises:
            KeyStoreError: If key not found.
        """
        ...

    def list_keys(
        self,
        key_type: KeyType | None = None,
        status: KeyStatus | None = None,
        owner_id: str | None = None,
        tags: tuple[str, ...] | None = None,
    ) -> list[KeyMetadata]:
        """
        List keys matching the given criteria.

        Args:
            key_type: Filter by key type.
            status: Filter by status.
            owner_id: Filter by owner.
            tags: Filter by tags (all must match).

        Returns:
            List of matching key metadata.

        Raises:
            KeyStoreError: If listing fails.
        """
        ...

    def rotate_key(
        self,
        key_id: str,
        new_public_key: bytes,
        new_secret_key: bytes,
        new_key_id: str | None = None,
    ) -> str:
        """
        Rotate a key to a new version.

        The old key is marked as inactive but retained.

        Args:
            key_id: ID of the key to rotate.
            new_public_key: New public key bytes.
            new_secret_key: New secret key bytes.
            new_key_id: Optional ID for the new key.

        Returns:
            The new key ID.

        Raises:
            KeyStoreError: If rotation fails.
        """
        ...

    def revoke_key(self, key_id: str, reason: str = "") -> None:
        """
        Revoke a key.

        Revoked keys cannot be used for new operations.

        Args:
            key_id: The key to revoke.
            reason: Optional revocation reason.

        Raises:
            KeyStoreError: If revocation fails.
        """
        ...

    def delete_key(self, key_id: str) -> None:
        """
        Permanently delete a key.

        Warning: This is irreversible. Consider revocation instead.

        Args:
            key_id: The key to delete.

        Raises:
            KeyStoreError: If deletion fails.
        """
        ...

    def record_usage(self, key_id: str) -> None:
        """
        Record that a key was used.

        Updates usage_count and last_used_at.

        Args:
            key_id: The key that was used.

        Raises:
            KeyStoreError: If recording fails.
        """
        ...

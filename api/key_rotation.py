"""
Key rotation service for PQC keys.

Handles automatic key rotation, expiration, and lifecycle management.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from quantum_safe_crypto import KemKeyPair, SigningKeyPair

logger = logging.getLogger(__name__)


@dataclass
class KeyMetadata:
    """Metadata for a managed key."""

    key_id: str
    key_type: str
    public_key: str
    security_level: int
    created_at: datetime
    expires_at: datetime
    is_active: bool = True
    rotated_at: datetime | None = None
    rotated_from: str | None = None


@dataclass
class RotationPolicy:
    """Policy for key rotation."""

    max_age_days: int = 90
    rotate_before_days: int = 7
    max_usage_count: int | None = None
    on_expiry: str = "rotate"


class KeyRotationService:
    """
    Manages PQC key lifecycle and rotation.

    Features:
    - Automatic key rotation based on age
    - Pre-rotation for seamless transitions
    - Key expiration management
    - Rotation audit trail
    """

    def __init__(
        self,
        rotation_policy: RotationPolicy | None = None,
        store: Any | None = None,
    ):
        self.policy = rotation_policy or RotationPolicy()
        self.store = store
        self._keys: dict[str, KeyMetadata] = {}
        self._rotation_task: asyncio.Task | None = None
        self._running = False

    async def generate_key(
        self,
        key_type: str,
        security_level: int = 3,
        expires_in_days: int | None = None,
    ) -> KeyMetadata:
        """Generate a new key with metadata."""
        import uuid

        key_id = str(uuid.uuid4())
        expires_in = expires_in_days or self.policy.max_age_days

        if key_type == "kem":
            keypair = KemKeyPair(security_level=security_level)
        elif key_type == "signing":
            keypair = SigningKeyPair(security_level=security_level)
        else:
            raise ValueError(f"Unknown key type: {key_type}")

        metadata = KeyMetadata(
            key_id=key_id,
            key_type=key_type,
            public_key=keypair.public_key,
            security_level=security_level,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(days=expires_in),
        )

        self._keys[key_id] = metadata

        logger.info(
            f"Generated {key_type} key",
            extra={
                "key_id": key_id,
                "security_level": security_level,
                "expires_at": metadata.expires_at.isoformat(),
            },
        )

        return metadata

    async def rotate_key(self, key_id: str) -> KeyMetadata:
        """Rotate an existing key."""
        if key_id not in self._keys:
            raise KeyError(f"Key {key_id} not found")

        old_key = self._keys[key_id]
        old_key.is_active = False

        new_key = await self.generate_key(
            key_type=old_key.key_type,
            security_level=old_key.security_level,
        )

        new_key.rotated_from = key_id
        new_key.rotated_at = datetime.now(UTC)

        logger.info(
            "Rotated key",
            extra={
                "old_key_id": key_id,
                "new_key_id": new_key.key_id,
            },
        )

        return new_key

    def get_key(self, key_id: str) -> KeyMetadata | None:
        """Get key metadata."""
        return self._keys.get(key_id)

    def get_active_keys(self, key_type: str | None = None) -> list[KeyMetadata]:
        """Get all active keys, optionally filtered by type."""
        keys = [k for k in self._keys.values() if k.is_active]
        if key_type:
            keys = [k for k in keys if k.key_type == key_type]
        return keys

    def get_expiring_keys(self, within_days: int = 7) -> list[KeyMetadata]:
        """Get keys expiring within the specified days."""
        threshold = datetime.now(UTC) + timedelta(days=within_days)
        return [k for k in self._keys.values() if k.is_active and k.expires_at <= threshold]

    async def check_and_rotate(self) -> list[KeyMetadata]:
        """Check for keys needing rotation and rotate them."""
        rotated = []
        expiring = self.get_expiring_keys(within_days=self.policy.rotate_before_days)

        for key in expiring:
            try:
                new_key = await self.rotate_key(key.key_id)
                rotated.append(new_key)
            except Exception as e:
                logger.error(f"Failed to rotate key {key.key_id}: {e}")

        return rotated

    async def start_rotation_scheduler(self, interval_hours: int = 24) -> None:
        """Start background rotation scheduler."""
        if self._running:
            return

        self._running = True
        self._rotation_task = asyncio.create_task(self._rotation_loop(interval_hours))
        logger.info(f"Started key rotation scheduler (interval: {interval_hours}h)")

    async def stop_rotation_scheduler(self) -> None:
        """Stop background rotation scheduler."""
        self._running = False
        if self._rotation_task:
            self._rotation_task.cancel()
            try:
                await self._rotation_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped key rotation scheduler")

    async def _rotation_loop(self, interval_hours: int) -> None:
        """Background task for periodic rotation checks."""
        while self._running:
            try:
                await asyncio.sleep(interval_hours * 3600)
                rotated = await self.check_and_rotate()
                if rotated:
                    logger.info(f"Auto-rotated {len(rotated)} keys")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Rotation check failed: {e}")

    def get_status(self) -> dict[str, Any]:
        """Get rotation service status."""
        active_keys = self.get_active_keys()
        expiring_keys = self.get_expiring_keys()

        return {
            "total_keys": len(self._keys),
            "active_keys": len(active_keys),
            "expiring_keys": len(expiring_keys),
            "scheduler_running": self._running,
            "policy": {
                "max_age_days": self.policy.max_age_days,
                "rotate_before_days": self.policy.rotate_before_days,
            },
            "keys_by_type": {
                key_type: len([k for k in active_keys if k.key_type == key_type])
                for key_type in ["kem", "signing"]
            },
        }

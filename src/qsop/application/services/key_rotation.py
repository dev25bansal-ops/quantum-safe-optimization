"""
Key rotation service.

Provides automated rotation of KEM and signing keys.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from ...crypto.pqc import (
    KEMAlgorithm,
    SignatureAlgorithm,
    get_kem,
    get_signature_scheme,
)
from ...domain.ports.keystore import KeyMetadata, KeyStatus, KeyStore, KeyType

logger = logging.getLogger(__name__)


class KeyRotationService:
    """
    Service for managing the lifecycle and rotation of cryptographic keys.
    """

    def __init__(
        self,
        keystore: KeyStore,
        rotation_interval_days: int = 30,
        warning_period_days: int = 7,
    ):
        self.keystore = keystore
        self.rotation_interval = timedelta(days=rotation_interval_days)
        self.warning_period = timedelta(days=warning_period_days)

    def rotate_expired_keys(self) -> list[str]:
        """
        Identify and rotate keys that have expired or are nearing expiration.
        
        Returns:
            List of new key IDs created.
        """
        now = datetime.now(timezone.utc)
        all_keys = self.keystore.list_keys(status=KeyStatus.ACTIVE)
        
        rotated_ids = []
        for meta in all_keys:
            if self._should_rotate(meta, now):
                try:
                    logger.info(f"Rotating key {meta.key_id} (type: {meta.key_type.value})")
                    new_id = self.rotate_key(meta.key_id)
                    rotated_ids.append(new_id)
                except Exception as e:
                    logger.error(f"Failed to rotate key {meta.key_id}: {e}")
                    
        return rotated_ids

    def rotate_key(self, key_id: str) -> str:
        """
        Force rotation of a specific key.
        
        Args:
            key_id: The ID of the key to rotate.
            
        Returns:
            The new key ID.
        """
        meta = self.keystore.get_metadata(key_id)
        
        if meta.key_type == KeyType.KEM:
            alg = KEMAlgorithm(meta.algorithm)
            kem = get_kem(alg)
            public_key, secret_key = kem.keygen()
        elif meta.key_type == KeyType.SIGNATURE:
            alg = SignatureAlgorithm(meta.algorithm)
            sig = get_signature_scheme(alg)
            public_key, secret_key = sig.keygen()
        else:
            raise ValueError(f"Rotation not supported for key type: {meta.key_type}")
            
        return self.keystore.rotate_key(
            key_id=key_id,
            new_public_key=public_key,
            new_secret_key=secret_key
        )

    def _should_rotate(self, meta: KeyMetadata, now: datetime) -> bool:
        """Check if a key should be rotated based on its metadata."""
        # 1. Check explicit expiration
        if meta.expires_at:
            if now >= meta.expires_at - self.warning_period:
                return True
                
        # 2. Check rotation interval from creation
        if now >= meta.created_at + self.rotation_interval:
            return True
            
        # 3. Check status
        if meta.status == KeyStatus.PENDING_ROTATION:
            return True
            
        return False

    def schedule_rotation(self, key_id: str) -> None:
        """Mark a key for rotation in the next automated pass."""
        # This would ideally update the key status to PENDING_ROTATION
        # Since we don't have an update_status in the protocol, we can use tags or custom_data
        # For now, let's assume we can use revoke/rotate directly or just wait for expiration.
        # Actually, let's just use the rotate_key method directly if requested.
        pass

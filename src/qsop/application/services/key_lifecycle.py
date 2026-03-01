"""
Key lifecycle management service.

Automates periodic key rotation and monitoring.
"""

from __future__ import annotations

import asyncio
import logging

from ...domain.ports.keystore import KeyStore
from .key_rotation import KeyRotationService

logger = logging.getLogger(__name__)


class KeyLifecycleManager:
    """
    Background service for automated key lifecycle management.

    Periodically runs the KeyRotationService to ensure keys are rotated
    according to security policies.
    """

    def __init__(
        self,
        keystore: KeyStore,
        check_interval_seconds: int = 3600,  # Default: hourly
        rotation_interval_days: int = 30,
        warning_period_days: int = 7,
    ):
        self._rotation_service = KeyRotationService(
            keystore=keystore,
            rotation_interval_days=rotation_interval_days,
            warning_period_days=warning_period_days,
        )
        self._check_interval = check_interval_seconds
        self._is_running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the lifecycle management background task."""
        if self._is_running:
            return

        self._is_running = True
        self._task = asyncio.create_task(self._run_lifecycle_loop())
        logger.info("KeyLifecycleManager started")

    async def stop(self) -> None:
        """Stop the lifecycle management background task."""
        if not self._is_running:
            return

        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("KeyLifecycleManager stopped")

    async def _run_lifecycle_loop(self) -> None:
        """Main lifecycle loop."""
        while self._is_running:
            try:
                logger.info("Running automated key rotation check...")
                rotated_ids = self._rotation_service.rotate_expired_keys()
                if rotated_ids:
                    logger.info(f"Automated rotation completed. Rotated {len(rotated_ids)} keys.")
            except Exception as e:
                logger.exception(f"Error during key lifecycle check: {e}")

            try:
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break

    def force_rotation(self, key_id: str) -> str:
        """Manually trigger rotation for a specific key."""
        return self._rotation_service.rotate_key(key_id)

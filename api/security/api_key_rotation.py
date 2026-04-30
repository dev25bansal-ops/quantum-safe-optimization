"""
API Key Rotation Service.

Provides automated API key rotation with:
- Scheduled rotation based on key age
- Grace period for key transition
- Notification of rotation events
- Audit logging
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

import structlog

logger = structlog.get_logger()


class RotationPolicy(str, Enum):
    """Key rotation policies."""

    MANUAL = "manual"
    DAYS_30 = "30_days"
    DAYS_60 = "60_days"
    DAYS_90 = "90_days"
    YEARLY = "yearly"


class RotationStatus(str, Enum):
    """Rotation status for a key."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RotationConfig:
    """Configuration for key rotation."""

    policy: RotationPolicy = RotationPolicy.DAYS_90
    grace_period_hours: int = 24
    notify_before_days: int = 7
    auto_rotate_enabled: bool = True
    max_key_age_days: int = 90


@dataclass
class RotationEvent:
    """A key rotation event."""

    event_id: str
    key_id: str
    old_key_prefix: str
    new_key_prefix: str
    status: RotationStatus
    started_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class APIKeyRotationService:
    """
    Service for automated API key rotation.

    Features:
    - Scheduled rotation based on age
    - Grace period for transition
    - Event logging and notifications
    - Failed rotation handling
    """

    def __init__(self, config: RotationConfig | None = None):
        self.config = config or RotationConfig()
        self._rotation_history: dict[str, list[RotationEvent]] = {}
        self._pending_rotations: dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    def _get_max_age_for_policy(self, policy: RotationPolicy) -> timedelta:
        """Get maximum age for rotation policy."""
        policy_days = {
            RotationPolicy.MANUAL: timedelta(days=36500),
            RotationPolicy.DAYS_30: timedelta(days=30),
            RotationPolicy.DAYS_60: timedelta(days=60),
            RotationPolicy.DAYS_90: timedelta(days=90),
            RotationPolicy.YEARLY: timedelta(days=365),
        }
        return policy_days.get(policy, timedelta(days=90))

    async def check_rotation_required(
        self, key_id: str, created_at: datetime, policy: RotationPolicy | None = None
    ) -> tuple[bool, str]:
        """
        Check if a key requires rotation.

        Returns:
            Tuple of (requires_rotation, reason)
        """
        policy = policy or self.config.policy
        max_age = self._get_max_age_for_policy(policy)
        age = datetime.now(UTC) - created_at

        if policy == RotationPolicy.MANUAL:
            return False, "Manual rotation policy - no automatic rotation"

        if age >= max_age:
            return True, f"Key age ({age.days} days) exceeds maximum ({max_age.days} days)"

        notify_threshold = max_age - timedelta(days=self.config.notify_before_days)
        if age >= notify_threshold:
            days_remaining = (max_age - age).days
            return False, f"Rotation due in {days_remaining} days"

        return False, f"Key age: {age.days} days, max: {max_age.days} days"

    async def schedule_rotation(
        self, key_id: str, scheduled_at: datetime | None = None, reason: str = "Scheduled rotation"
    ) -> str:
        """Schedule a key rotation."""
        async with self._lock:
            scheduled_time = scheduled_at or datetime.now(UTC) + timedelta(
                hours=self.config.grace_period_hours
            )
            self._pending_rotations[key_id] = scheduled_time

            logger.info(
                "api_key_rotation_scheduled",
                key_id=key_id,
                scheduled_at=scheduled_time.isoformat(),
                reason=reason,
            )

            return f"Rotation scheduled for {scheduled_time.isoformat()}"

    async def perform_rotation(
        self, key_id: str, rotate_func: callable, user_id: str
    ) -> RotationEvent:
        """
        Perform actual key rotation.

        Args:
            key_id: The key to rotate
            rotate_func: Async function to call for rotation
            user_id: User initiating rotation

        Returns:
            RotationEvent with results
        """
        event_id = f"rot_{uuid4().hex[:12]}"
        event = RotationEvent(
            event_id=event_id,
            key_id=key_id,
            old_key_prefix="",
            new_key_prefix="",
            status=RotationStatus.IN_PROGRESS,
            started_at=datetime.now(UTC),
        )

        try:
            result = await rotate_func(key_id)

            event.old_key_prefix = result.get("old_key_prefix", "")
            event.new_key_prefix = result.get("new_key_prefix", "")
            event.status = RotationStatus.COMPLETED
            event.completed_at = datetime.now(UTC)

            async with self._lock:
                if key_id not in self._rotation_history:
                    self._rotation_history[key_id] = []
                self._rotation_history[key_id].append(event)

                self._pending_rotations.pop(key_id, None)

            logger.info(
                "api_key_rotated",
                event_id=event_id,
                key_id=key_id,
                user_id=user_id,
                old_prefix=event.old_key_prefix,
                new_prefix=event.new_key_prefix,
            )

        except Exception as e:
            event.status = RotationStatus.FAILED
            event.error = str(e)
            event.completed_at = datetime.now(UTC)

            logger.error("api_key_rotation_failed", event_id=event_id, key_id=key_id, error=str(e))

        return event

    async def get_rotation_status(self, key_id: str) -> dict[str, Any]:
        """Get rotation status for a key."""
        history = self._rotation_history.get(key_id, [])
        pending = self._pending_rotations.get(key_id)

        latest_event = history[-1] if history else None

        return {
            "key_id": key_id,
            "rotation_count": len(history),
            "last_rotation": latest_event.completed_at.isoformat()
            if latest_event and latest_event.completed_at
            else None,
            "last_status": latest_event.status.value if latest_event else None,
            "pending_rotation": pending.isoformat() if pending else None,
            "rotation_history": [
                {
                    "event_id": e.event_id,
                    "status": e.status.value,
                    "started_at": e.started_at.isoformat(),
                    "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                    "error": e.error,
                }
                for e in history[-5:]
            ],
        }

    async def get_keys_due_for_rotation(self, keys: list[dict]) -> list[dict]:
        """Get keys that are due for rotation."""
        due_keys = []

        for key in keys:
            created_at = datetime.fromisoformat(key["created_at"].replace("Z", "+00:00"))
            policy = RotationPolicy(key.get("rotation_policy", self.config.policy.value))

            requires_rotation, reason = await self.check_rotation_required(
                key["key_id"], created_at, policy
            )

            if requires_rotation:
                due_keys.append({**key, "rotation_reason": reason})

        return due_keys

    async def run_scheduled_rotations(
        self, get_keys_func: callable, rotate_func: callable
    ) -> list[RotationEvent]:
        """Run all scheduled rotations."""
        results = []

        for key_id, scheduled_time in list(self._pending_rotations.items()):
            if datetime.now(UTC) >= scheduled_time:
                try:
                    event = await self.perform_rotation(
                        key_id=key_id, rotate_func=rotate_func, user_id="system"
                    )
                    results.append(event)
                except Exception as e:
                    logger.error("scheduled_rotation_error", key_id=key_id, error=str(e))

        return results


rotation_service = APIKeyRotationService()

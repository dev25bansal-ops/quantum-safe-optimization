"""
Secret Rotation Module.

Provides automatic secret rotation for:
- JWT secrets
- API keys
- Database credentials
- Encryption keys
"""

import asyncio
import base64
import hashlib
import logging
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SecretType(str, Enum):
    """Types of secrets."""

    JWT_SECRET = "jwt_secret"
    API_KEY = "api_key"
    DATABASE_PASSWORD = "database_password"
    ENCRYPTION_KEY = "encryption_key"
    PQC_SIGNING_KEY = "pqc_signing_key"
    PQC_ENCRYPTION_KEY = "pqc_encryption_key"
    REDIS_PASSWORD = "redis_password"
    OAUTH_CLIENT_SECRET = "oauth_client_secret"
    WEBHOOK_SECRET = "webhook_secret"


class RotationPolicy(BaseModel):
    """Policy for secret rotation."""

    secret_type: SecretType
    rotation_interval_days: int = Field(default=30, ge=1, le=365)
    grace_period_hours: int = Field(default=24, ge=1, le=168)
    max_age_days: int = Field(default=90, ge=1, le=365)
    auto_rotate: bool = True
    notify_before_days: int = Field(default=7, ge=1, le=30)
    retain_old_versions: int = Field(default=2, ge=1, le=5)
    min_length: int = Field(default=32, ge=16)
    algorithm: str = "random"


@dataclass
class SecretMetadata:
    """Metadata about a secret."""

    secret_id: str
    secret_type: SecretType
    version: int
    created_at: datetime
    expires_at: datetime
    rotated_at: datetime | None = None
    rotated_from: str | None = None
    is_active: bool = True
    is_current: bool = True
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class RotatedSecret:
    """A rotated secret with metadata."""

    metadata: SecretMetadata
    value: str
    previous_values: list[str] = field(default_factory=list)


class SecretRotationManager:
    """
    Manages automatic secret rotation.

    Features:
    - Scheduled rotation based on policies
    - Grace period for seamless rotation
    - Version history for rollback
    - Notifications before expiration
    - Integration with external secret stores
    """

    def __init__(self):
        self._secrets: dict[str, RotatedSecret] = {}
        self._policies: dict[SecretType, RotationPolicy] = {}
        self._rotation_handlers: dict[SecretType, Callable[[str], None]] = {}
        self._scheduler_task: asyncio.Task | None = None
        self._running: bool = False

        self._load_default_policies()

    def _load_default_policies(self):
        """Load default rotation policies."""
        default_policies = [
            RotationPolicy(
                secret_type=SecretType.JWT_SECRET,
                rotation_interval_days=30,
                grace_period_hours=24,
                notify_before_days=7,
            ),
            RotationPolicy(
                secret_type=SecretType.API_KEY,
                rotation_interval_days=90,
                grace_period_hours=48,
                notify_before_days=14,
            ),
            RotationPolicy(
                secret_type=SecretType.DATABASE_PASSWORD,
                rotation_interval_days=90,
                grace_period_hours=24,
                notify_before_days=7,
            ),
            RotationPolicy(
                secret_type=SecretType.ENCRYPTION_KEY,
                rotation_interval_days=365,
                grace_period_hours=72,
                notify_before_days=30,
                retain_old_versions=3,
            ),
            RotationPolicy(
                secret_type=SecretType.PQC_SIGNING_KEY,
                rotation_interval_days=365,
                grace_period_hours=168,
                notify_before_days=30,
            ),
        ]

        for policy in default_policies:
            self._policies[policy.secret_type] = policy

    def register_handler(
        self,
        secret_type: SecretType,
        handler: Callable[[str], None],
    ):
        """Register a handler for secret rotation."""
        self._rotation_handlers[secret_type] = handler

    def generate_secret(self, secret_type: SecretType, length: int | None = None) -> str:
        """Generate a new secret."""
        policy = self._policies.get(secret_type)
        length = length or (policy.min_length if policy else 32)

        if secret_type in (SecretType.JWT_SECRET, SecretType.API_KEY, SecretType.WEBHOOK_SECRET):
            return secrets.token_urlsafe(length)

        elif secret_type == SecretType.DATABASE_PASSWORD:
            chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
            return "".join(secrets.choice(chars) for _ in range(length))

        elif secret_type == SecretType.ENCRYPTION_KEY:
            return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()

        else:
            return secrets.token_urlsafe(length)

    def create_secret(
        self,
        secret_type: SecretType,
        value: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> RotatedSecret:
        """Create a new secret."""
        if value is None:
            value = self.generate_secret(secret_type)

        now = datetime.now(timezone.utc)
        policy = self._policies.get(secret_type)

        expires_at = now + timedelta(days=policy.max_age_days if policy else 90)

        metadata = SecretMetadata(
            secret_id=f"sec_{uuid4().hex[:12]}",
            secret_type=secret_type,
            version=1,
            created_at=now,
            expires_at=expires_at,
            tags=tags or {},
        )

        secret = RotatedSecret(
            metadata=metadata,
            value=value,
        )

        self._secrets[metadata.secret_id] = secret

        logger.info(f"Created secret: {metadata.secret_id} (type={secret_type.value})")

        return secret

    def rotate_secret(
        self,
        secret_id: str,
        new_value: str | None = None,
    ) -> RotatedSecret:
        """Rotate a secret."""
        if secret_id not in self._secrets:
            raise ValueError(f"Secret not found: {secret_id}")

        old_secret = self._secrets[secret_id]
        secret_type = old_secret.metadata.secret_type
        policy = self._policies.get(secret_type)

        if new_value is None:
            new_value = self.generate_secret(secret_type)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=policy.max_age_days if policy else 90)

        old_secret.metadata.is_current = False
        old_secret.metadata.rotated_at = now

        new_version = old_secret.metadata.version + 1

        metadata = SecretMetadata(
            secret_id=f"sec_{uuid4().hex[:12]}",
            secret_type=secret_type,
            version=new_version,
            created_at=now,
            expires_at=expires_at,
            rotated_from=secret_id,
            tags=old_secret.metadata.tags,
        )

        previous_values = [old_secret.value]
        if policy:
            previous_values.extend(old_secret.previous_values[: policy.retain_old_versions - 1])

        new_secret = RotatedSecret(
            metadata=metadata,
            value=new_value,
            previous_values=previous_values,
        )

        self._secrets[metadata.secret_id] = new_secret

        if secret_type in self._rotation_handlers:
            try:
                self._rotation_handlers[secret_type](new_value)
            except Exception as e:
                logger.error(f"Rotation handler failed for {secret_type}: {e}")

        logger.info(f"Rotated secret: {secret_id} -> {metadata.secret_id}")

        return new_secret

    def get_current_secret(self, secret_type: SecretType) -> RotatedSecret | None:
        """Get the current active secret for a type."""
        for secret in self._secrets.values():
            if secret.metadata.secret_type == secret_type and secret.metadata.is_current:
                return secret
        return None

    def get_secret_value(self, secret_id: str) -> str | None:
        """Get secret value by ID."""
        secret = self._secrets.get(secret_id)
        return secret.value if secret else None

    def get_secrets_expiring_soon(self, days: int = 7) -> list[SecretMetadata]:
        """Get secrets expiring within the given days."""
        now = datetime.now(timezone.utc)
        threshold = now + timedelta(days=days)

        expiring = []
        for secret in self._secrets.values():
            if secret.metadata.is_current and secret.metadata.expires_at <= threshold:
                expiring.append(secret.metadata)

        return expiring

    async def start_scheduler(self):
        """Start the rotation scheduler."""
        if self._running:
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._rotation_loop())

        logger.info("Secret rotation scheduler started")

    async def stop_scheduler(self):
        """Stop the rotation scheduler."""
        self._running = False

        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        logger.info("Secret rotation scheduler stopped")

    async def _rotation_loop(self):
        """Background task to check for needed rotations."""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Check every hour

                expiring = self.get_secrets_expiring_soon(days=7)

                for metadata in expiring:
                    if metadata.expires_at <= datetime.now(timezone.utc):
                        logger.warning(f"Secret {metadata.secret_id} has expired")

                        policy = self._policies.get(metadata.secret_type)
                        if policy and policy.auto_rotate:
                            try:
                                self.rotate_secret(metadata.secret_id)
                                logger.info(f"Auto-rotated expired secret: {metadata.secret_id}")
                            except Exception as e:
                                logger.error(f"Auto-rotation failed for {metadata.secret_id}: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Rotation loop error: {e}")

    def get_rotation_status(self) -> dict[str, Any]:
        """Get rotation status for all secrets."""
        now = datetime.now(timezone.utc)

        secrets_status = []
        for secret in self._secrets.values():
            days_until_expiry = (secret.metadata.expires_at - now).days

            secrets_status.append(
                {
                    "secret_id": secret.metadata.secret_id,
                    "type": secret.metadata.secret_type.value,
                    "version": secret.metadata.version,
                    "created_at": secret.metadata.created_at.isoformat(),
                    "expires_at": secret.metadata.expires_at.isoformat(),
                    "days_until_expiry": days_until_expiry,
                    "is_current": secret.metadata.is_current,
                    "needs_rotation": days_until_expiry <= 7,
                }
            )

        return {
            "total_secrets": len(self._secrets),
            "secrets_needing_rotation": sum(1 for s in secrets_status if s["needs_rotation"]),
            "scheduler_running": self._running,
            "policies": {
                st.value: {"interval_days": p.rotation_interval_days, "auto_rotate": p.auto_rotate}
                for st, p in self._policies.items()
            },
            "secrets": secrets_status,
        }


_rotation_manager: SecretRotationManager | None = None


def get_rotation_manager() -> SecretRotationManager:
    """Get or create the global rotation manager."""
    global _rotation_manager
    if _rotation_manager is None:
        _rotation_manager = SecretRotationManager()
    return _rotation_manager


def rotate_secret(secret_type: SecretType) -> str:
    """Rotate a secret by type."""
    manager = get_rotation_manager()
    current = manager.get_current_secret(secret_type)

    if current:
        new_secret = manager.rotate_secret(current.metadata.secret_id)
        return new_secret.value
    else:
        new_secret = manager.create_secret(secret_type)
        return new_secret.value


def get_rotation_status() -> dict[str, Any]:
    """Get rotation status."""
    return get_rotation_manager().get_rotation_status()


async def start_rotation_scheduler():
    """Start the rotation scheduler."""
    await get_rotation_manager().start_scheduler()


async def stop_rotation_scheduler():
    """Stop the rotation scheduler."""
    await get_rotation_manager().stop_scheduler()

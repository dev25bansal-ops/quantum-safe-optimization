"""In-memory secret rotation for enhanced security endpoints."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4


class SecretType(str, Enum):
    """Secret categories managed by the rotation service."""

    PQC_SIGNING_KEY = "pqc_signing_key"
    PQC_ENCRYPTION_KEY = "pqc_encryption_key"
    JWT_SECRET = "jwt_secret"
    API_KEY = "api_key"
    WEBHOOK_SECRET = "webhook_secret"
    ENCRYPTION_KEY = "encryption_key"


@dataclass(frozen=True)
class RotationPolicy:
    """Secret rotation policy."""

    max_age_days: int = 90
    rotate_before_days: int = 7


@dataclass
class SecretMetadata:
    """Metadata for a managed secret version."""

    secret_id: str
    secret_type: SecretType
    version: int
    created_at: datetime
    expires_at: datetime | None
    is_current: bool
    algorithm: str
    rotated_from: str | None = None


@dataclass
class ManagedSecret:
    """Secret value plus metadata."""

    metadata: SecretMetadata
    value: str


class SecretRotationManager:
    """Small rotation manager suitable for local/test deployments."""

    _ALGORITHMS = {
        SecretType.PQC_SIGNING_KEY: "ML-DSA-65",
        SecretType.PQC_ENCRYPTION_KEY: "ML-KEM-768",
        SecretType.JWT_SECRET: "HS256",
        SecretType.API_KEY: "opaque-token",
        SecretType.WEBHOOK_SECRET: "HMAC-SHA256",
        SecretType.ENCRYPTION_KEY: "AES-256-GCM",
    }

    def __init__(self, policy: RotationPolicy | None = None):
        self.policy = policy or RotationPolicy()
        self._secrets: dict[SecretType, list[ManagedSecret]] = {}
        self._bootstrap_defaults()

    def _bootstrap_defaults(self) -> None:
        for secret_type in (
            SecretType.PQC_SIGNING_KEY,
            SecretType.PQC_ENCRYPTION_KEY,
            SecretType.JWT_SECRET,
            SecretType.ENCRYPTION_KEY,
        ):
            self.rotate_secret(secret_type)

    def _new_secret_value(self, secret_type: SecretType) -> str:
        prefix = secret_type.value.replace("_", "-")
        return f"{prefix}_{secrets.token_urlsafe(48)}"

    def rotate_secret(self, secret_type: SecretType) -> ManagedSecret:
        """Create a new current version for a secret type."""
        versions = self._secrets.setdefault(secret_type, [])
        previous_current = next((s for s in versions if s.metadata.is_current), None)
        if previous_current:
            previous_current.metadata.is_current = False

        now = datetime.now(UTC)
        metadata = SecretMetadata(
            secret_id=f"sec_{uuid4().hex[:12]}",
            secret_type=secret_type,
            version=len(versions) + 1,
            created_at=now,
            expires_at=now + timedelta(days=self.policy.max_age_days),
            is_current=True,
            algorithm=self._ALGORITHMS.get(secret_type, "opaque-token"),
            rotated_from=previous_current.metadata.secret_id if previous_current else None,
        )
        secret = ManagedSecret(metadata=metadata, value=self._new_secret_value(secret_type))
        versions.append(secret)
        return secret

    def get_current_secret(self, secret_type: SecretType) -> ManagedSecret | None:
        """Return the current secret for a type."""
        return next(
            (secret for secret in self._secrets.get(secret_type, []) if secret.metadata.is_current),
            None,
        )

    def get_secrets_expiring_soon(self, days: int = 7) -> list[SecretMetadata]:
        """Return current secrets expiring within the requested window."""
        threshold = datetime.now(UTC) + timedelta(days=days)
        expiring: list[SecretMetadata] = []
        for versions in self._secrets.values():
            for secret in versions:
                expires_at = secret.metadata.expires_at
                if secret.metadata.is_current and expires_at and expires_at <= threshold:
                    expiring.append(secret.metadata)
        return expiring

    def get_rotation_status(self) -> dict[str, Any]:
        """Return non-sensitive rotation status for all managed secrets."""
        secrets_status = []
        for secret_type, versions in self._secrets.items():
            current = self.get_current_secret(secret_type)
            secrets_status.append(
                {
                    "type": secret_type.value,
                    "versions": len(versions),
                    "current_secret_id": current.metadata.secret_id if current else None,
                    "current_version": current.metadata.version if current else None,
                    "algorithm": current.metadata.algorithm if current else None,
                    "expires_at": current.metadata.expires_at.isoformat()
                    if current and current.metadata.expires_at
                    else None,
                }
            )
        return {
            "policy": {
                "max_age_days": self.policy.max_age_days,
                "rotate_before_days": self.policy.rotate_before_days,
            },
            "secrets": secrets_status,
            "expiring_soon": [
                metadata.secret_id
                for metadata in self.get_secrets_expiring_soon(self.policy.rotate_before_days)
            ],
        }


_rotation_manager: SecretRotationManager | None = None


def get_rotation_manager() -> SecretRotationManager:
    """Get the process-wide rotation manager."""
    global _rotation_manager
    if _rotation_manager is None:
        _rotation_manager = SecretRotationManager()
    return _rotation_manager


def rotate_secret(secret_type: SecretType) -> str:
    """Rotate a secret and return the new value."""
    return get_rotation_manager().rotate_secret(secret_type).value


def get_rotation_status() -> dict[str, Any]:
    """Return non-sensitive rotation status."""
    return get_rotation_manager().get_rotation_status()

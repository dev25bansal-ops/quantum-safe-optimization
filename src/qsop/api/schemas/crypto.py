"""Cryptographic key management schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class KeyAlgorithm(str, Enum):
    """Supported key algorithms."""

    KYBER512 = "kyber512"
    KYBER768 = "kyber768"
    KYBER1024 = "kyber1024"
    DILITHIUM2 = "dilithium2"
    DILITHIUM3 = "dilithium3"
    DILITHIUM5 = "dilithium5"
    SPHINCS_SHA256_128F = "sphincs-sha256-128f"
    RSA2048 = "rsa2048"
    RSA4096 = "rsa4096"
    ECDSA_P256 = "ecdsa-p256"


class KeyStatus(str, Enum):
    """Key lifecycle statuses."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING_ROTATION = "pending_rotation"
    REVOKED = "revoked"
    EXPIRED = "expired"


class KeyCreate(BaseModel):
    """Request body for creating a new key pair."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable key name",
    )
    algorithm: KeyAlgorithm = Field(
        default=KeyAlgorithm.KYBER768,
        description="Key algorithm to use",
    )
    key_size: int | None = Field(
        None,
        description="Key size in bits (algorithm-dependent)",
    )
    expires_in_days: int | None = Field(
        None,
        ge=1,
        le=3650,
        description="Number of days until key expires",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional key metadata",
    )
    auto_rotate: bool = Field(
        default=False,
        description="Enable automatic key rotation",
    )
    rotation_period_days: int | None = Field(
        None,
        ge=1,
        le=365,
        description="Days between automatic rotations",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "production-encryption-key",
                "algorithm": "kyber768",
                "expires_in_days": 365,
                "auto_rotate": True,
                "rotation_period_days": 90,
                "metadata": {"environment": "production", "purpose": "job-protection"},
            }
        }
    )


class CryptoSettings(BaseModel):
    """Cryptographic settings for a job."""

    kem_algorithm: KeyAlgorithm = Field(
        default=KeyAlgorithm.KYBER768,
        description="KEM algorithm for key exchange",
    )
    sig_algorithm: KeyAlgorithm = Field(
        default=KeyAlgorithm.DILITHIUM3,
        description="Signature algorithm for results",
    )
    hybrid_mode: bool = Field(
        default=True,
        description="Whether to use hybrid quantum-classical mode",
    )
    enabled: bool = Field(
        default=True,
        description="Whether encryption is enabled for this job",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "kem_algorithm": "kyber768",
                "sig_algorithm": "dilithium3",
                "hybrid_mode": True,
                "enabled": True,
            }
        }
    )


class KeyResponse(BaseModel):
    """Response model for key details."""

    id: UUID
    name: str
    algorithm: str
    key_size: int | None
    public_key: str | None = Field(
        None,
        description="PEM-encoded public key (only returned on creation)",
    )
    status: KeyStatus
    version: int = Field(default=1, description="Key version number")
    created_at: datetime
    rotated_at: datetime | None = None
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    usage_count: int = Field(default=0, description="Number of times key was used")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "770e8400-e29b-41d4-a716-446655440001",
                "name": "production-encryption-key",
                "algorithm": "kyber768",
                "key_size": 768,
                "public_key": "-----BEGIN PUBLIC KEY-----\nMIIBCgKCAQEA...",
                "status": "active",
                "version": 1,
                "created_at": "2024-01-01T00:00:00Z",
                "rotated_at": None,
                "expires_at": "2025-01-01T00:00:00Z",
                "last_used_at": "2024-01-15T10:30:00Z",
                "usage_count": 42,
            }
        },
    )


class KeyListResponse(BaseModel):
    """Paginated list of keys."""

    keys: list[KeyResponse]
    total: int
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        """Check if there are more results available."""
        return self.offset + len(self.keys) < self.total

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "keys": [
                    {
                        "id": "770e8400-e29b-41d4-a716-446655440001",
                        "name": "production-encryption-key",
                        "algorithm": "kyber768",
                        "key_size": 768,
                        "status": "active",
                        "version": 1,
                        "created_at": "2024-01-01T00:00:00Z",
                        "expires_at": "2025-01-01T00:00:00Z",
                        "usage_count": 42,
                    }
                ],
                "total": 1,
                "limit": 20,
                "offset": 0,
            }
        }
    )


class KeyRotateResponse(BaseModel):
    """Response after key rotation."""

    id: UUID
    name: str
    old_version: int
    new_version: int
    public_key: str | None = Field(
        None,
        description="PEM-encoded new public key",
    )
    rotated_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "770e8400-e29b-41d4-a716-446655440001",
                "name": "production-encryption-key",
                "old_version": 1,
                "new_version": 2,
                "public_key": "-----BEGIN PUBLIC KEY-----\nMIIBCgKCAQEA...",
                "rotated_at": "2024-04-01T00:00:00Z",
            }
        }
    )


class KeyUsageStats(BaseModel):
    """Key usage statistics."""

    key_id: UUID
    total_operations: int
    encrypt_count: int
    decrypt_count: int
    sign_count: int
    verify_count: int
    last_operation: datetime | None
    operations_by_day: dict[str, int] = Field(default_factory=dict)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "key_id": "770e8400-e29b-41d4-a716-446655440001",
                "total_operations": 150,
                "encrypt_count": 85,
                "decrypt_count": 60,
                "sign_count": 5,
                "verify_count": 0,
                "last_operation": "2024-01-15T10:30:00Z",
                "operations_by_day": {
                    "2024-01-14": 45,
                    "2024-01-15": 105,
                },
            }
        }
    )


class EncryptRequest(BaseModel):
    """Request to encrypt data with a key."""

    key_id: UUID
    plaintext: str = Field(..., description="Base64-encoded plaintext")
    associated_data: str | None = Field(None, description="Additional authenticated data")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "key_id": "770e8400-e29b-41d4-a716-446655440001",
                "plaintext": "SGVsbG8gV29ybGQh",
                "associated_data": "job-results-v1",
            }
        }
    )


class EncryptResponse(BaseModel):
    """Response with encrypted data."""

    key_id: UUID
    key_version: int
    ciphertext: str = Field(..., description="Base64-encoded ciphertext")
    iv: str | None = Field(None, description="Initialization vector if applicable")
    tag: str | None = Field(None, description="Authentication tag")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "key_id": "770e8400-e29b-41d4-a716-446655440001",
                "key_version": 1,
                "ciphertext": "ZXhhbXBsZV9lbmNyeXB0ZWRfZGF0YQ==",
                "iv": "YWJjZGVmZ2hpams=",
                "tag": "YXV0aF90YWdfc2lnbmF0dXJl",
            }
        }
    )


class DecryptRequest(BaseModel):
    """Request to decrypt data."""

    key_id: UUID
    key_version: int | None = Field(None, description="Specific version to use")
    ciphertext: str = Field(..., description="Base64-encoded ciphertext")
    iv: str | None = None
    tag: str | None = None
    associated_data: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "key_id": "770e8400-e29b-41d4-a716-446655440001",
                "key_version": 1,
                "ciphertext": "ZXhhbXBsZV9lbmNyeXB0ZWRfZGF0YQ==",
                "iv": "YWJjZGVmZ2hpams=",
                "tag": "YXV0aF90YWdfc2lnbmF0dXJl",
                "associated_data": "job-results-v1",
            }
        }
    )


class DecryptResponse(BaseModel):
    """Response with decrypted data."""

    key_id: UUID
    plaintext: str = Field(..., description="Base64-encoded plaintext")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "key_id": "770e8400-e29b-41d4-a716-446655440001",
                "plaintext": "SGVsbG8gV29ybGQh",
            }
        }
    )

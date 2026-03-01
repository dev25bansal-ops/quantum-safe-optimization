"""
Pydantic models for authentication.
"""

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """User registration request."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    organization: str | None = None


class UserLogin(BaseModel):
    """User login request."""

    username: str
    password: str


class TokenResponse(BaseModel):
    """Token response with PQC signature."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 - Standard JWT token type
    expires_in: int
    signature: str = Field(..., description="ML-DSA signature of the token")
    algorithm: str = Field(default="ML-DSA-65")


class UserResponse(BaseModel):
    """User profile response."""

    user_id: str
    username: str
    email: str
    organization: str | None = None
    created_at: str
    roles: list[str] = Field(default_factory=list)
    has_kem_key: bool = Field(default=False, description="User has registered ML-KEM public key")
    has_signing_key: bool = Field(
        default=False, description="User has registered ML-DSA public key"
    )


class KeyRegistration(BaseModel):
    """Request to register PQC public keys."""

    kem_public_key: str | None = Field(None, description="ML-KEM-768 public key (base64)")
    signing_public_key: str | None = Field(None, description="ML-DSA-65 public key (base64)")
    key_fingerprint: str | None = Field(None, description="SHA-256 fingerprint of the key")


class KeyResponse(BaseModel):
    """Response containing registered keys."""

    kem_public_key: str | None = None
    signing_public_key: str | None = None
    key_fingerprint: str | None = None
    registered_at: str


class PasswordChange(BaseModel):
    """Password change request."""

    current_password: str
    new_password: str = Field(..., min_length=8)


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""

    refresh_token: str

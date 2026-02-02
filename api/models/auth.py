"""
Pydantic models for authentication.
"""

from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr


class UserCreate(BaseModel):
    """User registration request."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    organization: Optional[str] = None


class UserLogin(BaseModel):
    """User login request."""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Token response with PQC signature."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    signature: str = Field(..., description="ML-DSA signature of the token")
    algorithm: str = Field(default="ML-DSA-65")


class UserResponse(BaseModel):
    """User profile response."""
    user_id: str
    username: str
    email: str
    organization: Optional[str] = None
    created_at: str
    roles: List[str] = Field(default_factory=list)
    has_kem_key: bool = Field(default=False, description="User has registered ML-KEM public key")
    has_signing_key: bool = Field(default=False, description="User has registered ML-DSA public key")


class KeyRegistration(BaseModel):
    """Request to register PQC public keys."""
    kem_public_key: Optional[str] = Field(None, description="ML-KEM-768 public key (base64)")
    signing_public_key: Optional[str] = Field(None, description="ML-DSA-65 public key (base64)")
    key_fingerprint: Optional[str] = Field(None, description="SHA-256 fingerprint of the key")


class KeyResponse(BaseModel):
    """Response containing registered keys."""
    kem_public_key: Optional[str] = None
    signing_public_key: Optional[str] = None
    key_fingerprint: Optional[str] = None
    registered_at: str


class PasswordChange(BaseModel):
    """Password change request."""
    current_password: str
    new_password: str = Field(..., min_length=8)


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str

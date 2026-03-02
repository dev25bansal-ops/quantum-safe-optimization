"""
Credential Management API Endpoints

Provides secure REST API endpoints for storing, retrieving, and managing
third-party quantum computing service credentials.

Security:
- All endpoints require authentication (ML-DSA signed JWT)
- Credentials are encrypted at rest (ML-KEM-768)
- Credential values only returned to the user who owns them
- Audit logging for all credential operations

Usage:
1. POST /credentials - Store a credential
2. GET /credentials - List all credentials (metadata only)
3. GET /credentials/{provider}/{type} - Retrieve a specific credential
4. DELETE /credentials/{provider}/{type} - Delete a credential
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from api.services.credentials import get_credential_manager
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)
router = APIRouter()


# Data Models
class CredentialStoreRequest(BaseModel):
    """Request to store a new credential."""

    provider: str = Field(
        ...,
        description="Service provider (ibm, dwave, aws)",
        pattern=r"^(ibm|dwave|aws)$",
    )
    credential_type: str = Field(
        ...,
        description="Credential type (api_token, access_key, secret_key)",
        min_length=1,
    )
    value: str = Field(
        ...,
        description="The credential value (will be encrypted)",
        min_length=1,
        max_length=2048,
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Optional metadata (region, account, etc.)",
    )


class CredentialResponse(BaseModel):
    """Response for credential queries (without value)."""

    id: str
    user_id: str
    provider: str
    credential_type: str
    metadata: dict[str, str]
    created_at: str
    updated_at: str


class CredentialDetailResponse(CredentialResponse):
    """Response including the decrypted credential value."""

    value: str


# Rate limiting dependency
from api.security.rate_limiter import limiter


async def get_current_user_for_credentials(request):
    """Get current user without circular import."""
    from api.routers.auth import get_current_user

    return await get_current_user(request)


@router.post("", response_model=CredentialResponse, status_code=201)
@limiter.limit("5/minute")
async def store_credential(
    request: Request,
    body: CredentialStoreRequest,
    current_user: dict = Depends(get_current_user_for_credentials),
):
    """
    Store a new credential in secure storage.

    The credential value is encrypted using ML-KEM-768 before storage
    and can only be retrieved by the user who stored it.

    Providers:
    - `ibm`: IBM Quantum (api_token)
    - `dwave`: D-Wave Leap (api_token)
    - `aws`: AWS Braket (access_key, secret_key)
    """
    manager = await get_credential_manager()

    try:
        response = await manager.store_credential(
            user_id=current_user["sub"],
            provider=body.provider,
            credential_type=body.credential_type,
            value=body.value,
            metadata=body.metadata,
        )

        logger.info(
            f"Credential stored: {body.provider}/{body.credential_type} "
            f"for user {current_user['sub']}"
        )

        return response
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Credential storage service unavailable",
        )
    except Exception as e:
        logger.error(f"Failed to store credential: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store credential",
        )


@router.get("", response_model=list[CredentialResponse])
@limiter.limit("10/minute")
async def list_credentials(
    request: Request,
    current_user: dict = Depends(get_current_user_for_credentials),
):
    """
    List all credentials for the current user.

    Only returns metadata (no credential values) for security.
    """
    manager = await get_credential_manager()

    try:
        credentials = await manager.list_credentials(current_user["sub"])
        return credentials
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Credential storage service unavailable",
        )


@router.get("/{provider}/{credential_type}", response_model=CredentialDetailResponse)
@limiter.limit("20/minute")
async def get_credential(
    request: Request,
    provider: str,
    credential_type: str,
    current_user: dict = Depends(get_current_user_for_credentials),
):
    """
    Retrieve a specific credential including the decrypted value.

    Only the user who stored the credential can retrieve it.
    """
    manager = await get_credential_manager()

    credential = await manager.get_credential(
        user_id=current_user["sub"],
        provider=provider,
        credential_type=credential_type,
    )

    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credential not found: {provider}/{credential_type}",
        )

    return credential


@router.delete("/{provider}/{credential_type}")
@limiter.limit("5/minute")
async def delete_credential(
    request: Request,
    provider: str,
    credential_type: str,
    current_user: dict = Depends(get_current_user_for_credentials),
):
    """
    Delete a stored credential.

    Only the user who stored the credential can delete it.
    """
    manager = await get_credential_manager()

    result = await manager.delete_credential(
        user_id=current_user["sub"],
        provider=provider,
        credential_type=credential_type,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credential not found: {provider}/{credential_type}",
        )

    logger.info(f"Credential deleted: {provider}/{credential_type} for user {current_user['sub']}")

    return {"message": "Credential deleted successfully"}

"""Cryptographic key management endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from qsop.api.deps import CurrentTenant, ServiceContainerDep
from qsop.api.schemas.crypto import (
    KeyCreate,
    KeyListResponse,
    KeyResponse,
    KeyRotateResponse,
)

router = APIRouter()


@router.post("", response_model=KeyResponse, status_code=status.HTTP_201_CREATED)
async def create_key(
    key_data: KeyCreate,
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
) -> KeyResponse:
    """
    Create a new cryptographic key pair.

    Generates a quantum-safe key pair and stores it securely.
    """
    try:
        # Generate key material via keystore
        key_material = await container.keystore.generate_keypair(
            algorithm=key_data.algorithm,
            key_size=key_data.key_size,
        )

        # Store key metadata in repository
        key = await container.key_repo.create(
            tenant_id=tenant_id,
            name=key_data.name,
            algorithm=key_data.algorithm,
            key_size=key_data.key_size,
            public_key_id=key_material["public_key_id"],
            private_key_id=key_material["private_key_id"],
            metadata=key_data.metadata,
        )

        return KeyResponse(
            id=key.id,
            name=key.name,
            algorithm=key.algorithm,
            key_size=key.key_size,
            public_key=key_material.get("public_key_pem"),
            status=key.status,
            created_at=key.created_at,
            rotated_at=key.rotated_at,
            expires_at=key.expires_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("", response_model=KeyListResponse)
async def list_keys(
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> KeyListResponse:
    """
    List cryptographic keys for the current tenant.
    """
    keys, total = await container.key_repo.list_by_tenant(
        tenant_id=tenant_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )

    return KeyListResponse(
        keys=[KeyResponse.model_validate(k) for k in keys],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{key_id}", response_model=KeyResponse)
async def get_key(
    key_id: UUID,
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
) -> KeyResponse:
    """
    Get details of a specific key.
    """
    key = await container.key_repo.get_by_id(key_id, tenant_id)

    if key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key {key_id} not found",
        )

    return KeyResponse.model_validate(key)


@router.post("/{key_id}/rotate", response_model=KeyRotateResponse)
async def rotate_key(
    key_id: UUID,
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
) -> KeyRotateResponse:
    """
    Rotate a cryptographic key.

    Creates a new version of the key while maintaining the ability
    to decrypt data encrypted with the previous version.
    """
    key = await container.key_repo.get_by_id(key_id, tenant_id)

    if key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key {key_id} not found",
        )

    if key.status == "revoked":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot rotate a revoked key",
        )

    # Generate new key material
    new_key_material = await container.keystore.generate_keypair(
        algorithm=key.algorithm,
        key_size=key.key_size,
    )

    # Update key with new version
    old_version = key.version
    updated_key = await container.key_repo.rotate(
        key_id=key_id,
        new_public_key_id=new_key_material["public_key_id"],
        new_private_key_id=new_key_material["private_key_id"],
    )

    return KeyRotateResponse(
        id=updated_key.id,
        name=updated_key.name,
        old_version=old_version,
        new_version=updated_key.version,
        public_key=new_key_material.get("public_key_pem"),
        rotated_at=updated_key.rotated_at,
    )


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_key(
    key_id: UUID,
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
) -> None:
    """
    Revoke a cryptographic key.

    The key will be marked as revoked and can no longer be used
    for new encryption operations. Existing encrypted data can
    still be decrypted during the grace period.
    """
    key = await container.key_repo.get_by_id(key_id, tenant_id)

    if key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key {key_id} not found",
        )

    if key.status == "revoked":
        return  # Already revoked, idempotent

    await container.key_repo.revoke(key_id)

    # Schedule key material deletion after grace period
    await container.event_bus.publish(
        "key.revoked",
        {
            "key_id": str(key_id),
            "tenant_id": tenant_id,
            "grace_period_days": 30,
        },
    )

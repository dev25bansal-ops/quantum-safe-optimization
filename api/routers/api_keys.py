"""
API Key Management for Service-to-Service Authentication.

Provides secure API key generation, validation, and management.
Keys are hashed using Argon2id and can have scoped permissions.
"""

import logging
import os
import secrets
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from argon2 import PasswordHasher
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api-keys", tags=["API Keys"])

_password_hasher = PasswordHasher()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class APIKeyScope(str, Enum):
    """API key permission scopes."""

    JOBS_READ = "jobs:read"
    JOBS_WRITE = "jobs:write"
    JOBS_SUBMIT = "jobs:submit"
    RESULTS_READ = "results:read"
    RESULTS_WRITE = "results:write"
    METRICS_READ = "metrics:read"
    ADMIN = "admin"
    ALL = "*"


class APIKeyCreate(BaseModel):
    """Request to create a new API key."""

    name: str = Field(..., min_length=1, max_length=100)
    scopes: list[APIKeyScope] = Field(default=[APIKeyScope.ALL])
    expires_in_days: int | None = Field(None, ge=1, le=365)
    metadata: dict[str, Any] | None = None
    rate_limit: int | None = Field(None, ge=10, le=10000, description="Requests per minute")


class APIKeyResponse(BaseModel):
    """API key creation response."""

    key_id: str
    name: str
    api_key: str  # Only shown once!
    scopes: list[str]
    expires_at: datetime | None
    created_at: datetime


class APIKeyInfo(BaseModel):
    """API key information (without the actual key)."""

    key_id: str
    name: str
    scopes: list[str]
    expires_at: datetime | None
    created_at: datetime
    last_used_at: datetime | None
    usage_count: int
    is_active: bool
    rate_limit: int | None


class APIKeyList(BaseModel):
    """List of API keys."""

    keys: list[APIKeyInfo]
    total: int


_in_memory_keys: dict[str, dict] = {}


async def get_key_store():
    """Get API key store."""
    try:
        from api.db.repository import get_key_store as _get_key_store

        return await _get_key_store()
    except ImportError:
        return None


async def save_api_key(key_data: dict) -> dict:
    """Save API key to store."""
    key_id = key_data.get("key_id")
    _in_memory_keys[key_id] = key_data

    store = await get_key_store()
    if store:
        try:
            await store.upsert(key_data)
        except Exception as e:
            logger.warning(f"Failed to save API key to store: {e}")

    return key_data


async def get_api_key_by_id(key_id: str) -> dict | None:
    """Get API key by ID."""
    if key_id in _in_memory_keys:
        return _in_memory_keys[key_id]

    store = await get_key_store()
    if store:
        try:
            return await store.get(key_id)
        except Exception:
            pass
    return None


async def get_api_key_by_prefix(key_prefix: str) -> dict | None:
    """Get API key by prefix (for lookup)."""
    for key in _in_memory_keys.values():
        if key.get("key_prefix") == key_prefix:
            return key

    store = await get_key_store()
    if store:
        try:
            keys = await store.list(limit=1000)
            for key in keys:
                if key.get("key_prefix") == key_prefix:
                    return key
        except Exception:
            pass
    return None


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns (full_key, key_prefix, key_secret).
    """
    prefix = f"qsop_{secrets.token_hex(4)}"
    secret = secrets.token_urlsafe(32)
    full_key = f"{prefix}_{secret}"
    return full_key, prefix, secret


def hash_api_key(key: str) -> str:
    """Hash an API key using Argon2id."""
    return _password_hasher.hash(key)


def verify_api_key(key: str, hashed_key: str) -> bool:
    """Verify an API key against its hash."""
    try:
        _password_hasher.verify(hashed_key, key)
        return True
    except Exception:
        return False


async def validate_api_key(api_key: str) -> dict | None:
    """Validate an API key and return its data."""
    if not api_key or not api_key.startswith("qsop_"):
        return None

    parts = api_key.split("_")
    if len(parts) < 3:
        return None

    key_prefix = f"{parts[0]}_{parts[1]}"

    key_data = await get_api_key_by_prefix(key_prefix)
    if not key_data:
        return None

    if key_data.get("is_active") is False:
        return None

    if key_data.get("expires_at"):
        expires_at = datetime.fromisoformat(key_data["expires_at"])
        if datetime.now(UTC) > expires_at:
            return None

    if not verify_api_key(api_key, key_data.get("key_hash", "")):
        return None

    key_data["last_used_at"] = datetime.now(UTC).isoformat()
    key_data["usage_count"] = key_data.get("usage_count", 0) + 1
    await save_api_key(key_data)

    return key_data


async def get_current_service(request: Request, api_key: str = Depends(api_key_header)) -> dict:
    """Dependency to get current authenticated service via API key."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    key_data = await validate_api_key(api_key)
    if not key_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    request.state.service_name = key_data.get("name")
    request.state.service_scopes = key_data.get("scopes", [])

    return key_data


def require_scope(*required_scopes: APIKeyScope):
    """Dependency to require specific scopes."""

    async def check_scopes(service: dict = Depends(get_current_service)) -> dict:
        service_scopes = service.get("scopes", [])

        if APIKeyScope.ALL in service_scopes or APIKeyScope.ADMIN in service_scopes:
            return service

        for scope in required_scopes:
            if scope.value not in service_scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required scope: {scope.value}",
                )

        return service

    return check_scopes


@router.post("/", response_model=APIKeyResponse, status_code=201)
async def create_api_key(request: Request, key_create: APIKeyCreate):
    """Create a new API key for service-to-service authentication."""
    from api.routers.auth import get_current_user

    try:
        current_user = await get_current_user(request, None)
        if "admin" not in current_user.get("roles", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin role required to create API keys",
            )
    except HTTPException:
        admin_secret = os.environ.get("API_KEY_ADMIN_SECRET")
        admin_header = request.headers.get("X-Admin-Secret")
        if not admin_secret or admin_header != admin_secret:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin authorization required",
            )
        current_user = {"sub": "system", "roles": ["admin"]}

    full_key, key_prefix, key_secret = generate_api_key()
    key_hash = hash_api_key(full_key)
    key_id = f"apikey_{secrets.token_hex(8)}"

    now = datetime.now(UTC)
    expires_at = None
    if key_create.expires_in_days:
        expires_at = now + timedelta(days=key_create.expires_in_days)

    key_data = {
        "key_id": key_id,
        "id": key_id,
        "name": key_create.name,
        "key_prefix": key_prefix,
        "key_hash": key_hash,
        "key_secret_hash": _password_hasher.hash(key_secret),
        "scopes": [s.value for s in key_create.scopes],
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat() if expires_at else None,
        "created_by": current_user.get("sub"),
        "is_active": True,
        "usage_count": 0,
        "last_used_at": None,
        "rate_limit": key_create.rate_limit,
        "metadata": key_create.metadata or {},
    }

    await save_api_key(key_data)

    logger.info(f"API key created: {key_id} for service: {key_create.name}")

    return APIKeyResponse(
        key_id=key_id,
        name=key_create.name,
        api_key=full_key,
        scopes=[s.value for s in key_create.scopes],
        expires_at=expires_at,
        created_at=now,
    )


@router.get("/", response_model=APIKeyList)
async def list_api_keys(
    skip: int = 0,
    limit: int = 50,
    service: dict = Depends(require_scope(APIKeyScope.ADMIN)),
):
    """List all API keys (admin only)."""
    keys = []
    for key_data in _in_memory_keys.values():
        keys.append(
            APIKeyInfo(
                key_id=key_data["key_id"],
                name=key_data["name"],
                scopes=key_data.get("scopes", []),
                expires_at=datetime.fromisoformat(key_data["expires_at"])
                if key_data.get("expires_at")
                else None,
                created_at=datetime.fromisoformat(key_data["created_at"]),
                last_used_at=datetime.fromisoformat(key_data["last_used_at"])
                if key_data.get("last_used_at")
                else None,
                usage_count=key_data.get("usage_count", 0),
                is_active=key_data.get("is_active", True),
                rate_limit=key_data.get("rate_limit"),
            )
        )

    return APIKeyList(keys=keys[skip : skip + limit], total=len(keys))


@router.get("/{key_id}", response_model=APIKeyInfo)
async def get_api_key_info(
    key_id: str,
    service: dict = Depends(require_scope(APIKeyScope.ADMIN)),
):
    """Get API key information."""
    key_data = await get_api_key_by_id(key_id)
    if not key_data:
        raise HTTPException(status_code=404, detail="API key not found")

    return APIKeyInfo(
        key_id=key_data["key_id"],
        name=key_data["name"],
        scopes=key_data.get("scopes", []),
        expires_at=datetime.fromisoformat(key_data["expires_at"])
        if key_data.get("expires_at")
        else None,
        created_at=datetime.fromisoformat(key_data["created_at"]),
        last_used_at=datetime.fromisoformat(key_data["last_used_at"])
        if key_data.get("last_used_at")
        else None,
        usage_count=key_data.get("usage_count", 0),
        is_active=key_data.get("is_active", True),
        rate_limit=key_data.get("rate_limit"),
    )


@router.post("/{key_id}/revoke")
async def revoke_api_key(
    key_id: str,
    service: dict = Depends(require_scope(APIKeyScope.ADMIN)),
):
    """Revoke an API key."""
    key_data = await get_api_key_by_id(key_id)
    if not key_data:
        raise HTTPException(status_code=404, detail="API key not found")

    key_data["is_active"] = False
    key_data["revoked_at"] = datetime.now(UTC).isoformat()
    await save_api_key(key_data)

    logger.info(f"API key revoked: {key_id}")

    return {"message": "API key revoked", "key_id": key_id}


@router.delete("/{key_id}")
async def delete_api_key(
    key_id: str,
    service: dict = Depends(require_scope(APIKeyScope.ADMIN)),
):
    """Delete an API key."""
    key_data = await get_api_key_by_id(key_id)
    if not key_data:
        raise HTTPException(status_code=404, detail="API key not found")

    if key_id in _in_memory_keys:
        del _in_memory_keys[key_id]

    logger.info(f"API key deleted: {key_id}")

    return {"message": "API key deleted", "key_id": key_id}


@router.post("/{key_id}/rotate", response_model=APIKeyResponse)
async def rotate_api_key(
    key_id: str,
    service: dict = Depends(require_scope(APIKeyScope.ADMIN)),
):
    """Rotate an API key (generate new key, keep same ID and scopes)."""
    key_data = await get_api_key_by_id(key_id)
    if not key_data:
        raise HTTPException(status_code=404, detail="API key not found")

    full_key, key_prefix, key_secret = generate_api_key()
    key_hash = hash_api_key(full_key)

    key_data["key_prefix"] = key_prefix
    key_data["key_hash"] = key_hash
    key_data["key_secret_hash"] = _password_hasher.hash(key_secret)
    key_data["rotated_at"] = datetime.now(UTC).isoformat()
    key_data["usage_count"] = 0
    key_data["is_active"] = True

    await save_api_key(key_data)

    logger.info(f"API key rotated: {key_id}")

    return APIKeyResponse(
        key_id=key_id,
        name=key_data["name"],
        api_key=full_key,
        scopes=key_data.get("scopes", []),
        expires_at=datetime.fromisoformat(key_data["expires_at"])
        if key_data.get("expires_at")
        else None,
        created_at=datetime.fromisoformat(key_data["created_at"]),
    )


@router.get("/validate/test")
async def test_api_key_validation(service: dict = Depends(get_current_service)):
    """Test API key validation."""
    return {
        "valid": True,
        "service_name": service.get("name"),
        "scopes": service.get("scopes", []),
        "key_id": service.get("key_id"),
    }


@router.get("/{key_id}/rotation-status")
async def get_rotation_status(
    key_id: str,
    service: dict = Depends(require_scope(APIKeyScope.JOBS_READ)),
):
    """Get rotation status for an API key."""
    from api.security.api_key_rotation import rotation_service

    return await rotation_service.get_rotation_status(key_id)


@router.post("/{key_id}/schedule-rotation")
async def schedule_key_rotation(
    key_id: str,
    days: int = 7,
    service: dict = Depends(require_scope(APIKeyScope.ADMIN)),
):
    """Schedule an API key rotation for a future date."""
    from api.security.api_key_rotation import rotation_service
    from datetime import timedelta

    scheduled_at = datetime.now(UTC) + timedelta(days=days)
    result = await rotation_service.schedule_rotation(
        key_id=key_id,
        scheduled_at=scheduled_at,
        reason=f"Scheduled by {service.get('name', 'admin')}",
    )

    return {
        "key_id": key_id,
        "scheduled": True,
        "scheduled_at": scheduled_at.isoformat(),
        "message": result,
    }


@router.get("/rotation/due")
async def get_keys_due_for_rotation(
    service: dict = Depends(require_scope(APIKeyScope.ADMIN)),
):
    """Get API keys that are due for rotation."""
    from api.security.api_key_rotation import rotation_service

    all_keys = list(_in_memory_keys.values())
    due_keys = await rotation_service.get_keys_due_for_rotation(all_keys)

    return {"keys_due": due_keys, "count": len(due_keys)}


@router.get("/rotation/settings")
async def get_rotation_settings(
    service: dict = Depends(require_scope(APIKeyScope.ADMIN)),
):
    """Get current rotation policy settings."""
    from api.security.api_key_rotation import rotation_service, RotationPolicy

    return {
        "policy": rotation_service.config.policy.value,
        "grace_period_hours": rotation_service.config.grace_period_hours,
        "notify_before_days": rotation_service.config.notify_before_days,
        "auto_rotate_enabled": rotation_service.config.auto_rotate_enabled,
        "max_key_age_days": rotation_service.config.max_key_age_days,
        "available_policies": [p.value for p in RotationPolicy],
    }


@router.put("/rotation/settings")
async def update_rotation_settings(
    policy: str = "90_days",
    grace_period_hours: int = 24,
    notify_before_days: int = 7,
    auto_rotate_enabled: bool = True,
    service: dict = Depends(require_scope(APIKeyScope.ADMIN)),
):
    """Update rotation policy settings."""
    from api.security.api_key_rotation import rotation_service, RotationConfig, RotationPolicy

    try:
        new_config = RotationConfig(
            policy=RotationPolicy(policy),
            grace_period_hours=grace_period_hours,
            notify_before_days=notify_before_days,
            auto_rotate_enabled=auto_rotate_enabled,
        )
        rotation_service.config = new_config

        logger.info(
            "rotation_settings_updated",
            policy=policy,
            grace_period_hours=grace_period_hours,
            updated_by=service.get("name", "admin"),
        )

        return {
            "updated": True,
            "config": {
                "policy": new_config.policy.value,
                "grace_period_hours": new_config.grace_period_hours,
                "notify_before_days": new_config.notify_before_days,
                "auto_rotate_enabled": new_config.auto_rotate_enabled,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid policy: {policy}")

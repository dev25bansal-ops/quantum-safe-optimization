"""
Multi-Tenant API Endpoints.

Provides tenant management, RBAC, and quota enforcement.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from .models import (
    Permission,
    Role,
    ROLE_PERMISSIONS,
    Tenant,
    TenantCreate,
    TenantMemberCreate,
    TenantMemberResponse,
    TenantMembership,
    TenantQuotaCheck,
    TenantResponse,
    TenantSettingsUpdate,
    TenantTier,
    TenantUsage,
    RoleUpdate,
    get_tier_quotas,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_in_memory_tenants: dict[str, Tenant] = {}
_in_memory_memberships: dict[str, list[TenantMembership]] = {}
_tenant_usage: dict[str, dict[str, int]] = {}


def get_current_tenant() -> Tenant:
    """Get current tenant (stub for auth integration)."""
    return list(_in_memory_tenants.values())[0] if _in_memory_tenants else None


async def check_permission_stub(user_id: str = "user_default") -> bool:
    """Stub permission checker - always returns True."""
    return True


def require_permission(permission: Permission):
    """Dependency factory to check user permission."""

    async def checker(user_id: str = "user_default") -> bool:
        return True

    return checker


@router.post("/tenants", response_model=TenantResponse)
async def create_tenant(
    request: TenantCreate,
    user_id: str = "user_default",
):
    """Create a new tenant."""
    tenant = Tenant.create(name=request.name, tier=request.tier)
    _in_memory_tenants[tenant.tenant_id] = tenant

    membership = TenantMembership(
        tenant_id=tenant.tenant_id,
        user_id=user_id,
        role=Role.ADMIN,
        invited_by=None,
    )
    _in_memory_memberships.setdefault(tenant.tenant_id, []).append(membership)

    _tenant_usage[tenant.tenant_id] = {
        "jobs_count": 0,
        "shots_used": 0,
        "compute_seconds": 0.0,
        "api_calls": 0,
        "storage_used_mb": 0.0,
    }

    logger.info(f"Created tenant: {tenant.tenant_id} - {tenant.name}")

    return TenantResponse(
        tenant_id=tenant.tenant_id,
        name=tenant.name,
        slug=tenant.slug,
        tier=tenant.tier,
        is_active=tenant.is_active,
        created_at=tenant.created_at.isoformat(),
        quotas=tenant.quotas,
        usage=_tenant_usage.get(tenant.tenant_id, {}),
    )


@router.get("/tenants", response_model=list[TenantResponse])
async def list_tenants(
    user_id: str = "user_default",
    limit: int = Query(default=20, le=100),
):
    """List tenants for current user."""
    user_tenant_ids = set()
    for tenant_id, memberships in _in_memory_memberships.items():
        for m in memberships:
            if m.user_id == user_id:
                user_tenant_ids.add(tenant_id)

    tenants = []
    for tenant_id in user_tenant_ids:
        if tenant_id in _in_memory_tenants:
            tenant = _in_memory_tenants[tenant_id]
            tenants.append(
                TenantResponse(
                    tenant_id=tenant.tenant_id,
                    name=tenant.name,
                    slug=tenant.slug,
                    tier=tenant.tier,
                    is_active=tenant.is_active,
                    created_at=tenant.created_at.isoformat(),
                    quotas=tenant.quotas,
                    usage=_tenant_usage.get(tenant_id, {}),
                )
            )

    return tenants[:limit]


@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(tenant_id: str):
    """Get tenant details."""
    if tenant_id not in _in_memory_tenants:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant = _in_memory_tenants[tenant_id]
    return TenantResponse(
        tenant_id=tenant.tenant_id,
        name=tenant.name,
        slug=tenant.slug,
        tier=tenant.tier,
        is_active=tenant.is_active,
        created_at=tenant.created_at.isoformat(),
        quotas=tenant.quotas,
        usage=_tenant_usage.get(tenant_id, {}),
    )


@router.patch("/tenants/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    request: TenantSettingsUpdate,
    _perm: bool = Depends(require_permission(Permission.ADMIN_TENANT)),
):
    """Update tenant settings."""
    if tenant_id not in _in_memory_tenants:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant = _in_memory_tenants[tenant_id]

    if request.name:
        tenant.name = request.name
        tenant.slug = request.name.lower().replace(" ", "-")[:50]

    if request.settings:
        tenant.settings.update(request.settings)

    return TenantResponse(
        tenant_id=tenant.tenant_id,
        name=tenant.name,
        slug=tenant.slug,
        tier=tenant.tier,
        is_active=tenant.is_active,
        created_at=tenant.created_at.isoformat(),
        quotas=tenant.quotas,
        usage=_tenant_usage.get(tenant_id, {}),
    )


@router.post("/tenants/{tenant_id}/members", response_model=TenantMemberResponse)
async def add_tenant_member(
    tenant_id: str,
    request: TenantMemberCreate,
    invited_by: str = "user_default",
    _perm: bool = Depends(require_permission(Permission.ADMIN_USERS)),
):
    """Add a member to tenant."""
    if tenant_id not in _in_memory_tenants:
        raise HTTPException(status_code=404, detail="Tenant not found")

    user_id = f"user_{request.user_email.split('@')[0]}"

    membership = TenantMembership(
        tenant_id=tenant_id,
        user_id=user_id,
        role=request.role,
        custom_permissions=set(request.custom_permissions),
        invited_by=invited_by,
    )

    _in_memory_memberships.setdefault(tenant_id, []).append(membership)

    return TenantMemberResponse(
        user_id=user_id,
        email=request.user_email,
        username=request.user_email.split("@")[0],
        role=membership.role,
        custom_permissions=[p.value for p in membership.custom_permissions],
        joined_at=membership.joined_at.isoformat(),
    )


@router.get("/tenants/{tenant_id}/members", response_model=list[TenantMemberResponse])
async def list_tenant_members(tenant_id: str):
    """List tenant members."""
    if tenant_id not in _in_memory_tenants:
        raise HTTPException(status_code=404, detail="Tenant not found")

    memberships = _in_memory_memberships.get(tenant_id, [])

    return [
        TenantMemberResponse(
            user_id=m.user_id,
            email=f"{m.user_id}@example.com",
            username=m.user_id.replace("user_", ""),
            role=m.role,
            custom_permissions=[p.value for p in m.custom_permissions],
            joined_at=m.joined_at.isoformat(),
        )
        for m in memberships
    ]


@router.patch("/tenants/{tenant_id}/members/{user_id}", response_model=TenantMemberResponse)
async def update_member_role(
    tenant_id: str,
    user_id: str,
    request: RoleUpdate,
    _perm: bool = Depends(require_permission(Permission.ADMIN_USERS)),
):
    """Update member role."""
    if tenant_id not in _in_memory_tenants:
        raise HTTPException(status_code=404, detail="Tenant not found")

    for membership in _in_memory_memberships.get(tenant_id, []):
        if membership.user_id == user_id:
            membership.role = request.role
            if request.custom_permissions is not None:
                membership.custom_permissions = set(request.custom_permissions)

            return TenantMemberResponse(
                user_id=membership.user_id,
                email=f"{membership.user_id}@example.com",
                username=membership.user_id.replace("user_", ""),
                role=membership.role,
                custom_permissions=[p.value for p in membership.custom_permissions],
                joined_at=membership.joined_at.isoformat(),
            )

    raise HTTPException(status_code=404, detail="Member not found")


@router.delete("/tenants/{tenant_id}/members/{user_id}")
async def remove_tenant_member(
    tenant_id: str,
    user_id: str,
    _perm: bool = Depends(require_permission(Permission.ADMIN_USERS)),
):
    """Remove member from tenant."""
    if tenant_id not in _in_memory_tenants:
        raise HTTPException(status_code=404, detail="Tenant not found")

    memberships = _in_memory_memberships.get(tenant_id, [])
    _in_memory_memberships[tenant_id] = [m for m in memberships if m.user_id != user_id]

    return {"status": "removed", "user_id": user_id}


@router.get("/tenants/{tenant_id}/quota", response_model=list[TenantQuotaCheck])
async def check_quotas(tenant_id: str):
    """Check quota usage for tenant."""
    if tenant_id not in _in_memory_tenants:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant = _in_memory_tenants[tenant_id]
    usage = _tenant_usage.get(tenant_id, {})

    checks = []
    for resource, limit in tenant.quotas.items():
        used = usage.get(resource, 0)
        remaining = max(0, limit - used) if limit > 0 else -1
        checks.append(
            TenantQuotaCheck(
                resource=resource,
                used=used,
                limit=limit,
                remaining=remaining,
                exceeded=(limit > 0 and used > limit),
            )
        )

    return checks


@router.get("/tenants/{tenant_id}/usage", response_model=TenantUsage)
async def get_tenant_usage(
    tenant_id: str,
    period: str = Query(default="month", pattern="^(day|week|month)$"),
):
    """Get tenant usage statistics."""
    if tenant_id not in _in_memory_tenants:
        raise HTTPException(status_code=404, detail="Tenant not found")

    usage = _tenant_usage.get(tenant_id, {})

    return TenantUsage(
        tenant_id=tenant_id,
        period=period,
        jobs_count=usage.get("jobs_count", 0),
        shots_used=usage.get("shots_used", 0),
        compute_seconds=usage.get("compute_seconds", 0.0),
        api_calls=usage.get("api_calls", 0),
        storage_used_mb=usage.get("storage_used_mb", 0.0),
    )


@router.get("/roles", response_model=dict[str, Any])
async def list_roles():
    """List available roles and their permissions."""
    return {
        "roles": [
            {
                "name": role.value,
                "permissions": [p.value for p in perms],
            }
            for role, perms in ROLE_PERMISSIONS.items()
        ],
        "all_permissions": [p.value for p in Permission],
    }

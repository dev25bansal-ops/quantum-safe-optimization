"""
Multi-tenant Isolation Module.

Provides tenant isolation, RBAC, and data segregation for enterprise deployments.
"""

import os
import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, EmailStr


class TenantTier(str, Enum):
    """Tenant subscription tiers."""

    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class Permission(str, Enum):
    """Permissions for RBAC."""

    # Job permissions
    JOB_CREATE = "job:create"
    JOB_READ = "job:read"
    JOB_UPDATE = "job:update"
    JOB_DELETE = "job:delete"
    JOB_CANCEL = "job:cancel"

    # Key permissions
    KEY_CREATE = "key:create"
    KEY_READ = "key:read"
    KEY_DELETE = "key:delete"

    # Billing permissions
    BILLING_READ = "billing:read"
    BILLING_MANAGE = "billing:manage"

    # Admin permissions
    ADMIN_USERS = "admin:users"
    ADMIN_TENANT = "admin:tenant"
    ADMIN_BILLING = "admin:billing"

    # Marketplace permissions
    ALGORITHM_PUBLISH = "algorithm:publish"
    ALGORITHM_PURCHASE = "algorithm:purchase"


class Role(str, Enum):
    """Pre-defined roles."""

    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"
    BILLING_ADMIN = "billing_admin"


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: {
        Permission.JOB_CREATE,
        Permission.JOB_READ,
        Permission.JOB_UPDATE,
        Permission.JOB_DELETE,
        Permission.JOB_CANCEL,
        Permission.KEY_CREATE,
        Permission.KEY_READ,
        Permission.KEY_DELETE,
        Permission.BILLING_READ,
        Permission.BILLING_MANAGE,
        Permission.ADMIN_USERS,
        Permission.ADMIN_TENANT,
        Permission.ALGORITHM_PUBLISH,
        Permission.ALGORITHM_PURCHASE,
    },
    Role.MEMBER: {
        Permission.JOB_CREATE,
        Permission.JOB_READ,
        Permission.JOB_UPDATE,
        Permission.JOB_CANCEL,
        Permission.KEY_CREATE,
        Permission.KEY_READ,
        Permission.BILLING_READ,
        Permission.ALGORITHM_PURCHASE,
    },
    Role.VIEWER: {
        Permission.JOB_READ,
        Permission.KEY_READ,
    },
    Role.BILLING_ADMIN: {
        Permission.JOB_READ,
        Permission.BILLING_READ,
        Permission.BILLING_MANAGE,
    },
}


@dataclass
class Tenant:
    """Tenant entity for multi-tenant isolation."""

    tenant_id: str
    name: str
    slug: str
    tier: TenantTier = TenantTier.FREE
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    settings: dict[str, Any] = field(default_factory=dict)
    quotas: dict[str, int] = field(default_factory=dict)

    @classmethod
    def create(cls, name: str, tier: TenantTier = TenantTier.FREE) -> "Tenant":
        """Create a new tenant."""
        slug = name.lower().replace(" ", "-").replace("_", "-")[:50]
        tenant_id = f"tenant_{uuid4().hex[:12]}"

        quotas = get_tier_quotas(tier)

        return cls(
            tenant_id=tenant_id,
            name=name,
            slug=slug,
            tier=tier,
            quotas=quotas,
        )


def get_tier_quotas(tier: TenantTier) -> dict[str, int]:
    """Get resource quotas for a tier."""
    quotas = {
        TenantTier.FREE: {
            "jobs_per_month": 100,
            "shots_per_month": 10000,
            "max_concurrent_jobs": 2,
            "max_users": 1,
            "max_keys": 5,
            "storage_mb": 100,
            "api_calls_per_minute": 60,
        },
        TenantTier.STARTER: {
            "jobs_per_month": 1000,
            "shots_per_month": 100000,
            "max_concurrent_jobs": 5,
            "max_users": 5,
            "max_keys": 20,
            "storage_mb": 1000,
            "api_calls_per_minute": 300,
        },
        TenantTier.PROFESSIONAL: {
            "jobs_per_month": 10000,
            "shots_per_month": 1000000,
            "max_concurrent_jobs": 20,
            "max_users": 50,
            "max_keys": 100,
            "storage_mb": 10000,
            "api_calls_per_minute": 1000,
        },
        TenantTier.ENTERPRISE: {
            "jobs_per_month": -1,  # Unlimited
            "shots_per_month": -1,
            "max_concurrent_jobs": 100,
            "max_users": -1,
            "max_keys": -1,
            "storage_mb": 100000,
            "api_calls_per_minute": 10000,
        },
    }
    return quotas.get(tier, quotas[TenantTier.FREE])


@dataclass
class TenantMembership:
    """User membership in a tenant."""

    tenant_id: str
    user_id: str
    role: Role = Role.MEMBER
    custom_permissions: set[Permission] = field(default_factory=set)
    joined_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    invited_by: str | None = None

    def has_permission(self, permission: Permission) -> bool:
        """Check if member has a specific permission."""
        role_perms = ROLE_PERMISSIONS.get(self.role, set())
        return permission in role_perms or permission in self.custom_permissions


# Pydantic Models for API


class TenantCreate(BaseModel):
    """Request to create a new tenant."""

    name: str = Field(..., min_length=2, max_length=100)
    tier: TenantTier = Field(default=TenantTier.FREE)
    admin_email: EmailStr


class TenantResponse(BaseModel):
    """Tenant details response."""

    tenant_id: str
    name: str
    slug: str
    tier: TenantTier
    is_active: bool
    created_at: str
    quotas: dict[str, int]
    usage: dict[str, int] = Field(default_factory=dict)


class TenantMemberCreate(BaseModel):
    """Request to add a member to tenant."""

    user_email: EmailStr
    role: Role = Field(default=Role.MEMBER)
    custom_permissions: list[Permission] = Field(default_factory=list)


class TenantMemberResponse(BaseModel):
    """Tenant member details."""

    user_id: str
    email: str
    username: str
    role: Role
    custom_permissions: list[str]
    joined_at: str


class TenantQuotaCheck(BaseModel):
    """Quota check response."""

    resource: str
    used: int
    limit: int
    remaining: int
    exceeded: bool


class TenantUsage(BaseModel):
    """Tenant usage statistics."""

    tenant_id: str
    period: str
    jobs_count: int
    shots_used: int
    compute_seconds: float
    api_calls: int
    storage_used_mb: float


class RoleUpdate(BaseModel):
    """Request to update member role."""

    role: Role
    custom_permissions: list[Permission] | None = None


class TenantSettingsUpdate(BaseModel):
    """Request to update tenant settings."""

    name: str | None = None
    settings: dict[str, Any] | None = None

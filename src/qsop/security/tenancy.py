"""Multi-tenant isolation and context management."""

from __future__ import annotations

import functools
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Generic,
    List,
    Optional,
    Set,
    TypeVar,
    ParamSpec,
)

P = ParamSpec("P")
T = TypeVar("T")
ResourceT = TypeVar("ResourceT")


class TenantStatus(Enum):
    """Tenant lifecycle status."""
    
    ACTIVE = auto()
    SUSPENDED = auto()
    PENDING = auto()
    DELETED = auto()


class IsolationLevel(Enum):
    """Level of tenant isolation."""
    
    SHARED = auto()
    DEDICATED = auto()
    ISOLATED = auto()


@dataclass
class TenantQuota:
    """Resource quotas for a tenant."""
    
    max_keys: int = 1000
    max_operations_per_hour: int = 10000
    max_storage_bytes: int = 1024 * 1024 * 1024  # 1GB
    max_concurrent_jobs: int = 10
    
    current_keys: int = 0
    current_operations: int = 0
    current_storage_bytes: int = 0
    current_concurrent_jobs: int = 0
    
    def can_create_key(self) -> bool:
        return self.current_keys < self.max_keys
    
    def can_perform_operation(self) -> bool:
        return self.current_operations < self.max_operations_per_hour
    
    def can_use_storage(self, bytes_needed: int) -> bool:
        return self.current_storage_bytes + bytes_needed <= self.max_storage_bytes
    
    def can_submit_job(self) -> bool:
        return self.current_concurrent_jobs < self.max_concurrent_jobs


@dataclass
class TenantContext:
    """Context for a tenant operation."""
    
    tenant_id: str
    tenant_name: str
    status: TenantStatus = TenantStatus.ACTIVE
    isolation_level: IsolationLevel = IsolationLevel.SHARED
    quota: TenantQuota = field(default_factory=TenantQuota)
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_tenant_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def is_active(self) -> bool:
        """Check if tenant is active."""
        return self.status == TenantStatus.ACTIVE
    
    def get_resource_prefix(self) -> str:
        """Get prefix for tenant-scoped resources."""
        return f"tenant:{self.tenant_id}:"
    
    def scope_resource_id(self, resource_id: str) -> str:
        """Add tenant scope to a resource ID."""
        prefix = self.get_resource_prefix()
        if resource_id.startswith(prefix):
            return resource_id
        return f"{prefix}{resource_id}"
    
    def unscope_resource_id(self, scoped_id: str) -> str:
        """Remove tenant scope from a resource ID."""
        prefix = self.get_resource_prefix()
        if scoped_id.startswith(prefix):
            return scoped_id[len(prefix):]
        return scoped_id
    
    def is_resource_owned(self, scoped_id: str) -> bool:
        """Check if a scoped resource ID belongs to this tenant."""
        return scoped_id.startswith(self.get_resource_prefix())


class TenantError(Exception):
    """Base exception for tenant-related errors."""
    pass


class TenantNotFoundError(TenantError):
    """Raised when tenant is not found."""
    
    def __init__(self, tenant_id: str):
        super().__init__(f"Tenant not found: {tenant_id}")
        self.tenant_id = tenant_id


class TenantAccessDeniedError(TenantError):
    """Raised when access to tenant resources is denied."""
    
    def __init__(self, tenant_id: str, resource_id: str):
        super().__init__(
            f"Access denied: resource {resource_id} does not belong to tenant {tenant_id}"
        )
        self.tenant_id = tenant_id
        self.resource_id = resource_id


class TenantQuotaExceededError(TenantError):
    """Raised when tenant quota is exceeded."""
    
    def __init__(self, tenant_id: str, quota_type: str):
        super().__init__(
            f"Quota exceeded for tenant {tenant_id}: {quota_type}"
        )
        self.tenant_id = tenant_id
        self.quota_type = quota_type


class TenantSuspendedError(TenantError):
    """Raised when operations on suspended tenant are attempted."""
    
    def __init__(self, tenant_id: str):
        super().__init__(f"Tenant is suspended: {tenant_id}")
        self.tenant_id = tenant_id


_current_tenant: ContextVar[Optional[TenantContext]] = ContextVar(
    "current_tenant", default=None
)


def get_current_tenant() -> Optional[TenantContext]:
    """Get the current tenant context."""
    return _current_tenant.get()


def set_current_tenant(tenant: Optional[TenantContext]) -> None:
    """Set the current tenant context."""
    _current_tenant.set(tenant)


@contextmanager
def tenant_scope(tenant: TenantContext) -> Generator[TenantContext, None, None]:
    """
    Context manager for tenant-scoped operations.
    
    Args:
        tenant: The tenant context to use
        
    Yields:
        The tenant context
        
    Raises:
        TenantSuspendedError: If tenant is suspended
    """
    if tenant.status == TenantStatus.SUSPENDED:
        raise TenantSuspendedError(tenant.tenant_id)
    
    previous = get_current_tenant()
    set_current_tenant(tenant)
    try:
        yield tenant
    finally:
        set_current_tenant(previous)


class TenantManager:
    """Manages tenant lifecycle and operations."""
    
    def __init__(self) -> None:
        self._tenants: Dict[str, TenantContext] = {}
        self._tenant_hierarchy: Dict[str, Set[str]] = {}
    
    def create_tenant(
        self,
        tenant_id: str,
        tenant_name: str,
        isolation_level: IsolationLevel = IsolationLevel.SHARED,
        parent_tenant_id: Optional[str] = None,
        quota: Optional[TenantQuota] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TenantContext:
        """
        Create a new tenant.
        
        Args:
            tenant_id: Unique tenant identifier
            tenant_name: Human-readable tenant name
            isolation_level: Level of isolation for the tenant
            parent_tenant_id: Optional parent tenant for hierarchy
            quota: Resource quotas for the tenant
            metadata: Additional tenant metadata
            
        Returns:
            The created tenant context
        """
        if tenant_id in self._tenants:
            raise TenantError(f"Tenant already exists: {tenant_id}")
        
        if parent_tenant_id and parent_tenant_id not in self._tenants:
            raise TenantNotFoundError(parent_tenant_id)
        
        tenant = TenantContext(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            status=TenantStatus.ACTIVE,
            isolation_level=isolation_level,
            quota=quota or TenantQuota(),
            metadata=metadata or {},
            parent_tenant_id=parent_tenant_id,
        )
        
        self._tenants[tenant_id] = tenant
        
        if parent_tenant_id:
            if parent_tenant_id not in self._tenant_hierarchy:
                self._tenant_hierarchy[parent_tenant_id] = set()
            self._tenant_hierarchy[parent_tenant_id].add(tenant_id)
        
        return tenant
    
    def get_tenant(self, tenant_id: str) -> TenantContext:
        """
        Get a tenant by ID.
        
        Args:
            tenant_id: The tenant ID
            
        Returns:
            The tenant context
            
        Raises:
            TenantNotFoundError: If tenant doesn't exist
        """
        if tenant_id not in self._tenants:
            raise TenantNotFoundError(tenant_id)
        return self._tenants[tenant_id]
    
    def update_tenant(
        self,
        tenant_id: str,
        status: Optional[TenantStatus] = None,
        quota: Optional[TenantQuota] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TenantContext:
        """
        Update a tenant's configuration.
        
        Args:
            tenant_id: The tenant ID
            status: New status (optional)
            quota: New quota (optional)
            metadata: Metadata to merge (optional)
            
        Returns:
            The updated tenant context
        """
        tenant = self.get_tenant(tenant_id)
        
        if status is not None:
            tenant.status = status
        
        if quota is not None:
            tenant.quota = quota
        
        if metadata is not None:
            tenant.metadata.update(metadata)
        
        return tenant
    
    def delete_tenant(self, tenant_id: str, cascade: bool = False) -> None:
        """
        Delete a tenant.
        
        Args:
            tenant_id: The tenant ID
            cascade: Whether to delete child tenants
            
        Raises:
            TenantError: If tenant has children and cascade is False
        """
        tenant = self.get_tenant(tenant_id)
        
        children = self._tenant_hierarchy.get(tenant_id, set())
        if children and not cascade:
            raise TenantError(
                f"Cannot delete tenant {tenant_id} with children: {children}"
            )
        
        if cascade:
            for child_id in list(children):
                self.delete_tenant(child_id, cascade=True)
        
        tenant.status = TenantStatus.DELETED
        del self._tenants[tenant_id]
        
        if tenant.parent_tenant_id:
            parent_children = self._tenant_hierarchy.get(tenant.parent_tenant_id)
            if parent_children:
                parent_children.discard(tenant_id)
        
        if tenant_id in self._tenant_hierarchy:
            del self._tenant_hierarchy[tenant_id]
    
    def suspend_tenant(self, tenant_id: str, cascade: bool = True) -> None:
        """
        Suspend a tenant.
        
        Args:
            tenant_id: The tenant ID
            cascade: Whether to suspend child tenants
        """
        tenant = self.get_tenant(tenant_id)
        tenant.status = TenantStatus.SUSPENDED
        
        if cascade:
            for child_id in self._tenant_hierarchy.get(tenant_id, set()):
                self.suspend_tenant(child_id, cascade=True)
    
    def activate_tenant(self, tenant_id: str) -> None:
        """
        Activate a suspended tenant.
        
        Args:
            tenant_id: The tenant ID
        """
        tenant = self.get_tenant(tenant_id)
        tenant.status = TenantStatus.ACTIVE
    
    def get_child_tenants(self, tenant_id: str) -> List[TenantContext]:
        """Get all direct child tenants."""
        children = self._tenant_hierarchy.get(tenant_id, set())
        return [self._tenants[child_id] for child_id in children]
    
    def list_tenants(
        self,
        status: Optional[TenantStatus] = None,
        isolation_level: Optional[IsolationLevel] = None,
    ) -> List[TenantContext]:
        """
        List tenants with optional filters.
        
        Args:
            status: Filter by status
            isolation_level: Filter by isolation level
            
        Returns:
            List of matching tenants
        """
        result = list(self._tenants.values())
        
        if status is not None:
            result = [t for t in result if t.status == status]
        
        if isolation_level is not None:
            result = [t for t in result if t.isolation_level == isolation_level]
        
        return result


class TenantScopedResource(Generic[ResourceT]):
    """Base class for tenant-scoped resources."""
    
    def __init__(self) -> None:
        self._resources: Dict[str, Dict[str, ResourceT]] = {}
    
    def _get_tenant_id(self) -> str:
        """Get current tenant ID or raise error."""
        tenant = get_current_tenant()
        if tenant is None:
            raise TenantError("No tenant context available")
        if not tenant.is_active():
            raise TenantSuspendedError(tenant.tenant_id)
        return tenant.tenant_id
    
    def set(self, resource_id: str, resource: ResourceT) -> None:
        """Store a resource scoped to current tenant."""
        tenant_id = self._get_tenant_id()
        if tenant_id not in self._resources:
            self._resources[tenant_id] = {}
        self._resources[tenant_id][resource_id] = resource
    
    def get(self, resource_id: str) -> Optional[ResourceT]:
        """Get a resource scoped to current tenant."""
        tenant_id = self._get_tenant_id()
        tenant_resources = self._resources.get(tenant_id, {})
        return tenant_resources.get(resource_id)
    
    def delete(self, resource_id: str) -> bool:
        """Delete a resource scoped to current tenant."""
        tenant_id = self._get_tenant_id()
        if tenant_id in self._resources:
            if resource_id in self._resources[tenant_id]:
                del self._resources[tenant_id][resource_id]
                return True
        return False
    
    def list(self) -> List[ResourceT]:
        """List all resources for current tenant."""
        tenant_id = self._get_tenant_id()
        return list(self._resources.get(tenant_id, {}).values())
    
    def list_ids(self) -> List[str]:
        """List all resource IDs for current tenant."""
        tenant_id = self._get_tenant_id()
        return list(self._resources.get(tenant_id, {}).keys())
    
    def count(self) -> int:
        """Count resources for current tenant."""
        tenant_id = self._get_tenant_id()
        return len(self._resources.get(tenant_id, {}))


def require_tenant(func: Callable[P, T]) -> Callable[P, T]:
    """Decorator to require a tenant context."""
    
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        tenant = get_current_tenant()
        if tenant is None:
            raise TenantError("No tenant context available")
        if not tenant.is_active():
            raise TenantSuspendedError(tenant.tenant_id)
        return func(*args, **kwargs)
    
    return wrapper


def require_tenant_quota(quota_type: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to check tenant quota before operation."""
    
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            tenant = get_current_tenant()
            if tenant is None:
                raise TenantError("No tenant context available")
            
            quota = tenant.quota
            checks = {
                "keys": quota.can_create_key,
                "operations": quota.can_perform_operation,
                "jobs": quota.can_submit_job,
            }
            
            if quota_type in checks:
                if not checks[quota_type]():
                    raise TenantQuotaExceededError(tenant.tenant_id, quota_type)
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

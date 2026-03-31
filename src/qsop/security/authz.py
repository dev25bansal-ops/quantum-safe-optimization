"""Role-based access control and permission management."""

from __future__ import annotations

import functools
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


class Permission(Enum):
    """Permissions for QSOP resources."""

    # Key operations
    KEY_CREATE = auto()
    KEY_READ = auto()
    KEY_UPDATE = auto()
    KEY_DELETE = auto()
    KEY_ROTATE = auto()
    KEY_EXPORT = auto()

    # Encryption operations
    ENCRYPT = auto()
    DECRYPT = auto()

    # Signature operations
    SIGN = auto()
    VERIFY = auto()

    # Optimization operations
    OPTIMIZATION_SUBMIT = auto()
    OPTIMIZATION_READ = auto()
    OPTIMIZATION_CANCEL = auto()

    # Admin operations
    ADMIN_READ = auto()
    ADMIN_WRITE = auto()
    AUDIT_READ = auto()

    # Tenant operations
    TENANT_CREATE = auto()
    TENANT_READ = auto()
    TENANT_UPDATE = auto()
    TENANT_DELETE = auto()


@dataclass(frozen=True)
class Role:
    """A role with a set of permissions."""

    name: str
    permissions: frozenset[Permission]
    description: str = ""

    def has_permission(self, permission: Permission) -> bool:
        """Check if role has the specified permission."""
        return permission in self.permissions

    def has_all_permissions(self, permissions: set[Permission]) -> bool:
        """Check if role has all specified permissions."""
        return permissions.issubset(self.permissions)

    def has_any_permission(self, permissions: set[Permission]) -> bool:
        """Check if role has any of the specified permissions."""
        return bool(permissions.intersection(self.permissions))


# Predefined roles
ROLE_VIEWER = Role(
    name="viewer",
    permissions=frozenset(
        {
            Permission.KEY_READ,
            Permission.VERIFY,
            Permission.OPTIMIZATION_READ,
        }
    ),
    description="Read-only access to resources",
)

ROLE_OPERATOR = Role(
    name="operator",
    permissions=frozenset(
        {
            Permission.KEY_READ,
            Permission.ENCRYPT,
            Permission.DECRYPT,
            Permission.SIGN,
            Permission.VERIFY,
            Permission.OPTIMIZATION_SUBMIT,
            Permission.OPTIMIZATION_READ,
            Permission.OPTIMIZATION_CANCEL,
        }
    ),
    description="Standard operational access",
)

ROLE_KEY_MANAGER = Role(
    name="key_manager",
    permissions=frozenset(
        {
            Permission.KEY_CREATE,
            Permission.KEY_READ,
            Permission.KEY_UPDATE,
            Permission.KEY_DELETE,
            Permission.KEY_ROTATE,
            Permission.ENCRYPT,
            Permission.DECRYPT,
            Permission.SIGN,
            Permission.VERIFY,
        }
    ),
    description="Full key management access",
)

ROLE_ADMIN = Role(
    name="admin",
    permissions=frozenset(Permission),
    description="Full administrative access",
)


@dataclass
class Principal:
    """A security principal (user, service, etc.)."""

    id: str
    roles: set[Role] = field(default_factory=set)
    resource_ownership: dict[str, set[str]] = field(default_factory=dict)
    tenant_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def has_permission(self, permission: Permission) -> bool:
        """Check if principal has permission through any role."""
        return any(role.has_permission(permission) for role in self.roles)


def has_all_permissions(self, permissions: set[Permission]) -> bool:
    """Check if principal has all permissions."""
    all_perms: set[Permission] = set()
    for role in self.roles:
        all_perms.update(role.permissions)
    return permissions.issubset(all_perms)

    def owns_resource(self, resource_type: str, resource_id: str) -> bool:
        """Check if principal owns a specific resource."""
        owned = self.resource_ownership.get(resource_type, set())
        return resource_id in owned

    def add_resource_ownership(self, resource_type: str, resource_id: str) -> None:
        """Add resource ownership."""
        if resource_type not in self.resource_ownership:
            self.resource_ownership[resource_type] = set()
        self.resource_ownership[resource_type].add(resource_id)

    def remove_resource_ownership(self, resource_type: str, resource_id: str) -> None:
        """Remove resource ownership."""
        if resource_type in self.resource_ownership:
            self.resource_ownership[resource_type].discard(resource_id)


_current_principal: ContextVar[Principal | None] = ContextVar("current_principal", default=None)


class AuthorizationError(Exception):
    """Raised when authorization fails."""

    def __init__(
        self,
        message: str,
        required_permission: Permission | None = None,
        principal_id: str | None = None,
    ):
        super().__init__(message)
        self.required_permission = required_permission
        self.principal_id = principal_id


class RoleManager:
    """Manages roles and role assignments."""

    def __init__(self) -> None:
        self._roles: dict[str, Role] = {
            ROLE_VIEWER.name: ROLE_VIEWER,
            ROLE_OPERATOR.name: ROLE_OPERATOR,
            ROLE_KEY_MANAGER.name: ROLE_KEY_MANAGER,
            ROLE_ADMIN.name: ROLE_ADMIN,
        }
        self._principal_roles: dict[str, set[str]] = {}

    def register_role(self, role: Role) -> None:
        """Register a custom role."""
        self._roles[role.name] = role

    def get_role(self, name: str) -> Role | None:
        """Get a role by name."""
        return self._roles.get(name)

    def assign_role(self, principal_id: str, role_name: str) -> bool:
        """Assign a role to a principal."""
        if role_name not in self._roles:
            return False
        if principal_id not in self._principal_roles:
            self._principal_roles[principal_id] = set()
        self._principal_roles[principal_id].add(role_name)
        return True

    def revoke_role(self, principal_id: str, role_name: str) -> bool:
        """Revoke a role from a principal."""
        if principal_id in self._principal_roles:
            self._principal_roles[principal_id].discard(role_name)
            return True
        return False

    def get_principal_roles(self, principal_id: str) -> set[Role]:
        """Get all roles for a principal."""
        role_names = self._principal_roles.get(principal_id, set())
        return {self._roles[name] for name in role_names if name in self._roles}

    def get_principal_permissions(self, principal_id: str) -> set[Permission]:
        """Get all permissions for a principal."""
        permissions: set[Permission] = set()
        for role in self.get_principal_roles(principal_id):
            permissions.update(role.permissions)
        return permissions


def get_current_principal() -> Principal | None:
    """Get the current security principal from context."""
    return _current_principal.get()


def set_current_principal(principal: Principal | None) -> None:
    """Set the current security principal in context."""
    _current_principal.set(principal)


def check_permission(
    permission: Permission,
    principal: Principal | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> bool:
    """
    Check if principal has permission.

    Args:
        permission: The permission to check
        principal: The principal to check (uses current if not provided)
        resource_type: Optional resource type for ownership check
        resource_id: Optional resource ID for ownership check

    Returns:
        True if authorized, False otherwise
    """
    if principal is None:
        principal = get_current_principal()

    if principal is None:
        return False

    if not principal.has_permission(permission):
        return False

    if resource_type and resource_id:
        if not principal.owns_resource(resource_type, resource_id):
            if not principal.has_permission(Permission.ADMIN_READ):
                return False

    return True


def require_permission(
    permission: Permission,
    resource_type: str | None = None,
    resource_id_param: str | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to require permission for a function.

    Args:
        permission: The required permission
        resource_type: Optional resource type for ownership check
        resource_id_param: Name of parameter containing resource ID
    """


def decorator(func: Callable[P, T]) -> Callable[P, T]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        principal = get_current_principal()

        resource_id: str | None = None
        if resource_id_param and resource_id_param in kwargs:
            rid = kwargs[resource_id_param]
            if isinstance(rid, str):
                resource_id = rid

        if not check_permission(
            permission,
            principal,
            resource_type,
            resource_id,
        ):
            principal_id = principal.id if principal else "anonymous"
            raise AuthorizationError(
                f"Permission denied: {permission.name} for {principal_id}",
                required_permission=permission,
                principal_id=principal_id,
            )

        return func(*args, **kwargs)

    return wrapper

    return decorator


def validate_resource_ownership(
    principal: Principal,
    resource_type: str,
    resource_id: str,
    allow_admin: bool = True,
) -> bool:
    """
    Validate that a principal owns a resource or is admin.

    Args:
        principal: The principal to check
        resource_type: The type of resource
        resource_id: The resource ID
        allow_admin: Whether admins can access any resource

    Returns:
        True if ownership is valid
    """
    if principal.owns_resource(resource_type, resource_id):
        return True

    if allow_admin and principal.has_permission(Permission.ADMIN_READ):
        return True

    return False

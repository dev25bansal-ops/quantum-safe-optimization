"""QSOP Security Layer - Comprehensive security utilities for quantum-safe operations."""

from .audit import (
    AuditEvent,
    AuditEventType,
    AuditLogger,
)
from .authz import (
    Permission,
    Role,
    RoleManager,
    check_permission,
    require_permission,
)
from .compliance import (
    ComplianceChecker,
    CompliancePolicy,
)
from .secrets import (
    SecureBytes,
    generate_secure_random,
    secure_compare,
    zeroize,
)
from .tenancy import (
    TenantContext,
    TenantManager,
    get_current_tenant,
    tenant_scope,
)
from .validation import (
    ValidationError,
    canonicalize,
    check_complexity,
    check_size_limits,
    validate_input,
)

__all__ = [
    # authz
    "Permission",
    "Role",
    "RoleManager",
    "check_permission",
    "require_permission",
    # tenancy
    "TenantContext",
    "TenantManager",
    "tenant_scope",
    "get_current_tenant",
    # secrets
    "SecureBytes",
    "secure_compare",
    "zeroize",
    "generate_secure_random",
    # validation
    "ValidationError",
    "validate_input",
    "canonicalize",
    "check_size_limits",
    "check_complexity",
    # audit
    "AuditLogger",
    "AuditEvent",
    "AuditEventType",
    # compliance
    "ComplianceChecker",
    "CompliancePolicy",
]

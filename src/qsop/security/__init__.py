"""QSOP Security Layer - Comprehensive security utilities for quantum-safe operations."""

from .authz import (
    Permission,
    Role,
    RoleManager,
    check_permission,
    require_permission,
)
from .tenancy import (
    TenantContext,
    TenantManager,
    tenant_scope,
    get_current_tenant,
)
from .secrets import (
    SecureBytes,
    secure_compare,
    zeroize,
    generate_secure_random,
)
from .validation import (
    ValidationError,
    validate_input,
    canonicalize,
    check_size_limits,
    check_complexity,
)
from .audit import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
)
from .compliance import (
    ComplianceChecker,
    CompliancePolicy,
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

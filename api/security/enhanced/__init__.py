"""Security module for encryption, secrets, audit, and integrity."""

from .audit_integrity import (
    AuditIntegrityManager,
    SignedAuditEntry,
    get_audit_integrity,
    sign_audit_entry,
    verify_audit_chain,
)
from .audit_retention import (
    AuditEvent,
    AuditLogManager,
    RetentionPolicy,
    cleanup_old_logs,
    get_audit_logs,
    log_audit_event,
)
from .encryption import (
    EncryptionManager,
    decrypt_data,
    decrypt_file,
    encrypt_data,
    encrypt_file,
    get_encryption_manager,
)
from .quantum_encryption import (
    QuantumSafeEncryptionManager,
    WrappedKey,
    decrypt_with_mlkem,
    encrypt_with_mlkem,
    get_qs_encryption_manager,
)
from .request_signing import (
    RequestSigningManager,
    RequestSigningMiddleware,
    get_request_signer,
    sign_api_request,
)
from .router import router
from .secrets_rotation import (
    RotationPolicy,
    SecretMetadata,
    SecretRotationManager,
    get_rotation_status,
    rotate_secret,
)

__all__ = [
    "EncryptionManager",
    "encrypt_data",
    "decrypt_data",
    "encrypt_file",
    "decrypt_file",
    "get_encryption_manager",
    "SecretRotationManager",
    "RotationPolicy",
    "SecretMetadata",
    "rotate_secret",
    "get_rotation_status",
    "AuditLogManager",
    "RetentionPolicy",
    "AuditEvent",
    "log_audit_event",
    "get_audit_logs",
    "cleanup_old_logs",
    "QuantumSafeEncryptionManager",
    "WrappedKey",
    "encrypt_with_mlkem",
    "decrypt_with_mlkem",
    "get_qs_encryption_manager",
    "AuditIntegrityManager",
    "SignedAuditEntry",
    "sign_audit_entry",
    "verify_audit_chain",
    "get_audit_integrity",
    "RequestSigningManager",
    "RequestSigningMiddleware",
    "sign_api_request",
    "get_request_signer",
    "router",
]

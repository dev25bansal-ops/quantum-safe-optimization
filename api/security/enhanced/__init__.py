"""Security module for encryption, secrets, audit, and integrity."""

from .encryption import (
    EncryptionManager,
    encrypt_data,
    decrypt_data,
    encrypt_file,
    decrypt_file,
    get_encryption_manager,
)
from .secrets_rotation import (
    SecretRotationManager,
    RotationPolicy,
    SecretMetadata,
    rotate_secret,
    get_rotation_status,
)
from .audit_retention import (
    AuditLogManager,
    RetentionPolicy,
    AuditEvent,
    log_audit_event,
    get_audit_logs,
    cleanup_old_logs,
)
from .quantum_encryption import (
    QuantumSafeEncryptionManager,
    WrappedKey,
    encrypt_with_mlkem,
    decrypt_with_mlkem,
    get_qs_encryption_manager,
)
from .audit_integrity import (
    AuditIntegrityManager,
    SignedAuditEntry,
    sign_audit_entry,
    verify_audit_chain,
    get_audit_integrity,
)
from .request_signing import (
    RequestSigningManager,
    RequestSigningMiddleware,
    sign_api_request,
    get_request_signer,
)
from .router import router

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

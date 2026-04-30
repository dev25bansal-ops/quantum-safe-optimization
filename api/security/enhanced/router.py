"""
Security router for encryption, rotation, audit, and integrity APIs.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .audit_integrity import (
    get_audit_integrity,
    sign_audit_entry,
    verify_audit_chain,
)
from .audit_retention import (
    AuditEventType,
    AuditSeverity,
    cleanup_old_logs,
    get_audit_logs,
    get_audit_manager,
    log_audit_event,
)
from .encryption import (
    get_encryption_manager,
)
from .quantum_encryption import (
    decrypt_with_mlkem,
    encrypt_with_mlkem,
    get_qs_encryption_manager,
)
from .request_signing import (
    get_request_signer,
    sign_api_request,
)
from .secrets_rotation import (
    SecretType,
    get_rotation_manager,
    get_rotation_status,
    rotate_secret,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_user_id() -> str:
    return "user_default"


def get_tenant_id() -> str:
    return "tenant_default"


# ============================================================================
# Quantum-Safe Encryption Endpoints
# ============================================================================


@router.get("/quantum-encryption/status")
async def get_qs_encryption_status():
    """Get quantum-safe encryption status."""
    manager = get_qs_encryption_manager()
    return manager.export_public_params()


@router.post("/quantum-encryption/encrypt")
async def quantum_encrypt_endpoint(
    data: dict[str, Any],
    user_id: str = Depends(get_user_id),
):
    """Encrypt data with ML-KEM wrapped AES."""
    ciphertext = encrypt_with_mlkem(data)

    log_audit_event(
        event_type=AuditEventType.DATA_ACCESS,
        severity=AuditSeverity.INFO,
        user_id=user_id,
        action="data_encrypted_mlkem",
    )

    return {"ciphertext": ciphertext, "algorithm": "ML-KEM-768 + AES-256-GCM"}


@router.post("/quantum-encryption/decrypt")
async def quantum_decrypt_endpoint(
    ciphertext: str,
    user_id: str = Depends(get_user_id),
):
    """Decrypt data encrypted with ML-KEM wrapped AES."""
    try:
        plaintext = decrypt_with_mlkem(ciphertext)

        log_audit_event(
            event_type=AuditEventType.DATA_ACCESS,
            severity=AuditSeverity.INFO,
            user_id=user_id,
            action="data_decrypted_mlkem",
        )

        return {"plaintext": plaintext}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Decryption failed: {e}")


@router.post("/quantum-encryption/rotate")
async def rotate_qs_key(user_id: str = Depends(get_user_id)):
    """Rotate quantum-safe encryption key."""
    manager = get_qs_encryption_manager()
    new_key_id = manager.rotate_key()

    log_audit_event(
        event_type=AuditEventType.SECRET_ROTATE,
        severity=AuditSeverity.WARNING,
        user_id=user_id,
        action="mlkem_key_rotated",
        details={"new_key_id": new_key_id},
    )

    return {"status": "rotated", "new_key_id": new_key_id}


# ============================================================================
# Audit Integrity Endpoints
# ============================================================================


@router.get("/audit-integrity/status")
async def get_audit_integrity_status():
    """Get audit log integrity status."""
    manager = get_audit_integrity()
    return manager.get_integrity_status()


@router.post("/audit-integrity/verify")
async def verify_audit_integrity(
    start_index: int = Query(default=0, ge=0),
    user_id: str = Depends(get_user_id),
):
    """Verify audit log chain integrity."""
    result = verify_audit_chain()

    log_audit_event(
        event_type=AuditEventType.ADMIN_ACTION,
        severity=AuditSeverity.INFO,
        user_id=user_id,
        action="audit_chain_verified",
        details=result,
    )

    return result


@router.get("/audit-integrity/public-key")
async def get_audit_public_key():
    """Get public key for audit log verification."""
    manager = get_audit_integrity()
    return {
        "public_key": manager.get_public_key(),
        "algorithm": "ML-DSA-65",
    }


@router.post("/audit-integrity/sign")
async def sign_audit_event(
    event_data: dict[str, Any],
    user_id: str = Depends(get_user_id),
):
    """Sign an audit event."""
    entry = sign_audit_entry(event_data)
    return entry.to_dict()


# ============================================================================
# Request Signing Endpoints
# ============================================================================


@router.get("/request-signing/status")
async def get_request_signing_status():
    """Get request signing manager status."""
    signer = get_request_signer()
    return signer.get_status()


@router.get("/request-signing/public-key")
async def get_signing_public_key(key_id: str | None = None):
    """Get public key for request verification."""
    signer = get_request_signer()
    return {
        "public_key": signer.get_public_key(key_id),
        "algorithm": "ML-DSA-65",
    }


@router.post("/request-signing/sign")
async def sign_outgoing_request(
    method: str,
    path: str,
    body: str | None = None,
    user_id: str = Depends(get_user_id),
):
    """Generate signature headers for outgoing request."""
    headers = sign_api_request(
        method=method,
        path=path,
        body=body,
    )

    log_audit_event(
        event_type=AuditEventType.API_ACCESS,
        severity=AuditSeverity.INFO,
        user_id=user_id,
        action="request_signed",
        details={"method": method, "path": path},
    )

    return {"headers": headers}


@router.post("/request-signing/rotate")
async def rotate_signing_key(user_id: str = Depends(get_user_id)):
    """Rotate request signing key."""
    signer = get_request_signer()
    new_key_id = signer.rotate_key()

    log_audit_event(
        event_type=AuditEventType.SECRET_ROTATE,
        severity=AuditSeverity.WARNING,
        user_id=user_id,
        action="signing_key_rotated",
        details={"new_key_id": new_key_id},
    )

    return {"status": "rotated", "new_key_id": new_key_id}


# ============================================================================
# PQC Key Rotation Endpoints
# ============================================================================


@router.get("/pqc-keys/status")
async def get_pqc_key_status():
    """Get PQC key rotation status."""
    manager = get_rotation_manager()

    pqc_types = [
        SecretType.PQC_SIGNING_KEY,
        SecretType.PQC_ENCRYPTION_KEY,
    ]

    keys_status = []
    for st in pqc_types:
        secret = manager.get_current_secret(st)
        if secret:
            keys_status.append(
                {
                    "type": st.value,
                    "secret_id": secret.metadata.secret_id,
                    "version": secret.metadata.version,
                    "created_at": secret.metadata.created_at.isoformat(),
                    "expires_at": secret.metadata.expires_at.isoformat()
                    if secret.metadata.expires_at
                    else None,
                    "is_current": secret.metadata.is_current,
                }
            )

    return {
        "keys": keys_status,
        "rotation_interval_days": 90,
        "algorithm_signing": "ML-DSA-65",
        "algorithm_encryption": "ML-KEM-768",
    }


@router.post("/pqc-keys/rotate/{key_type}")
async def rotate_pqc_key(
    key_type: str,
    user_id: str = Depends(get_user_id),
):
    """Rotate PQC key (signing or encryption)."""
    type_map = {
        "signing": SecretType.PQC_SIGNING_KEY,
        "encryption": SecretType.PQC_ENCRYPTION_KEY,
    }

    if key_type not in type_map:
        raise HTTPException(status_code=400, detail=f"Invalid key type: {key_type}")

    secret_type = type_map[key_type]
    new_value = rotate_secret(secret_type)

    log_audit_event(
        event_type=AuditEventType.SECRET_ROTATE,
        severity=AuditSeverity.WARNING,
        user_id=user_id,
        action=f"pqc_key_rotated:{key_type}",
        details={"key_type": key_type},
    )

    return {
        "status": "rotated",
        "key_type": key_type,
        "new_key_preview": new_value[:16] + "..." if new_value else None,
    }


# ============================================================================
# Security Headers Status
# ============================================================================


@router.get("/headers/status")
async def get_security_headers_status(request: Request):
    """Get current security headers configuration."""
    return {
        "headers_applied": {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        },
        "hsts": {
            "enabled": request.url.scheme == "https",
            "max_age": 31536000,
            "include_subdomains": True,
            "preload": True,
        },
        "csp": {
            "default_src": "'none'",
            "frame_ancestors": "'none'",
            "script_src": "'self'",
            "style_src": "'self' 'unsafe-inline'",
            "img_src": "'self' data:",
            "connect_src": "'self'",
        },
    }


# ============================================================================
# Legacy Encryption Endpoints
# ============================================================================


@router.get("/encryption/status")
async def get_encryption_status():
    """Get encryption manager status."""
    manager = get_encryption_manager()
    return manager.export_public_params()


@router.post("/encryption/rotate-key")
async def rotate_encryption_key(
    user_id: str = Depends(get_user_id),
):
    """Rotate the encryption key."""
    manager = get_encryption_manager()
    new_key_id = manager.rotate_key()

    log_audit_event(
        event_type=AuditEventType.SECRET_ROTATE,
        severity=AuditSeverity.WARNING,
        user_id=user_id,
        action="encryption_key_rotated",
        details={"new_key_id": new_key_id},
    )

    return {"status": "rotated", "new_key_id": new_key_id}


@router.get("/rotation/status")
async def get_secret_rotation_status():
    """Get secret rotation status."""
    return get_rotation_status()


@router.get("/rotation/expiring")
async def get_expiring_secrets(
    days: int = Query(default=7, ge=1, le=30),
):
    """Get secrets expiring soon."""
    manager = get_rotation_manager()
    expiring = manager.get_secrets_expiring_soon(days=days)

    return {
        "count": len(expiring),
        "secrets": [
            {
                "secret_id": s.secret_id,
                "type": s.secret_type.value,
                "expires_at": s.expires_at.isoformat(),
            }
            for s in expiring
        ],
    }


# ============================================================================
# Audit Log Endpoints
# ============================================================================


@router.get("/audit/logs")
async def list_audit_logs(
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    event_type: AuditEventType | None = None,
    user_id: str | None = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user_id: str = Depends(get_user_id),
):
    """List audit logs."""
    events = get_audit_logs(
        start_time=start_time,
        end_time=end_time,
        event_type=event_type,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )

    return {
        "total": len(events),
        "events": [e.to_dict() for e in events],
    }


@router.post("/audit/cleanup")
async def trigger_audit_cleanup(
    user_id: str = Depends(get_user_id),
):
    """Trigger audit log cleanup."""
    stats = await cleanup_old_logs()

    log_audit_event(
        event_type=AuditEventType.ADMIN_ACTION,
        severity=AuditSeverity.WARNING,
        user_id=user_id,
        action="audit_cleanup_triggered",
        details=stats,
    )

    return {"status": "completed", "stats": stats}


@router.get("/audit/storage")
async def get_audit_storage_stats():
    """Get audit storage statistics."""
    manager = get_audit_manager()
    return manager.get_storage_stats()


@router.get("/audit/summary")
async def get_audit_summary(
    start_time: datetime | None = None,
    end_time: datetime | None = None,
):
    """Get audit summary statistics."""
    if start_time is None:
        start_time = datetime.now(UTC) - timedelta(days=7)
    if end_time is None:
        end_time = datetime.now(UTC)

    manager = get_audit_manager()
    events = [e for e in manager._events if start_time <= e.timestamp <= end_time]

    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}

    for event in events:
        by_type[event.event_type.value] = by_type.get(event.event_type.value, 0) + 1
        by_severity[event.severity.value] = by_severity.get(event.severity.value, 0) + 1

    return {
        "period": {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
        },
        "total_events": len(events),
        "by_type": by_type,
        "by_severity": by_severity,
    }

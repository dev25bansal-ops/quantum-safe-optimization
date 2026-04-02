"""Security router for encryption, rotation, and audit APIs."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from .encryption import (
    EncryptionManager,
    encrypt_data,
    decrypt_data,
    get_encryption_manager,
)
from .secrets_rotation import (
    SecretType,
    RotationPolicy,
    get_rotation_manager,
    get_rotation_status,
    rotate_secret,
)
from .audit_retention import (
    AuditEventType,
    AuditSeverity,
    RetentionPolicy,
    AuditEvent,
    get_audit_manager,
    log_audit_event,
    get_audit_logs,
    cleanup_old_logs,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_user_id() -> str:
    """Get current user ID (stub for auth integration)."""
    return "user_default"


def get_tenant_id() -> str:
    """Get current tenant ID (stub for auth integration)."""
    return "tenant_default"


# ============================================================================
# Encryption Endpoints
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


@router.post("/encryption/encrypt")
async def encrypt_endpoint(
    data: dict[str, Any],
    user_id: str = Depends(get_user_id),
):
    """Encrypt data."""
    ciphertext = encrypt_data(data)

    log_audit_event(
        event_type=AuditEventType.DATA_ACCESS,
        severity=AuditSeverity.INFO,
        user_id=user_id,
        action="data_encrypted",
    )

    return {"ciphertext": ciphertext}


@router.post("/encryption/decrypt")
async def decrypt_endpoint(
    ciphertext: str,
    user_id: str = Depends(get_user_id),
):
    """Decrypt data."""
    try:
        plaintext = decrypt_data(ciphertext)

        log_audit_event(
            event_type=AuditEventType.DATA_ACCESS,
            severity=AuditSeverity.INFO,
            user_id=user_id,
            action="data_decrypted",
        )

        return {"plaintext": plaintext}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Decryption failed: {e}")


# ============================================================================
# Secret Rotation Endpoints
# ============================================================================


@router.get("/rotation/status")
async def get_secret_rotation_status():
    """Get secret rotation status."""
    return get_rotation_status()


@router.post("/rotation/rotate/{secret_type}")
async def rotate_secret_endpoint(
    secret_type: SecretType,
    user_id: str = Depends(get_user_id),
):
    """Rotate a secret."""
    new_value = rotate_secret(secret_type)

    log_audit_event(
        event_type=AuditEventType.SECRET_ROTATE,
        severity=AuditSeverity.WARNING,
        user_id=user_id,
        action=f"secret_rotated:{secret_type.value}",
    )

    return {
        "status": "rotated",
        "secret_type": secret_type.value,
        "new_value_preview": new_value[:8] + "..." if new_value else None,
    }


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


@router.get("/rotation/policies")
async def get_rotation_policies():
    """Get all rotation policies."""
    manager = get_rotation_manager()
    return {
        "policies": [
            {
                "type": st.value,
                "interval_days": p.rotation_interval_days,
                "grace_period_hours": p.grace_period_hours,
                "auto_rotate": p.auto_rotate,
            }
            for st, p in manager._policies.items()
        ]
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
    tenant_id: str | None = None,
    severity: AuditSeverity | None = None,
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
        tenant_id=tenant_id,
        severity=severity,
        limit=limit,
        offset=offset,
    )

    return {
        "total": len(events),
        "events": [e.to_dict() for e in events],
    }


@router.get("/audit/events/{event_id}")
async def get_audit_event(
    event_id: str,
    user_id: str = Depends(get_user_id),
):
    """Get a specific audit event."""
    manager = get_audit_manager()
    events = [e for e in manager._events if e.event_id == event_id]

    if not events:
        raise HTTPException(status_code=404, detail="Event not found")

    return events[0].to_dict()


@router.post("/audit/cleanup")
async def trigger_audit_cleanup(
    user_id: str = Depends(get_user_id),
):
    """Trigger audit log cleanup."""
    log_audit_event(
        event_type=AuditEventType.ADMIN_ACTION,
        severity=AuditSeverity.WARNING,
        user_id=user_id,
        action="audit_cleanup_triggered",
    )

    stats = await cleanup_old_logs()

    return {"status": "completed", "stats": stats}


@router.get("/audit/storage")
async def get_audit_storage_stats():
    """Get audit storage statistics."""
    manager = get_audit_manager()
    return manager.get_storage_stats()


@router.get("/audit/retention-policy")
async def get_retention_policy():
    """Get current retention policy."""
    manager = get_audit_manager()
    return {
        "policy": {
            "default_retention_days": manager._policy.default_retention_days,
            "severity_retention": manager._policy.severity_retention,
            "event_type_retention": manager._policy.event_type_retention,
            "compress_after_days": manager._policy.compress_after_days,
            "archive_after_days": manager._policy.archive_after_days,
            "delete_archived_after_days": manager._policy.delete_archived_after_days,
        }
    }


@router.put("/audit/retention-policy")
async def update_retention_policy(
    default_retention_days: int = Query(default=90, ge=1, le=3650),
    user_id: str = Depends(get_user_id),
):
    """Update retention policy."""
    manager = get_audit_manager()
    manager._policy.default_retention_days = default_retention_days

    log_audit_event(
        event_type=AuditEventType.CONFIG_CHANGE,
        severity=AuditSeverity.WARNING,
        user_id=user_id,
        action="retention_policy_updated",
        details={"default_retention_days": default_retention_days},
    )

    return {"status": "updated", "default_retention_days": default_retention_days}


@router.get("/audit/summary")
async def get_audit_summary(
    start_time: datetime | None = None,
    end_time: datetime | None = None,
):
    """Get audit summary statistics."""
    if start_time is None:
        start_time = datetime.now(timezone.utc) - timedelta(days=7)
    if end_time is None:
        end_time = datetime.now(timezone.utc)

    manager = get_audit_manager()
    events = [e for e in manager._events if start_time <= e.timestamp <= end_time]

    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_user: dict[str, int] = {}
    failed_count = 0

    for event in events:
        by_type[event.event_type.value] = by_type.get(event.event_type.value, 0) + 1
        by_severity[event.severity.value] = by_severity.get(event.severity.value, 0) + 1
        if event.user_id:
            by_user[event.user_id] = by_user.get(event.user_id, 0) + 1
        if not event.success:
            failed_count += 1

    return {
        "period": {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
        },
        "total_events": len(events),
        "failed_events": failed_count,
        "by_type": by_type,
        "by_severity": by_severity,
        "top_users": sorted(by_user.items(), key=lambda x: x[1], reverse=True)[:10],
    }


# ============================================================================
# WebSocket Auth Check
# ============================================================================


@router.get("/websocket/auth-check")
async def websocket_auth_check(
    token: str | None = None,
    user_id: str | None = None,
):
    """Check WebSocket authentication requirements."""
    if not token and not user_id:
        return {
            "authenticated": False,
            "error": "Either token or user_id required",
            "requirements": {
                "token": "JWT token for authentication (preferred)",
                "user_id": "User ID for legacy/demo mode (not recommended for production)",
            },
        }

    if token:
        try:
            from api.routers.websocket import verify_websocket_token

            verified_user_id = await verify_websocket_token(token)

            log_audit_event(
                event_type=AuditEventType.WEBSOCKET_CONNECT,
                severity=AuditSeverity.INFO,
                user_id=verified_user_id,
                action="websocket_auth_validated",
            )

            return {
                "authenticated": True,
                "user_id": verified_user_id,
                "method": "jwt_token",
            }
        except Exception as e:
            log_audit_event(
                event_type=AuditEventType.AUTH_FAILED,
                severity=AuditSeverity.WARNING,
                action="websocket_auth_failed",
                error_message=str(e),
            )

            return {
                "authenticated": False,
                "error": str(e),
            }

    return {
        "authenticated": True,
        "user_id": user_id,
        "method": "user_id",
        "warning": "Using user_id auth is not recommended for production",
    }

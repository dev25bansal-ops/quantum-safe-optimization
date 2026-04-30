"""
Audit Log Retention Module.

Provides audit logging with configurable retention:
- Structured audit events
- Configurable retention policies
- Automatic log cleanup
- Secure log storage
- Compliance-ready audit trails
"""

import asyncio
import gzip
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events."""

    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_TOKEN_REFRESH = "auth.token_refresh"
    AUTH_FAILED = "auth.failed"
    AUTH_MFA = "auth.mfa"

    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_PASSWORD_CHANGE = "user.password_change"

    JOB_CREATE = "job.create"
    JOB_READ = "job.read"
    JOB_UPDATE = "job.update"
    JOB_DELETE = "job.delete"
    JOB_CANCEL = "job.cancel"

    KEY_CREATE = "key.create"
    KEY_DELETE = "key.delete"
    KEY_ROTATE = "key.rotate"

    SECRET_ACCESS = "secret.access"
    SECRET_ROTATE = "secret.rotate"

    CONFIG_CHANGE = "config.change"

    ADMIN_ACTION = "admin.action"

    DATA_ACCESS = "data.access"
    DATA_EXPORT = "data.export"
    DATA_DELETE = "data.delete"

    SECURITY_EVENT = "security.event"

    API_ACCESS = "api.access"

    WEBSOCKET_CONNECT = "websocket.connect"
    WEBSOCKET_DISCONNECT = "websocket.disconnect"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RetentionPolicy(BaseModel):
    """Policy for audit log retention."""

    name: str
    default_retention_days: int = Field(default=90, ge=1, le=3650)
    severity_retention: dict[str, int] = Field(
        default_factory=lambda: {
            "critical": 365,
            "error": 180,
            "warning": 90,
            "info": 30,
            "debug": 7,
        }
    )
    event_type_retention: dict[str, int] = Field(
        default_factory=lambda: {
            "auth.login": 365,
            "auth.failed": 365,
            "security.event": 365,
            "secret.access": 365,
            "admin.action": 365,
        }
    )
    max_storage_mb: int = Field(default=1024, ge=100)
    compress_after_days: int = Field(default=7, ge=1)
    archive_after_days: int = Field(default=30, ge=7)
    delete_archived_after_days: int = Field(default=365, ge=30)
    include_request_body: bool = False
    include_response_body: bool = False
    hash_sensitive_fields: list[str] = Field(
        default_factory=lambda: ["password", "token", "secret", "key", "credential"]
    )


@dataclass
class AuditEvent:
    """An audit event."""

    event_id: str
    event_type: AuditEventType
    severity: AuditSeverity
    timestamp: datetime
    user_id: str | None
    tenant_id: str | None
    ip_address: str | None
    user_agent: str | None
    resource_type: str | None
    resource_id: str | None
    action: str
    details: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    session_id: str | None = None
    success: bool = True
    error_message: str | None = None
    duration_ms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        event_type_val = self.event_type.value if hasattr(self.event_type, 'value') else self.event_type
        severity_val = self.severity.value if hasattr(self.severity, 'value') else self.severity
        return {
            "event_id": self.event_id,
            "event_type": event_type_val,
            "severity": severity_val,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "details": self.details,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "success": self.success,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class AuditLogManager:
    """
    Manages audit logging with retention.

    Features:
    - Structured audit events
    - Configurable retention
    - Automatic cleanup
    - Log compression
    - Integrity verification
    """

    def __init__(
        self,
        log_dir: str | Path | None = None,
        policy: RetentionPolicy | None = None,
    ):
        self._log_dir = Path(log_dir or os.getenv("AUDIT_LOG_DIR", "logs/audit"))
        self._log_dir.mkdir(parents=True, exist_ok=True)

        self._policy = policy or RetentionPolicy(name="default")
        self._events: list[AuditEvent] = []
        self._current_log_file: Path | None = None
        self._current_log_size: int = 0
        self._max_log_size_bytes: int = 100 * 1024 * 1024  # 100MB per file
        self._cleanup_task: asyncio.Task | None = None
        self._running: bool = False

    def _get_log_file_path(self, date: datetime | None = None) -> Path:
        """Get log file path for a date."""
        date = date or datetime.now(UTC)
        return self._log_dir / f"audit-{date.strftime('%Y-%m-%d')}.jsonl"

    def _hash_sensitive_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Hash sensitive fields in data."""
        result = {}
        for key, value in data.items():
            if key.lower() in [f.lower() for f in self._policy.hash_sensitive_fields]:
                if isinstance(value, str):
                    result[key] = f"hash:{hashlib.sha256(value.encode()).hexdigest()[:16]}"
                else:
                    result[key] = "[REDACTED]"
            elif isinstance(value, dict):
                result[key] = self._hash_sensitive_data(value)
            else:
                result[key] = value
        return result

    def log_event(
        self,
        event_type: AuditEventType,
        severity: AuditSeverity = AuditSeverity.INFO,
        user_id: str | None = None,
        tenant_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        action: str = "",
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
        session_id: str | None = None,
        success: bool = True,
        error_message: str | None = None,
        duration_ms: float | None = None,
    ) -> AuditEvent:
        """Log an audit event."""
        event = AuditEvent(
            event_id=f"evt_{uuid4().hex[:16]}",
            event_type=event_type,
            severity=severity,
            timestamp=datetime.now(UTC),
            user_id=user_id,
            tenant_id=tenant_id,
            ip_address=ip_address,
            user_agent=user_agent,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            details=self._hash_sensitive_data(details) if details else {},
            request_id=request_id,
            session_id=session_id,
            success=success,
            error_message=error_message,
            duration_ms=duration_ms,
        )

        self._write_event(event)

        self._events.append(event)

        if len(self._events) > 10000:
            self._events = self._events[-5000:]

        return event

    def _write_event(self, event: AuditEvent):
        """Write event to log file."""
        log_file = self._get_log_file_path()

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(event.to_json() + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit event: {e}")

    def get_events(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        event_type: AuditEventType | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None,
        severity: AuditSeverity | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """Query audit events."""
        events = list(self._events)

        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
        if end_time:
            events = [e for e in events if e.timestamp <= end_time]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if user_id:
            events = [e for e in events if e.user_id == user_id]
        if tenant_id:
            events = [e for e in events if e.tenant_id == tenant_id]
        if severity:
            events = [e for e in events if e.severity == severity]
        if resource_type:
            events = [e for e in events if e.resource_type == resource_type]
        if resource_id:
            events = [e for e in events if e.resource_id == resource_id]

        events.sort(key=lambda e: e.timestamp, reverse=True)

        return events[offset : offset + limit]

    def get_retention_for_event(self, event: AuditEvent) -> int:
        """Get retention days for an event."""
        if event.event_type.value in self._policy.event_type_retention:
            return self._policy.event_type_retention[event.event_type.value]

        if event.severity.value in self._policy.severity_retention:
            return self._policy.severity_retention[event.severity.value]

        return self._policy.default_retention_days

    async def cleanup_old_logs(self) -> dict[str, int]:
        """Clean up old log files based on retention policy."""
        now = datetime.now(UTC)
        stats = {
            "files_deleted": 0,
            "files_compressed": 0,
            "files_archived": 0,
            "bytes_freed": 0,
        }

        try:
            for log_file in self._log_dir.glob("audit-*.jsonl*"):
                try:
                    date_str = log_file.stem.replace("audit-", "").replace(".jsonl", "")
                    file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
                    age_days = (now - file_date).days

                    if age_days > self._policy.delete_archived_after_days:
                        if log_file.suffix == ".gz":
                            stats["bytes_freed"] += log_file.stat().st_size
                            log_file.unlink()
                            stats["files_deleted"] += 1

                    elif age_days > self._policy.archive_after_days:
                        if log_file.suffix != ".gz":
                            archive_path = self._log_dir / "archive"
                            archive_path.mkdir(exist_ok=True)
                            log_file.rename(archive_path / log_file.name)
                            stats["files_archived"] += 1

                    elif age_days > self._policy.compress_after_days:
                        if log_file.suffix != ".gz":
                            self._compress_file(log_file)
                            stats["files_compressed"] += 1

                except (ValueError, OSError) as e:
                    logger.warning(f"Error processing log file {log_file}: {e}")

        except Exception as e:
            logger.error(f"Cleanup error: {e}")

        logger.info(f"Audit log cleanup: {stats}")

        return stats

    def _compress_file(self, file_path: Path):
        """Compress a log file."""
        compressed_path = file_path.with_suffix(file_path.suffix + ".gz")

        try:
            with open(file_path, "rb") as f_in:
                with gzip.open(compressed_path, "wb") as f_out:
                    f_out.writelines(f_in)

            file_path.unlink()

        except Exception as e:
            logger.error(f"Compression error for {file_path}: {e}")

    async def start_cleanup_scheduler(self):
        """Start automatic cleanup."""
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info("Audit cleanup scheduler started")

    async def stop_cleanup_scheduler(self):
        """Stop automatic cleanup."""
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("Audit cleanup scheduler stopped")

    async def _cleanup_loop(self):
        """Background cleanup task."""
        while self._running:
            try:
                await asyncio.sleep(86400)  # Run daily
                await self.cleanup_old_logs()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")

    def get_storage_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        total_size = 0
        file_count = 0

        for log_file in self._log_dir.glob("audit-*.jsonl*"):
            try:
                total_size += log_file.stat().st_size
                file_count += 1
            except OSError:
                pass

        return {
            "log_directory": str(self._log_dir),
            "file_count": file_count,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "max_storage_mb": self._policy.max_storage_mb,
            "usage_percent": round(
                total_size / (self._policy.max_storage_mb * 1024 * 1024) * 100, 2
            ),
            "events_in_memory": len(self._events),
            "retention_policy": {
                "default_days": self._policy.default_retention_days,
                "compress_after_days": self._policy.compress_after_days,
                "archive_after_days": self._policy.archive_after_days,
                "delete_after_days": self._policy.delete_archived_after_days,
            },
        }


_audit_manager: AuditLogManager | None = None


def get_audit_manager() -> AuditLogManager:
    """Get or create the global audit manager."""
    global _audit_manager
    if _audit_manager is None:
        _audit_manager = AuditLogManager()
    return _audit_manager


def log_audit_event(
    event_type: AuditEventType,
    severity: AuditSeverity = AuditSeverity.INFO,
    **kwargs,
) -> AuditEvent:
    """Log an audit event."""
    return get_audit_manager().log_event(
        event_type=event_type,
        severity=severity,
        **kwargs,
    )


def get_audit_logs(
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    **kwargs,
) -> list[AuditEvent]:
    """Get audit logs."""
    return get_audit_manager().get_events(
        start_time=start_time,
        end_time=end_time,
        **kwargs,
    )


async def cleanup_old_logs() -> dict[str, int]:
    """Clean up old audit logs."""
    return await get_audit_manager().cleanup_old_logs()

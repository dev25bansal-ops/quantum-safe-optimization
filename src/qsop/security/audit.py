"""Audit logging with tamper-evident hash chaining."""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TextIO, Union


class AuditEventType(Enum):
    """Types of security audit events."""
    
    # Authentication events
    AUTH_LOGIN = auto()
    AUTH_LOGOUT = auto()
    AUTH_FAILED = auto()
    AUTH_TOKEN_ISSUED = auto()
    AUTH_TOKEN_REVOKED = auto()
    
    # Authorization events
    AUTHZ_GRANTED = auto()
    AUTHZ_DENIED = auto()
    AUTHZ_ROLE_ASSIGNED = auto()
    AUTHZ_ROLE_REVOKED = auto()
    
    # Key management events
    KEY_CREATED = auto()
    KEY_ROTATED = auto()
    KEY_DELETED = auto()
    KEY_EXPORTED = auto()
    KEY_IMPORTED = auto()
    KEY_ACCESSED = auto()
    
    # Cryptographic operations
    CRYPTO_ENCRYPT = auto()
    CRYPTO_DECRYPT = auto()
    CRYPTO_SIGN = auto()
    CRYPTO_VERIFY = auto()
    CRYPTO_KEM_ENCAPSULATE = auto()
    CRYPTO_KEM_DECAPSULATE = auto()
    
    # Data events
    DATA_ACCESSED = auto()
    DATA_MODIFIED = auto()
    DATA_DELETED = auto()
    DATA_EXPORTED = auto()
    
    # System events
    SYSTEM_START = auto()
    SYSTEM_STOP = auto()
    SYSTEM_CONFIG_CHANGE = auto()
    SYSTEM_ERROR = auto()
    
    # Tenant events
    TENANT_CREATED = auto()
    TENANT_SUSPENDED = auto()
    TENANT_DELETED = auto()
    
    # Compliance events
    COMPLIANCE_VIOLATION = auto()
    COMPLIANCE_CHECK = auto()
    POLICY_CHANGE = auto()


class AuditSeverity(Enum):
    """Severity levels for audit events."""
    
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class AuditEvent:
    """An audit event record."""
    
    event_type: AuditEventType
    timestamp: datetime
    event_id: str
    severity: AuditSeverity
    actor_id: Optional[str]
    tenant_id: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[str]
    action: str
    outcome: str
    details: Dict[str, Any]
    source_ip: Optional[str]
    user_agent: Optional[str]
    request_id: Optional[str]
    session_id: Optional[str]
    previous_hash: Optional[str]
    event_hash: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = {
            "event_type": self.event_type.name,
            "timestamp": self.timestamp.isoformat(),
            "event_id": self.event_id,
            "severity": self.severity.value,
            "actor_id": self.actor_id,
            "tenant_id": self.tenant_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "outcome": self.outcome,
            "details": self.details,
            "source_ip": self.source_ip,
            "user_agent": self.user_agent,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "previous_hash": self.previous_hash,
            "event_hash": self.event_hash,
        }
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEvent":
        """Create from dictionary."""
        return cls(
            event_type=AuditEventType[data["event_type"]],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            event_id=data["event_id"],
            severity=AuditSeverity(data["severity"]),
            actor_id=data.get("actor_id"),
            tenant_id=data.get("tenant_id"),
            resource_type=data.get("resource_type"),
            resource_id=data.get("resource_id"),
            action=data["action"],
            outcome=data["outcome"],
            details=data.get("details", {}),
            source_ip=data.get("source_ip"),
            user_agent=data.get("user_agent"),
            request_id=data.get("request_id"),
            session_id=data.get("session_id"),
            previous_hash=data.get("previous_hash"),
            event_hash=data.get("event_hash"),
        )
    
    def compute_hash(self, hmac_key: Optional[bytes] = None) -> str:
        """
        Compute the hash for this event.
        
        Args:
            hmac_key: Optional key for HMAC (if None, uses SHA-256)
            
        Returns:
            Hex-encoded hash
        """
        hash_data = {
            "event_type": self.event_type.name,
            "timestamp": self.timestamp.isoformat(),
            "event_id": self.event_id,
            "actor_id": self.actor_id,
            "tenant_id": self.tenant_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "outcome": self.outcome,
            "details": self.details,
            "previous_hash": self.previous_hash,
        }
        
        canonical = json.dumps(hash_data, sort_keys=True, separators=(",", ":"))
        data_bytes = canonical.encode("utf-8")
        
        if hmac_key:
            return hmac.new(hmac_key, data_bytes, hashlib.sha256).hexdigest()
        else:
            return hashlib.sha256(data_bytes).hexdigest()


class AuditLogStorage:
    """Base class for audit log storage backends."""
    
    def write(self, event: AuditEvent) -> None:
        """Write an event to storage."""
        raise NotImplementedError
    
    def read(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[AuditEventType]] = None,
        actor_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[AuditEvent]:
        """Read events from storage with filters."""
        raise NotImplementedError
    
    def get_last_hash(self) -> Optional[str]:
        """Get the hash of the last event."""
        raise NotImplementedError
    
    def close(self) -> None:
        """Close the storage backend."""
        pass


class FileAuditStorage(AuditLogStorage):
    """File-based audit log storage."""
    
    def __init__(self, path: Union[str, Path]) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._last_hash: Optional[str] = None
        self._file: Optional[TextIO] = None
        
        self._ensure_file()
        self._load_last_hash()
    
    def _ensure_file(self) -> None:
        """Ensure the log file exists."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()
    
    def _load_last_hash(self) -> None:
        """Load the last hash from the file."""
        if self.path.stat().st_size == 0:
            return
        
        with open(self.path, "r") as f:
            last_line = None
            for line in f:
                if line.strip():
                    last_line = line
            
            if last_line:
                try:
                    event_data = json.loads(last_line)
                    self._last_hash = event_data.get("event_hash")
                except json.JSONDecodeError:
                    pass
    
    def write(self, event: AuditEvent) -> None:
        """Write an event to the log file."""
        with self._lock:
            with open(self.path, "a") as f:
                f.write(json.dumps(event.to_dict(), separators=(",", ":")))
                f.write("\n")
                f.flush()
            self._last_hash = event.event_hash
    
    def read(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[AuditEventType]] = None,
        actor_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[AuditEvent]:
        """Read events from the log file with filters."""
        events = []
        
        with open(self.path, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                
                try:
                    event_data = json.loads(line)
                    event = AuditEvent.from_dict(event_data)
                    
                    if start_time and event.timestamp < start_time:
                        continue
                    if end_time and event.timestamp > end_time:
                        continue
                    if event_types and event.event_type not in event_types:
                        continue
                    if actor_id and event.actor_id != actor_id:
                        continue
                    if tenant_id and event.tenant_id != tenant_id:
                        continue
                    
                    events.append(event)
                    
                    if len(events) >= limit:
                        break
                        
                except json.JSONDecodeError:
                    continue
        
        return events
    
    def get_last_hash(self) -> Optional[str]:
        """Get the hash of the last event."""
        return self._last_hash


class MemoryAuditStorage(AuditLogStorage):
    """In-memory audit log storage for testing."""
    
    def __init__(self, max_events: int = 10000) -> None:
        self._events: List[AuditEvent] = []
        self._max_events = max_events
        self._lock = threading.Lock()
    
    def write(self, event: AuditEvent) -> None:
        """Write an event to memory."""
        with self._lock:
            self._events.append(event)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]
    
    def read(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[AuditEventType]] = None,
        actor_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[AuditEvent]:
        """Read events from memory with filters."""
        with self._lock:
            events = []
            for event in self._events:
                if start_time and event.timestamp < start_time:
                    continue
                if end_time and event.timestamp > end_time:
                    continue
                if event_types and event.event_type not in event_types:
                    continue
                if actor_id and event.actor_id != actor_id:
                    continue
                if tenant_id and event.tenant_id != tenant_id:
                    continue
                
                events.append(event)
                
                if len(events) >= limit:
                    break
            
            return events
    
    def get_last_hash(self) -> Optional[str]:
        """Get the hash of the last event."""
        with self._lock:
            if self._events:
                return self._events[-1].event_hash
            return None
    
    def clear(self) -> None:
        """Clear all events."""
        with self._lock:
            self._events.clear()


class AuditLogger:
    """
    Audit logger with tamper-evident hash chaining.
    
    Features:
    - Hash chaining for tamper detection
    - Optional HMAC for authentication
    - Multiple storage backends
    - Event filtering and querying
    
    Example:
        logger = AuditLogger(storage=FileAuditStorage("audit.log"))
        logger.log(
            event_type=AuditEventType.KEY_CREATED,
            actor_id="user-123",
            resource_type="key",
            resource_id="key-456",
            action="create",
            outcome="success",
        )
    """
    
    def __init__(
        self,
        storage: Optional[AuditLogStorage] = None,
        hmac_key: Optional[bytes] = None,
        default_severity: AuditSeverity = AuditSeverity.INFO,
        event_handlers: Optional[List[Callable[[AuditEvent], None]]] = None,
    ) -> None:
        """
        Initialize the audit logger.
        
        Args:
            storage: Storage backend (defaults to memory)
            hmac_key: Optional HMAC key for hash authentication
            default_severity: Default severity for events
            event_handlers: Optional handlers called for each event
        """
        self._storage = storage or MemoryAuditStorage()
        self._hmac_key = hmac_key
        self._default_severity = default_severity
        self._event_handlers = event_handlers or []
        self._lock = threading.Lock()
    
    def log(
        self,
        event_type: AuditEventType,
        action: str,
        outcome: str,
        actor_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: Optional[AuditSeverity] = None,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> AuditEvent:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event
            action: Action performed
            outcome: Outcome (success, failure, etc.)
            actor_id: ID of the actor performing the action
            tenant_id: Tenant context
            resource_type: Type of resource affected
            resource_id: ID of resource affected
            details: Additional event details
            severity: Event severity
            source_ip: Source IP address
            user_agent: User agent string
            request_id: Request correlation ID
            session_id: Session ID
            
        Returns:
            The created audit event
        """
        with self._lock:
            previous_hash = self._storage.get_last_hash()
            
            event = AuditEvent(
                event_type=event_type,
                timestamp=datetime.now(timezone.utc),
                event_id=str(uuid.uuid4()),
                severity=severity or self._default_severity,
                actor_id=actor_id,
                tenant_id=tenant_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                outcome=outcome,
                details=details or {},
                source_ip=source_ip,
                user_agent=user_agent,
                request_id=request_id,
                session_id=session_id,
                previous_hash=previous_hash,
                event_hash=None,
            )
            
            event.event_hash = event.compute_hash(self._hmac_key)
            
            self._storage.write(event)
            
            for handler in self._event_handlers:
                try:
                    handler(event)
                except Exception:
                    pass
            
            return event
    
    def log_auth_success(
        self,
        actor_id: str,
        **kwargs: Any,
    ) -> AuditEvent:
        """Log successful authentication."""
        return self.log(
            event_type=AuditEventType.AUTH_LOGIN,
            action="login",
            outcome="success",
            actor_id=actor_id,
            **kwargs,
        )
    
    def log_auth_failure(
        self,
        actor_id: Optional[str] = None,
        reason: str = "unknown",
        **kwargs: Any,
    ) -> AuditEvent:
        """Log failed authentication."""
        return self.log(
            event_type=AuditEventType.AUTH_FAILED,
            action="login",
            outcome="failure",
            actor_id=actor_id,
            severity=AuditSeverity.WARNING,
            details={"reason": reason},
            **kwargs,
        )
    
    def log_authz_denied(
        self,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        permission: str,
        **kwargs: Any,
    ) -> AuditEvent:
        """Log authorization denial."""
        return self.log(
            event_type=AuditEventType.AUTHZ_DENIED,
            action=permission,
            outcome="denied",
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            severity=AuditSeverity.WARNING,
            **kwargs,
        )
    
    def log_key_operation(
        self,
        operation: str,
        key_id: str,
        actor_id: str,
        success: bool = True,
        **kwargs: Any,
    ) -> AuditEvent:
        """Log a key management operation."""
        event_map = {
            "create": AuditEventType.KEY_CREATED,
            "rotate": AuditEventType.KEY_ROTATED,
            "delete": AuditEventType.KEY_DELETED,
            "export": AuditEventType.KEY_EXPORTED,
            "import": AuditEventType.KEY_IMPORTED,
            "access": AuditEventType.KEY_ACCESSED,
        }
        return self.log(
            event_type=event_map.get(operation, AuditEventType.KEY_ACCESSED),
            action=operation,
            outcome="success" if success else "failure",
            actor_id=actor_id,
            resource_type="key",
            resource_id=key_id,
            **kwargs,
        )
    
    def log_crypto_operation(
        self,
        operation: str,
        actor_id: str,
        key_id: Optional[str] = None,
        success: bool = True,
        **kwargs: Any,
    ) -> AuditEvent:
        """Log a cryptographic operation."""
        event_map = {
            "encrypt": AuditEventType.CRYPTO_ENCRYPT,
            "decrypt": AuditEventType.CRYPTO_DECRYPT,
            "sign": AuditEventType.CRYPTO_SIGN,
            "verify": AuditEventType.CRYPTO_VERIFY,
            "encapsulate": AuditEventType.CRYPTO_KEM_ENCAPSULATE,
            "decapsulate": AuditEventType.CRYPTO_KEM_DECAPSULATE,
        }
        return self.log(
            event_type=event_map.get(operation, AuditEventType.CRYPTO_ENCRYPT),
            action=operation,
            outcome="success" if success else "failure",
            actor_id=actor_id,
            resource_type="key" if key_id else None,
            resource_id=key_id,
            **kwargs,
        )
    
    def log_compliance_violation(
        self,
        violation_type: str,
        description: str,
        actor_id: Optional[str] = None,
        **kwargs: Any,
    ) -> AuditEvent:
        """Log a compliance violation."""
        return self.log(
            event_type=AuditEventType.COMPLIANCE_VIOLATION,
            action=violation_type,
            outcome="violation",
            actor_id=actor_id,
            severity=AuditSeverity.ERROR,
            details={"description": description},
            **kwargs,
        )
    
    def query(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[AuditEventType]] = None,
        actor_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 1000,
    ) -> List[AuditEvent]:
        """Query audit events."""
        return self._storage.read(
            start_time=start_time,
            end_time=end_time,
            event_types=event_types,
            actor_id=actor_id,
            tenant_id=tenant_id,
            limit=limit,
        )
    
    def verify_chain(
        self,
        events: Optional[List[AuditEvent]] = None,
    ) -> bool:
        """
        Verify the hash chain integrity.
        
        Args:
            events: Events to verify (reads all if not provided)
            
        Returns:
            True if chain is valid, False if tampered
        """
        if events is None:
            events = self._storage.read(limit=1000000)
        
        if not events:
            return True
        
        for i, event in enumerate(events):
            expected_hash = event.compute_hash(self._hmac_key)
            if event.event_hash != expected_hash:
                return False
            
            if i > 0:
                if event.previous_hash != events[i - 1].event_hash:
                    return False
        
        return True
    
    def close(self) -> None:
        """Close the audit logger."""
        self._storage.close()

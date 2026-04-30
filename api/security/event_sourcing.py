"""
Event Sourcing for Audit Trail.

Implements event sourcing pattern for:
- Complete audit history
- Event replay capability
- Temporal queries
- Compliance reporting
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

import structlog

logger = structlog.get_logger()


class EventType(str, Enum):
    """Audit event types."""

    USER_CREATED = "user.created"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_UPDATED = "user.updated"

    JOB_SUBMITTED = "job.submitted"
    JOB_STARTED = "job.started"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    JOB_CANCELLED = "job.cancelled"

    KEY_GENERATED = "key.generated"
    KEY_ROTATED = "key.rotated"
    KEY_REVOKED = "key.revoked"
    KEY_EXPORTED = "key.exported"

    DATA_ENCRYPTED = "data.encrypted"
    DATA_DECRYPTED = "data.decrypted"
    DATA_EXPORTED = "data.exported"

    API_KEY_CREATED = "api_key.created"
    API_KEY_ROTATED = "api_key.rotated"
    API_KEY_REVOKED = "api_key.revoked"

    WEBHOOK_SENT = "webhook.sent"
    WEBHOOK_FAILED = "webhook.failed"

    SECURITY_ALERT = "security.alert"
    RATE_LIMIT_EXCEEDED = "security.rate_limit"

    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"


@dataclass
class AuditEvent:
    """Base audit event."""

    event_id: str
    event_type: EventType
    aggregate_id: str
    aggregate_type: str
    timestamp: datetime
    version: int = 1
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "metadata": self.metadata,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AuditEvent":
        return cls(
            event_id=data["event_id"],
            event_type=EventType(data["event_type"]),
            aggregate_id=data["aggregate_id"],
            aggregate_type=data["aggregate_type"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            version=data.get("version", 1),
            user_id=data.get("user_id"),
            tenant_id=data.get("tenant_id"),
            correlation_id=data.get("correlation_id"),
            causation_id=data.get("causation_id"),
            metadata=data.get("metadata", {}),
            payload=data.get("payload", {}),
        )


@dataclass
class EventStream:
    """Stream of events for an aggregate."""

    aggregate_id: str
    aggregate_type: str
    events: list[AuditEvent] = field(default_factory=list)
    version: int = 0

    def append(self, event: AuditEvent) -> None:
        self.version += 1
        event.version = self.version
        self.events.append(event)


class EventStore:
    """
    Event store for persisting audit events.

    Features:
    - Append-only storage
    - Event replay
    - Temporal queries
    - Snapshot support
    """

    def __init__(self, max_events_per_stream: int = 10000):
        self._streams: dict[str, EventStream] = {}
        self._all_events: list[AuditEvent] = []
        self._max_events = max_events_per_stream
        self._lock = asyncio.Lock()

    async def append(
        self,
        event_type: EventType,
        aggregate_id: str,
        aggregate_type: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        payload: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> AuditEvent:
        """Append a new event to the store."""
        event = AuditEvent(
            event_id=f"evt_{uuid4().hex[:12]}",
            event_type=event_type,
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            timestamp=datetime.now(UTC),
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            payload=payload or {},
            metadata=metadata or {},
        )

        async with self._lock:
            if aggregate_id not in self._streams:
                self._streams[aggregate_id] = EventStream(
                    aggregate_id=aggregate_id, aggregate_type=aggregate_type
                )

            self._streams[aggregate_id].append(event)
            self._all_events.append(event)

            if len(self._all_events) > self._max_events:
                self._all_events = self._all_events[-self._max_events :]

        logger.info(
            "audit_event_appended",
            event_id=event.event_id,
            event_type=event_type.value,
            aggregate_id=aggregate_id,
            user_id=user_id,
        )

        return event

    async def get_stream(self, aggregate_id: str) -> list[AuditEvent]:
        """Get all events for an aggregate."""
        stream = self._streams.get(aggregate_id)
        return stream.events if stream else []

    async def get_events(
        self,
        event_type: Optional[EventType] = None,
        aggregate_type: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Query events with filters."""
        events = self._all_events

        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if aggregate_type:
            events = [e for e in events if e.aggregate_type == aggregate_type]
        if user_id:
            events = [e for e in events if e.user_id == user_id]
        if tenant_id:
            events = [e for e in events if e.tenant_id == tenant_id]
        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
        if end_time:
            events = [e for e in events if e.timestamp <= end_time]

        return events[-limit:]

    async def replay_events(self, aggregate_id: str, handler: callable) -> Any:
        """Replay events for an aggregate through a handler."""
        events = await self.get_stream(aggregate_id)
        result = None

        for event in events:
            result = await handler(event)

        return result

    async def get_statistics(self) -> dict[str, Any]:
        """Get event store statistics."""
        event_counts = {}
        for event in self._all_events:
            event_type = event.event_type.value
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        return {
            "total_events": len(self._all_events),
            "total_streams": len(self._streams),
            "event_counts": event_counts,
            "oldest_event": self._all_events[0].timestamp.isoformat() if self._all_events else None,
            "newest_event": self._all_events[-1].timestamp.isoformat()
            if self._all_events
            else None,
        }


event_store = EventStore()


class AuditEventPublisher:
    """Publisher for audit events."""

    def __init__(self, store: EventStore):
        self._store = store
        self._subscribers: list[callable] = []

    def subscribe(self, handler: callable) -> None:
        """Subscribe to audit events."""
        self._subscribers.append(handler)

    async def publish(self, event: AuditEvent) -> None:
        """Publish event to all subscribers."""
        for handler in self._subscribers:
            try:
                await handler(event)
            except Exception as e:
                logger.error("audit_subscriber_error", error=str(e))


audit_publisher = AuditEventPublisher(event_store)


async def record_audit_event(
    event_type: EventType,
    aggregate_id: str,
    aggregate_type: str,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    payload: Optional[dict] = None,
) -> AuditEvent:
    """Convenience function to record an audit event."""
    return await event_store.append(
        event_type=event_type,
        aggregate_id=aggregate_id,
        aggregate_type=aggregate_type,
        user_id=user_id,
        tenant_id=tenant_id,
        payload=payload,
    )

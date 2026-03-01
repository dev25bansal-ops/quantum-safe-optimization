"""
Event bus port definition.

Defines the protocol for publishing and subscribing to domain events.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID, uuid4


@dataclass(frozen=True)
class DomainEvent:
    """
    Base class for domain events.

    Attributes:
        event_id: Unique event identifier.
        event_type: Type of the event.
        timestamp: When the event occurred.
        payload: Event-specific data.
        metadata: Additional metadata.
    """

    event_id: UUID = field(default_factory=uuid4)
    event_type: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


EventHandler = Callable[[DomainEvent], Awaitable[None]]


@runtime_checkable
class EventBus(Protocol):
    """
    Protocol for domain event publishing and subscription.

    Provides a mechanism for loose coupling between components
    through event-driven communication.
    """

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        Subscribe to events of a specific type.

        Args:
            event_type: The type of events to subscribe to.
            handler: Async function to call when event occurs.
        """
        ...

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        Unsubscribe a handler from an event type.

        Args:
            event_type: The event type.
            handler: The handler to remove.
        """
        ...

    async def publish(self, event: DomainEvent) -> None:
        """
        Publish an event to all subscribers.

        Args:
            event: The event to publish.
        """
        ...

    async def publish_many(self, events: list[DomainEvent]) -> None:
        """
        Publish multiple events.

        Args:
            events: List of events to publish.
        """
        ...


# Common domain event types
class EventTypes:
    """Standard domain event types."""

    # Job lifecycle
    JOB_CREATED = "job.created"
    JOB_SUBMITTED = "job.submitted"
    JOB_STARTED = "job.started"
    JOB_PROGRESS = "job.progress"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    JOB_CANCELLED = "job.cancelled"

    # Optimization events
    ITERATION_STARTED = "optimization.iteration_started"
    ITERATION_COMPLETED = "optimization.iteration_completed"
    CONVERGENCE_REACHED = "optimization.convergence_reached"
    CHECKPOINT_CREATED = "optimization.checkpoint_created"

    # Quantum execution
    CIRCUIT_SUBMITTED = "quantum.circuit_submitted"
    CIRCUIT_COMPLETED = "quantum.circuit_completed"
    CIRCUIT_FAILED = "quantum.circuit_failed"

    # Cryptographic events
    KEY_GENERATED = "crypto.key_generated"
    KEY_ROTATED = "crypto.key_rotated"
    KEY_REVOKED = "crypto.key_revoked"
    ENCRYPTION_PERFORMED = "crypto.encryption_performed"
    DECRYPTION_PERFORMED = "crypto.decryption_performed"
    SIGNATURE_CREATED = "crypto.signature_created"
    SIGNATURE_VERIFIED = "crypto.signature_verified"

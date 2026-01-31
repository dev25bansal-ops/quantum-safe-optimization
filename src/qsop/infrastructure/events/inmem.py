"""
In-memory event bus for development and testing.

Not suitable for production - use Redis or other distributed solutions.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """An event in the system."""
    event_id: str
    event_type: str
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


EventHandler = Callable[[Event], Awaitable[None]]


class InMemoryEventBus:
    """
    In-memory event bus for development and testing.
    
    Provides pub/sub functionality within a single process.
    """
    
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._event_history: list[Event] = []
        self._max_history: int = 1000
    
    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        Subscribe to events of a specific type.
        
        Args:
            event_type: The type of events to subscribe to
            handler: Async function to call when event occurs
        """
        self._handlers[event_type].append(handler)
        logger.debug(f"Subscribed handler to {event_type}")
    
    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Unsubscribe a handler from an event type."""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
    
    async def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers.
        
        Args:
            event: The event to publish
        """
        self._record_event(event)
        
        handlers = self._handlers.get(event.event_type, [])
        # Also notify wildcard subscribers
        handlers.extend(self._handlers.get("*", []))
        
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(
                    f"Event handler error for {event.event_type}: {e}",
                    exc_info=True,
                )
    
    async def publish_many(self, events: list[Event]) -> None:
        """Publish multiple events."""
        for event in events:
            await self.publish(event)
    
    def create_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> Event:
        """Create a new event."""
        return Event(
            event_id=str(uuid4()),
            event_type=event_type,
            payload=payload,
            metadata=metadata or {},
        )
    
    def _record_event(self, event: Event) -> None:
        """Record event in history."""
        self._event_history.append(event)
        
        # Trim history if needed
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
    
    def get_history(
        self,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Get event history, optionally filtered by type."""
        events = self._event_history
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        return events[-limit:]
    
    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history.clear()
    
    def clear_handlers(self) -> None:
        """Clear all handlers."""
        self._handlers.clear()


# Common event types
class EventTypes:
    """Standard event types for the platform."""
    
    # Job events
    JOB_SUBMITTED = "job.submitted"
    JOB_STARTED = "job.started"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    JOB_CANCELLED = "job.cancelled"
    
    # Optimization events
    ITERATION_COMPLETED = "optimization.iteration_completed"
    CONVERGENCE_REACHED = "optimization.converged"
    
    # Quantum events
    CIRCUIT_EXECUTED = "quantum.circuit_executed"
    BACKEND_ERROR = "quantum.backend_error"
    
    # Crypto events
    KEY_CREATED = "crypto.key_created"
    KEY_ROTATED = "crypto.key_rotated"
    KEY_REVOKED = "crypto.key_revoked"
    
    # Security events
    AUTH_SUCCESS = "security.auth_success"
    AUTH_FAILURE = "security.auth_failure"
    POLICY_VIOLATION = "security.policy_violation"

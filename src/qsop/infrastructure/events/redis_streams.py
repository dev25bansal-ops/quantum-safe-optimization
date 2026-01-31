"""
Redis Streams-based event bus for production.

Provides distributed pub/sub with persistence.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
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
    timestamp: datetime
    metadata: dict[str, Any]


EventHandler = Callable[[Event], Awaitable[None]]


class RedisEventBus:
    """
    Redis Streams-based event bus for production.
    
    Uses Redis Streams for reliable, distributed event handling
    with consumer groups for load balancing.
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        stream_prefix: str = "qsop:events:",
        consumer_group: str = "qsop-workers",
        consumer_name: str | None = None,
    ):
        self.redis_url = redis_url
        self.stream_prefix = stream_prefix
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name or f"consumer-{uuid4().hex[:8]}"
        
        self._client: Any = None
        self._handlers: dict[str, list[EventHandler]] = {}
        self._running = False
        self._consumer_task: asyncio.Task | None = None
    
    async def connect(self) -> None:
        """Connect to Redis."""
        try:
            import redis.asyncio as redis
            self._client = redis.from_url(self.redis_url)
            await self._client.ping()
            logger.info(f"Connected to Redis at {self.redis_url}")
        except ImportError:
            raise RuntimeError("redis package required: pip install redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        self._running = False
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
        
        if self._client:
            await self._client.close()
            self._client = None
    
    def _stream_name(self, event_type: str) -> str:
        """Get Redis stream name for event type."""
        return f"{self.stream_prefix}{event_type}"
    
    async def _ensure_consumer_group(self, stream: str) -> None:
        """Ensure consumer group exists for stream."""
        try:
            await self._client.xgroup_create(
                stream,
                self.consumer_group,
                id="0",
                mkstream=True,
            )
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                raise
    
    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe to events of a specific type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"Subscribed handler to {event_type}")
    
    async def publish(self, event: Event) -> str:
        """
        Publish an event to Redis Stream.
        
        Returns:
            The Redis message ID
        """
        if self._client is None:
            raise RuntimeError("Not connected to Redis")
        
        stream = self._stream_name(event.event_type)
        
        message = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "payload": json.dumps(event.payload),
            "timestamp": event.timestamp.isoformat(),
            "metadata": json.dumps(event.metadata),
        }
        
        message_id = await self._client.xadd(stream, message)
        logger.debug(f"Published event {event.event_id} to {stream}")
        
        return message_id
    
    async def start_consuming(self) -> None:
        """Start consuming events from subscribed streams."""
        if not self._handlers:
            logger.warning("No handlers registered, nothing to consume")
            return
        
        self._running = True
        self._consumer_task = asyncio.create_task(self._consume_loop())
    
    async def _consume_loop(self) -> None:
        """Main consumption loop."""
        streams = {
            self._stream_name(et): ">"
            for et in self._handlers
        }
        
        # Ensure consumer groups exist
        for stream in streams:
            await self._ensure_consumer_group(stream)
        
        while self._running:
            try:
                messages = await self._client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    streams,
                    count=10,
                    block=1000,  # 1 second
                )
                
                for stream, stream_messages in messages:
                    for message_id, data in stream_messages:
                        await self._process_message(stream, message_id, data)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error consuming events: {e}")
                await asyncio.sleep(1)
    
    async def _process_message(
        self,
        stream: str,
        message_id: str,
        data: dict,
    ) -> None:
        """Process a single message from Redis."""
        try:
            event = Event(
                event_id=data[b"event_id"].decode(),
                event_type=data[b"event_type"].decode(),
                payload=json.loads(data[b"payload"]),
                timestamp=datetime.fromisoformat(data[b"timestamp"].decode()),
                metadata=json.loads(data[b"metadata"]),
            )
            
            handlers = self._handlers.get(event.event_type, [])
            
            for handler in handlers:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Handler error for {event.event_type}: {e}")
            
            # Acknowledge the message
            await self._client.xack(stream, self.consumer_group, message_id)
            
        except Exception as e:
            logger.error(f"Error processing message {message_id}: {e}")
    
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
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {},
        )

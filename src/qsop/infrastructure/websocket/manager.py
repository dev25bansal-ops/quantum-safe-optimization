"""
WebSocket manager for real-time job status updates.

Provides live updates via WebSocket connections for:
- Job progress updates
- Status changes
- Completion notifications
- Error alerts
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect

from qsop.api.schemas.job import JobProgress, JobStatus


class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates.

    Features:
    - Broadcast to all clients
    - Send to specific client
    - Send to specific subscribers (e.g., by job_id)
    - Connection lifecycle management
    """

    def __init__(self):
        self._active_connections: dict[str, WebSocket] = {}
        self._job_subscribers: dict[UUID, set[str]] = {}
        self._tenant_subscribers: dict[str, set[str]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        client_id: str,
        tenant_id: str | None = None,
    ) -> None:
        """Accept a WebSocket connection and register client."""
        await websocket.accept()
        self._active_connections[client_id] = websocket

        if tenant_id:
            if tenant_id not in self._tenant_subscribers:
                self._tenant_subscribers[tenant_id] = set()
            self._tenant_subscribers[tenant_id].add(client_id)

    async def disconnect(self, client_id: str) -> None:
        """Remove disconnected client from all subscriptions."""
        if client_id in self._active_connections:
            del self._active_connections[client_id]

        # Remove from job subscriptions
        for job_id in list(self._job_subscribers.keys()):
            if client_id in self._job_subscribers[job_id]:
                self._job_subscribers[job_id].remove(client_id)
                if not self._job_subscribers[job_id]:
                    del self._job_subscribers[job_id]

        # Remove from tenant subscriptions
        for tenant_id in list(self._tenant_subscribers.keys()):
            if client_id in self._tenant_subscribers[tenant_id]:
                self._tenant_subscribers[tenant_id].remove(client_id)
                if not self._tenant_subscribers[tenant_id]:
                    del self._tenant_subscribers[tenant_id]

    def subscribe_to_job(self, client_id: str, job_id: UUID) -> None:
        """Subscribe a client to updates for a specific job."""
        if job_id not in self._job_subscribers:
            self._job_subscribers[job_id] = set()
        self._job_subscribers[job_id].add(client_id)

    def unsubscribe_from_job(self, client_id: str, job_id: UUID) -> None:
        """Unsubscribe a client from job updates."""
        if job_id in self._job_subscribers:
            self._job_subscribers[job_id].discard(client_id)
            if not self._job_subscribers[job_id]:
                del self._job_subscribers[job_id]

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast message to all connected clients."""
        disconnected = []
        for client_id, connection in self._active_connections.items():
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(client_id)

        for client_id in disconnected:
            await self.disconnect(client_id)

    async def send_to_client(self, client_id: str, message: dict[str, Any]) -> bool:
        """Send message to a specific client."""
        if client_id in self._active_connections:
            try:
                await self._active_connections[client_id].send_json(message)
                return True
            except Exception:
                await self.disconnect(client_id)
        return False

    async def send_to_job_subscribers(self, job_id: UUID, message: dict[str, Any]) -> int:
        """Send message to all clients subscribed to a job."""
        if job_id not in self._job_subscribers:
            return 0

        count = 0
        for client_id in list(self._job_subscribers[job_id]):
            if await self.send_to_client(client_id, message):
                count += 1

        return count

    async def send_to_tenant_subscribers(self, tenant_id: str, message: dict[str, Any]) -> int:
        """Send message to all clients belonging to a tenant."""
        if tenant_id not in self._tenant_subscribers:
            return 0

        count = 0
        for client_id in list(self._tenant_subscribers[tenant_id]):
            if await self.send_to_client(client_id, message):
                count += 1

        return count

    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return len(self._active_connections)

    def get_job_subscriber_count(self, job_id: UUID) -> int:
        """Get number of subscribers for a specific job."""
        return len(self._job_subscribers.get(job_id, set()))


class JobUpdateBroadcaster:
    """
    Broadcasts job-related updates via WebSocket.

    Provides structured update methods for different job events:
    - Status changes
    - Progress updates
    - Completion
    - Errors
    """

    def __init__(self, connection_manager: ConnectionManager):
        self._manager = connection_manager

    async def broadcast_status_change(
        self,
        job_id: UUID,
        old_status: JobStatus,
        new_status: JobStatus,
        tenant_id: str,
    ) -> None:
        """Broadcast job status change to subscribers."""
        message = {
            "type": "job_status_change",
            "job_id": str(job_id),
            "old_status": old_status.value,
            "new_status": new_status.value,
            "tenant_id": tenant_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._manager.send_to_job_subscribers(job_id, message)

    async def broadcast_progress(
        self,
        job_id: UUID,
        progress: JobProgress,
    ) -> None:
        """Broadcast job progress update."""
        message = {
            "type": "job_progress",
            "job_id": str(job_id),
            "status": progress.status.value,
            "progress": progress.progress,
            "message": progress.message,
            "current_iteration": progress.current_iteration,
            "total_iterations": progress.total_iterations,
            "timestamp": progress.timestamp.isoformat(),
        }
        await self._manager.send_to_job_subscribers(job_id, message)

    async def broadcast_completion(
        self,
        job_id: UUID,
        result: dict[str, Any],
        tenant_id: str,
    ) -> None:
        """Broadcast job completion with results."""
        message = {
            "type": "job_completed",
            "job_id": str(job_id),
            "tenant_id": tenant_id,
            "result": result,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._manager.send_to_job_subscribers(job_id, message)

    async def broadcast_error(
        self,
        job_id: UUID,
        error_message: str,
        tenant_id: str,
        error_details: dict[str, Any] | None = None,
    ) -> None:
        """Broadcast job error."""
        message = {
            "type": "job_error",
            "job_id": str(job_id),
            "tenant_id": tenant_id,
            "error_message": error_message,
            "error_details": error_details,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._manager.send_to_job_subscribers(job_id, message)

    async def broadcast_cancellation(
        self,
        job_id: UUID,
        tenant_id: str,
    ) -> None:
        """Broadcast job cancellation."""
        message = {
            "type": "job_cancelled",
            "job_id": str(job_id),
            "tenant_id": tenant_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._manager.send_to_job_subscribers(job_id, message)


class WebSocketMessageHandler:
    """
    Handles incoming WebSocket messages from clients.

    Supported message types:
    - subscribe_job: Subscribe to job updates
    - unsubscribe_job: Unsubscribe from job updates
    - ping: Keep-alive check
    - get_status: Request current status
    """

    def __init__(
        self,
        connection_manager: ConnectionManager,
        broadcaster: JobUpdateBroadcaster,
    ):
        self._manager = connection_manager
        self._broadcaster = broadcaster

    async def handle_message(
        self, client_id: str, message: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Handle incoming WebSocket message.

        Args:
            client_id: Sending client's ID
            message: Message payload

        Returns:
            Optional response message
        """
        message_type = message.get("type")

        if message_type == "subscribe_job":
            job_id = UUID(message["job_id"])
            self._manager.subscribe_to_job(client_id, job_id)
            return {
                "type": "subscribed",
                "job_id": str(job_id),
                "timestamp": datetime.utcnow().isoformat(),
            }

        elif message_type == "unsubscribe_job":
            job_id = UUID(message["job_id"])
            self._manager.unsubscribe_from_job(client_id, job_id)
            return {
                "type": "unsubscribed",
                "job_id": str(job_id),
                "timestamp": datetime.utcnow().isoformat(),
            }

        elif message_type == "ping":
            return {
                "type": "pong",
                "timestamp": datetime.utcnow().isoformat(),
            }

        elif message_type == "get_status":
            return {
                "type": "status",
                "connected": True,
                "connections": self._manager.get_connection_count(),
                "timestamp": datetime.utcnow().isoformat(),
            }

        else:
            return {
                "type": "error",
                "error": f"Unknown message type: {message_type}",
                "timestamp": datetime.utcnow().isoformat(),
            }


async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
    tenant_id: str | None = None,
    connection_manager: ConnectionManager | None = None,
) -> None:
    """
    WebSocket endpoint handler for real-time updates.

    Example usage in FastAPI:
        @app.websocket("/ws/{client_id}")
        async def websocket_route(
            websocket: WebSocket,
            client_id: str,
            token: str = Query(...)
        ):
            tenant_id = await verify_token(token)
            await websocket_endpoint(websocket, client_id, tenant_id, manager)
    """
    if connection_manager is None:
        from qsop.infrastructure.websocket.manager import get_connection_manager

        connection_manager = get_connection_manager()

    broadcaster = JobUpdateBroadcaster(connection_manager)
    handler = WebSocketMessageHandler(connection_manager, broadcaster)

    await connection_manager.connect(websocket, client_id, tenant_id)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                response = await handler.handle_message(client_id, message)
                if response:
                    await websocket.send_json(response)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {
                        "type": "error",
                        "error": "Invalid JSON message",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

    except WebSocketDisconnect:
        await connection_manager.disconnect(client_id)

    except Exception:
        await connection_manager.disconnect(client_id)


class EventPublisher:
    """
    Publishes service events to WebSocket subscribers.

    Integrates with the event bus to broadcast important events
    to connected clients.
    """

    def __init__(
        self,
        connection_manager: ConnectionManager,
        broadcaster: JobUpdateBroadcaster,
    ):
        self._manager = connection_manager
        self._broadcaster = broadcaster
        self._subscribers: dict[str, set[Callable]] = {}

    async def publish_job_created(
        self,
        job_id: UUID,
        tenant_id: str,
        algorithm: str,
    ) -> None:
        """Publish job created event."""
        message = {
            "type": "job_created",
            "job_id": str(job_id),
            "tenant_id": tenant_id,
            "algorithm": algorithm,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._manager.send_to_tenant_subscribers(tenant_id, message)

    async def publish_backend_status_update(
        self,
        backend_id: str,
        status: str,
        queue_depth: int,
    ) -> None:
        """Publish backend status update."""
        message = {
            "type": "backend_status",
            "backend_id": backend_id,
            "status": status,
            "queue_depth": queue_depth,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._manager.broadcast(message)

    async def publish_system_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Publish system-wide alert."""
        message = {
            "type": "system_alert",
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "metadata": metadata,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._manager.broadcast(message)

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """Subscribe to specific event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = set()
        self._subscribers[event_type].add(callback)

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Unsubscribe from event type."""
        if event_type in self._subscribers:
            self._subscribers[event_type].discard(callback)


_global_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    """Get global connection manager singleton."""
    global _global_manager
    if _global_manager is None:
        _global_manager = ConnectionManager()
    return _global_manager


def get_broadcaster() -> JobUpdateBroadcaster:
    """Get global job update broadcaster."""
    manager = get_connection_manager()
    return JobUpdateBroadcaster(manager)


def get_event_publisher() -> EventPublisher:
    """Get global event publisher."""
    manager = get_connection_manager()
    broadcaster = JobUpdateBroadcaster(manager)
    return EventPublisher(manager, broadcaster)


__all__ = [
    "ConnectionManager",
    "JobUpdateBroadcaster",
    "WebSocketMessageHandler",
    "EventPublisher",
    "websocket_endpoint",
    "get_connection_manager",
    "get_broadcaster",
    "get_event_publisher",
]

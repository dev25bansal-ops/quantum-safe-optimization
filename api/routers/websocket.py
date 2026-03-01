"""
WebSocket endpoint for real-time job progress updates.

Streams job progress from Redis pub/sub to connected clients.
Features:
- Connection health monitoring
- Automatic reconnection support
- Heartbeat/keepalive mechanism
- Metrics integration
"""

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

router = APIRouter()

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# WebSocket configuration
WS_HEARTBEAT_INTERVAL = int(os.getenv("WS_HEARTBEAT_INTERVAL", "30"))
WS_MAX_MESSAGE_SIZE = int(os.getenv("WS_MAX_MESSAGE_SIZE", "65536"))


class ConnectionState(str, Enum):
    """WebSocket connection states."""

    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""

    websocket: WebSocket
    job_id: str
    user_id: str | None = None
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    messages_sent: int = 0
    messages_received: int = 0
    state: ConnectionState = ConnectionState.CONNECTED

    def __hash__(self):
        """Make hashable using websocket object identity."""
        return id(self.websocket)

    def __eq__(self, other):
        """Equality based on websocket identity."""
        if not isinstance(other, ConnectionInfo):
            return False
        return id(self.websocket) == id(other.websocket)

    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for status reporting."""
        return {
            "job_id": self.job_id,
            "user_id": self.user_id,
            "connected_at": self.connected_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "state": self.state.value,
            "uptime_seconds": (datetime.utcnow() - self.connected_at).total_seconds(),
        }


class ConnectionManager:
    """
    Manages WebSocket connections for job updates.

    Supports:
    - Multiple connections per job
    - Redis pub/sub for distributed updates
    - Connection health monitoring
    - Automatic cleanup on disconnect
    - Metrics collection
    """

    def __init__(self):
        # Map of job_id -> set of ConnectionInfo
        self.active_connections: dict[str, set[ConnectionInfo]] = {}
        self._redis: aioredis.Redis | None = None
        self._pubsub: aioredis.client.PubSub | None = None
        self._listener_task: asyncio.Task | None = None
        self._health_check_task: asyncio.Task | None = None

        # Connection statistics
        self._total_connections: int = 0
        self._total_messages_sent: int = 0
        self._total_messages_received: int = 0
        self._connection_errors: int = 0

    async def initialize(self):
        """Initialize Redis connection for pub/sub."""
        try:
            self._redis = aioredis.from_url(REDIS_URL, decode_responses=True)
            await self._redis.ping()
            self._pubsub = self._redis.pubsub()

            # Start health check task
            self._health_check_task = asyncio.create_task(self._health_check_loop())

        except Exception:  # noqa: BLE001 - Non-critical exception
            self._redis = None

    async def close(self):
        """Close Redis connections and cleanup."""
        # Cancel tasks
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        # Close all WebSocket connections gracefully
        for _job_id, connections in list(self.active_connections.items()):
            for conn_info in list(connections):
                try:
                    await conn_info.websocket.close(code=1001, reason="Server shutdown")
except Exception:  # noqa: BLE001 - Connection cleanup is non-critical
                    pass

        self.active_connections.clear()

        if self._pubsub:
            await self._pubsub.close()

        if self._redis:
            await self._redis.close()

    async def connect(
        self,
        websocket: WebSocket,
        job_id: str,
        user_id: str | None = None,
    ) -> ConnectionInfo:
        """Accept WebSocket connection and subscribe to job updates."""
        await websocket.accept()

        # Create connection info
        conn_info = ConnectionInfo(
            websocket=websocket,
            job_id=job_id,
            user_id=user_id,
        )

        if job_id not in self.active_connections:
            self.active_connections[job_id] = set()
            # Subscribe to Redis channel for this job
            if self._pubsub:
                await self._pubsub.subscribe(f"job:{job_id}:progress")

        self.active_connections[job_id].add(conn_info)
        self._total_connections += 1

        # Record metrics
        try:
            from api.routers.metrics import metrics

            metrics.record_ws_connection(connected=True)
        except ImportError:
            pass

        # Send current job state if available
        if self._redis:
            state = await self._redis.hgetall(f"job:{job_id}:state")
            if state:
                await self.send_to_connection(
                    conn_info,
                    {
                        "type": "state",
                        "data": state,
                    },
                )

        # Start listener if not running
        if self._listener_task is None or self._listener_task.done():
            self._listener_task = asyncio.create_task(self._listen_for_updates())

        return conn_info

    def disconnect(self, conn_info: ConnectionInfo):
        """Remove WebSocket connection."""
        job_id = conn_info.job_id
        conn_info.state = ConnectionState.DISCONNECTED

        if job_id in self.active_connections:
            self.active_connections[job_id].discard(conn_info)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]
                # Unsubscribe from Redis channel
                if self._pubsub:
                    asyncio.create_task(self._pubsub.unsubscribe(f"job:{job_id}:progress"))

        # Record metrics
        try:
            from api.routers.metrics import metrics

            metrics.record_ws_connection(connected=False)
        except ImportError:
            pass

    async def send_to_connection(
        self,
        conn_info: ConnectionInfo,
        message: dict[str, Any],
    ) -> bool:
        """Send message to specific connection."""
        if conn_info.websocket.client_state != WebSocketState.CONNECTED:
            return False

        try:
            await conn_info.websocket.send_json(message)
            conn_info.messages_sent += 1
            conn_info.update_activity()
            self._total_messages_sent += 1

            # Record metrics
            try:
                from api.routers.metrics import metrics

                metrics.record_ws_message(sent=True)
            except ImportError:
                pass

            return True
        except Exception:  # noqa: BLE001 - Non-critical exception
            self._connection_errors += 1
            return False

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to specific WebSocket (legacy compatibility)."""
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.send_json(message)
                self._total_messages_sent += 1
            except Exception:  # noqa: BLE001 - Non-critical exception
                self._connection_errors += 1

    async def broadcast_to_job(self, job_id: str, message: dict):
        """Broadcast message to all connections watching a job."""
        if job_id not in self.active_connections:
            return

        disconnected = []
        for conn_info in self.active_connections[job_id]:
            success = await self.send_to_connection(conn_info, message)
            if not success:
                disconnected.append(conn_info)

        # Clean up disconnected clients
        for conn_info in disconnected:
            self.active_connections[job_id].discard(conn_info)

    async def _health_check_loop(self):
        """Periodically check connection health and send pings."""
        while True:
            try:
                await asyncio.sleep(WS_HEARTBEAT_INTERVAL)

                # Check all connections
                for _job_id, connections in list(self.active_connections.items()):
                    stale_connections = []

                    for conn_info in connections:
                        # Check if connection is stale (no activity in 2x heartbeat interval)
                        idle_time = (datetime.utcnow() - conn_info.last_activity).total_seconds()

                        if idle_time > WS_HEARTBEAT_INTERVAL * 3:
                            stale_connections.append(conn_info)
                            continue

                        # Send ping
                        try:
                            if conn_info.websocket.client_state == WebSocketState.CONNECTED:
                                await conn_info.websocket.send_json(
                                    {
                                        "type": "ping",
                                        "timestamp": datetime.utcnow().isoformat(),
                                    }
                                )
                        except Exception:  # noqa: BLE001 - Non-critical exception
                            stale_connections.append(conn_info)

                    # Remove stale connections
                    for conn_info in stale_connections:
                        self.disconnect(conn_info)

            except asyncio.CancelledError:
                break
except Exception:  # noqa: BLE001 - Error sending is non-critical
                pass

    async def _listen_for_updates(self):
        """Background task to listen for Redis pub/sub messages."""
        if not self._pubsub:
            return

        try:
            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    channel = message["channel"]
                    # Extract job_id from channel name (job:{job_id}:progress)
                    parts = channel.split(":")
                    if len(parts) >= 2:
                        job_id = parts[1]
                        try:
                            data = json.loads(message["data"])
                            await self.broadcast_to_job(
                                job_id,
                                {
                                    "type": "progress",
                                    "data": data,
                                    "timestamp": datetime.utcnow().isoformat(),
                                },
                            )
                        except json.JSONDecodeError:
                            pass
        except asyncio.CancelledError:
            pass
except Exception:  # noqa: BLE001 - Heartbeat error is non-critical
            pass

    def get_status(self) -> dict[str, Any]:
        """Get WebSocket manager status."""
        connections_by_job = {}
        for job_id, connections in self.active_connections.items():
            connections_by_job[job_id] = [conn.to_dict() for conn in connections]

        return {
            "redis_connected": self._redis is not None,
            "total_connections": self._total_connections,
            "active_connections": sum(len(c) for c in self.active_connections.values()),
            "connections_by_job": len(self.active_connections),
            "total_messages_sent": self._total_messages_sent,
            "total_messages_received": self._total_messages_received,
            "connection_errors": self._connection_errors,
            "connections": connections_by_job,
        }


# Global connection manager
manager = ConnectionManager()
# Alias for backward compatibility with tests
connection_manager = manager


async def init_websocket_manager():
    """Initialize the WebSocket connection manager."""
    await manager.initialize()


async def close_websocket_manager():
    """Close the WebSocket connection manager."""
    await manager.close()


@router.get("/status")
async def websocket_status() -> dict[str, Any]:
    """
    Get WebSocket connection manager status.

    Returns information about active connections and statistics.
    """
    return manager.get_status()


@router.websocket("/jobs/{job_id}")
async def job_progress_websocket(
    websocket: WebSocket,
    job_id: str,
    user_id: str | None = Query(None, description="User ID for authorization"),
):
    """
    WebSocket endpoint for streaming job progress.

    Connect to receive real-time updates for a specific job.

    Messages sent by server:
    - {"type": "connected", "job_id": "..."} - Connection confirmed
    - {"type": "state", "data": {...}} - Current job state on connect
    - {"type": "progress", "data": {...}} - Progress updates
    - {"type": "ping", "timestamp": "..."} - Keepalive ping
    - {"type": "completed", "data": {...}} - Job completed
    - {"type": "error", "message": "..."} - Error occurred

    Messages accepted from client:
    - {"type": "pong"} - Response to ping
    - {"type": "ping"} - Client-initiated ping
    - {"type": "unsubscribe"} - Disconnect from this job
    """
    conn_info = await manager.connect(websocket, job_id, user_id)

    try:
        # Send initial connection confirmation
        await manager.send_to_connection(
            conn_info,
            {
                "type": "connected",
                "job_id": job_id,
                "timestamp": datetime.utcnow().isoformat(),
                "heartbeat_interval": WS_HEARTBEAT_INTERVAL,
            },
        )

        # Keep connection alive and handle client messages
        while True:
            try:
                # Wait for client messages with timeout
                data = await asyncio.wait_for(
                    websocket.receive_json(), timeout=float(WS_HEARTBEAT_INTERVAL * 2)
                )

                conn_info.messages_received += 1
                conn_info.update_activity()
                manager._total_messages_received += 1

                # Record metrics
                try:
                    from api.routers.metrics import metrics

                    metrics.record_ws_message(sent=False)
                except ImportError:
                    pass

                # Handle client commands
                msg_type = data.get("type", "")

                if msg_type == "ping":
                    await manager.send_to_connection(
                        conn_info,
                        {
                            "type": "pong",
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )
                elif msg_type == "pong":
                    # Client responded to our ping, connection is healthy
                    pass
                elif msg_type == "unsubscribe":
                    await manager.send_to_connection(
                        conn_info,
                        {
                            "type": "unsubscribed",
                            "job_id": job_id,
                        },
                    )
                    break
                elif msg_type == "status":
                    # Client requesting connection status
                    await manager.send_to_connection(
                        conn_info,
                        {
                            "type": "status",
                            "connection": conn_info.to_dict(),
                        },
                    )

            except TimeoutError:
                # Send keepalive ping
                success = await manager.send_to_connection(
                    conn_info,
                    {
                        "type": "ping",
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )
                if not success:
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await manager.send_to_connection(
                conn_info,
                {
                    "type": "error",
                    "message": str(e),
                },
            )
except Exception:  # noqa: BLE001 - Job lookup error is non-critical
            pass
    finally:
        manager.disconnect(conn_info)


@router.websocket("/jobs")
async def all_jobs_websocket(
    websocket: WebSocket,
    user_id: str = Query(..., description="User ID for filtering"),
):
    """
    WebSocket endpoint for streaming all job updates for a user.

    Requires user_id query parameter for filtering.

    Messages sent by server:
    - {"type": "connected", "channel": "...", "timestamp": "..."} - Connection confirmed
    - {"type": "job_update", "data": {...}, "timestamp": "..."} - Job update
    - {"type": "ping", "timestamp": "..."} - Keepalive ping
    - {"type": "pong", "timestamp": "..."} - Response to client ping
    - {"type": "status", "redis_connected": bool, ...} - Connection status
    - {"type": "error", "message": "..."} - Error occurred

    Messages accepted from client:
    - {"type": "ping"} - Client-initiated ping
    - {"type": "pong"} - Response to server ping
    - {"type": "status"} - Request connection status
    - {"type": "unsubscribe"} - Disconnect
    """
    await websocket.accept()

    # Subscribe to user's job channel
    channel = f"user:{user_id}:jobs"
    connected_at = datetime.utcnow()
    messages_sent = 0
    messages_received = 0

    # Record connection metric
    try:
        from api.routers.metrics import metrics

        metrics.record_ws_connection(connected=True)
    except ImportError:
        pass

    try:
        await websocket.send_json(
            {
                "type": "connected",
                "channel": channel,
                "user_id": user_id,
                "timestamp": connected_at.isoformat(),
                "heartbeat_interval": WS_HEARTBEAT_INTERVAL,
            }
        )
        messages_sent += 1

        # Listen for user's job updates
        if manager._redis:
            pubsub = manager._redis.pubsub()
            await pubsub.subscribe(channel)

            # Create task to receive client messages
            async def receive_client_messages():
                nonlocal messages_received
                while True:
                    try:
                        data = await asyncio.wait_for(
                            websocket.receive_json(), timeout=float(WS_HEARTBEAT_INTERVAL * 2)
                        )
                        messages_received += 1

                        msg_type = data.get("type", "")

                        if msg_type == "ping":
                            await websocket.send_json(
                                {
                                    "type": "pong",
                                    "timestamp": datetime.utcnow().isoformat(),
                                }
                            )
                        elif msg_type == "status":
                            await websocket.send_json(
                                {
                                    "type": "status",
                                    "user_id": user_id,
                                    "channel": channel,
                                    "connected_at": connected_at.isoformat(),
                                    "messages_sent": messages_sent,
                                    "messages_received": messages_received,
                                    "redis_connected": manager._redis is not None,
                                }
                            )
                        elif msg_type == "unsubscribe":
                            return  # Exit the receive loop

                    except TimeoutError:
                        # Send keepalive ping
                        await websocket.send_json(
                            {
                                "type": "ping",
                                "timestamp": datetime.utcnow().isoformat(),
                            }
                        )

            # Run both receive and listen tasks concurrently
            receive_task = asyncio.create_task(receive_client_messages())

            try:
                async for message in pubsub.listen():
                    if receive_task.done():
                        break

                    if message["type"] == "message":
                        try:
                            data = json.loads(message["data"])
                            await websocket.send_json(
                                {
                                    "type": "job_update",
                                    "data": data,
                                    "timestamp": datetime.utcnow().isoformat(),
                                }
                            )
                            messages_sent += 1
                        except json.JSONDecodeError:
                            pass
            finally:
                receive_task.cancel()
                await pubsub.unsubscribe(channel)
                await pubsub.close()
        else:
            # No Redis, just keep connection alive with ping/pong
            while True:
                try:
                    data = await asyncio.wait_for(
                        websocket.receive_json(), timeout=float(WS_HEARTBEAT_INTERVAL * 2)
                    )
                    messages_received += 1

                    msg_type = data.get("type", "")

                    if msg_type == "ping":
                        await websocket.send_json(
                            {
                                "type": "pong",
                                "timestamp": datetime.utcnow().isoformat(),
                            }
                        )
                        messages_sent += 1
                    elif msg_type == "unsubscribe":
                        break

                except TimeoutError:
                    await websocket.send_json(
                        {
                            "type": "ping",
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )
                    messages_sent += 1

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": str(e),
                }
            )
except Exception:  # noqa: BLE001 - Broadcast error is non-critical
            pass
    finally:
        # Record disconnection metric
        try:
            from api.routers.metrics import metrics

            metrics.record_ws_connection(connected=False)
        except ImportError:
            pass

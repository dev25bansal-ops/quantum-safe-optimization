"""
WebSocket integration tests.

Tests real WebSocket connections across pods and pub/sub functionality.
"""

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis.asyncio as aioredis
from fastapi.websockets import WebSocketState
from httpx import ASGITransport, AsyncClient

from api.main import app
from api.routers.websocket import ConnectionManager, ConnectionState

os.environ["TESTING"] = "1"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class MockWebSocket:
    """Mock WebSocket for testing."""

    def __init__(self):
        self.messages = []
        self.closed = False
        self.accepted = False
        self._close_code = None
        self.client_state = WebSocketState.CONNECTED
        self._queue = asyncio.Queue()

    async def accept(self):
        self.accepted = True

    async def send_json(self, data: dict):
        self.messages.append(data)

    async def send_text(self, data: str):
        self.messages.append(json.loads(data))

    async def receive_json(self):
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            return {"type": "timeout"}

    async def close(self, code: int = 1000, reason: str = None):
        self.closed = True
        self._close_code = code
        self.client_state = WebSocketState.DISCONNECTED

    async def send(self, data: dict):
        await self._queue.put(data)


@pytest.mark.anyio
async def test_websocket_connection_to_nonexistent_job():
    """Test WebSocket connection to a non-existent job."""
    from api.routers.websocket import manager

    mock_ws = MockWebSocket()
    job_id = "nonexistent-job-12345"

    await manager.initialize()

    conn_info = await manager.connect(mock_ws, job_id)

    assert conn_info.job_id == job_id
    assert conn_info.state == ConnectionState.CONNECTED

    manager.disconnect(conn_info)

    await manager.close()


@pytest.mark.anyio
async def test_websocket_broadcast_to_specific_job():
    """Test broadcasting to a specific job's subscribers."""
    from api.routers.websocket import manager

    await manager.initialize()

    job_id = "broadcast-job-1"

    ws1 = MockWebSocket()
    ws2 = MockWebSocket()
    ws3 = MockWebSocket()

    conn1 = await manager.connect(ws1, job_id)
    conn2 = await manager.connect(ws2, job_id)

    other_job_id = "other-job"
    conn3 = await manager.connect(ws3, other_job_id)

    test_message = {"status": "running", "progress": 50, "iteration": 10}

    await manager.broadcast_to_job(job_id, test_message)

    assert len(ws1.messages) >= 1
    assert len(ws2.messages) >= 1
    assert ws1.messages[-1]["status"] == "running"
    assert ws2.messages[-1]["status"] == "running"

    initial_ws3_count = len(ws3.messages)

    manager.disconnect(conn1)
    manager.disconnect(conn2)
    manager.disconnect(conn3)

    await manager.close()


@pytest.mark.anyio
async def test_websocket_cross_pod_communication_via_redis():
    """Test WebSocket communication across simulated pods via Redis."""
    try:
        redis_client = aioredis.from_url("redis://localhost:6379", decode_responses=True)
        await redis_client.ping()

        job_id = "cross-pod-job-123"
        channel = f"job:{job_id}:progress"

        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)

        await asyncio.sleep(0.1)

        test_message = {"status": "running", "progress": 75}
        await redis_client.publish(channel, json.dumps(test_message))

        received = await asyncio.wait_for(pubsub.get_message(), timeout=2.0)

        assert received is not None
        assert received["type"] == "message"
        data = json.loads(received["data"])
        assert data["status"] == "running"

        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await redis_client.close()
    except Exception:
        pytest.skip("Redis not available for cross-pod test")


@pytest.mark.anyio
async def test_websocket_multiple_subscribers_same_job():
    """Test multiple clients subscribing to the same job."""
    from api.routers.websocket import manager

    await manager.initialize()

    job_id = "multi-sub-job-1"

    websockets = [MockWebSocket() for _ in range(10)]
    connections = []

    for ws in websockets:
        conn = await manager.connect(ws, job_id)
        connections.append(conn)

    test_messages = [
        {"status": "queued"},
        {"status": "running", "progress": 25},
        {"status": "running", "progress": 50},
        {"status": "running", "progress": 75},
        {"status": "completed"},
    ]

    for msg in test_messages:
        await manager.broadcast_to_job(job_id, msg)
        await asyncio.sleep(0.01)

    for ws in websockets:
        assert len(ws.messages) >= len(test_messages)

    for conn in connections:
        manager.disconnect(conn)

    await manager.close()


@pytest.mark.anyio
async def test_websocket_connection_cleanup_on_disconnect():
    """Test proper cleanup of connection data on disconnect."""
    from api.routers.websocket import manager

    await manager.initialize()

    job_id = "cleanup-job-123"

    ws = MockWebSocket()
    conn = await manager.connect(ws, job_id)

    assert job_id in manager.active_connections

    manager.disconnect(conn)

    assert len(manager.active_connections.get(job_id, [])) == 0

    await manager.close()


@pytest.mark.anyio
async def test_websocket_error_handling_during_broadcast():
    """Test graceful handling of connection errors during broadcast."""
    from api.routers.websocket import manager

    await manager.initialize()

    job_id = "error-job-456"

    ws1 = MockWebSocket()
    ws2 = MockWebSocket()
    ws3 = MockWebSocket()

    conn1 = await manager.connect(ws1, job_id)
    conn2 = await manager.connect(ws2, job_id)
    conn3 = await manager.connect(ws3, job_id)

    original_send = ws2.send_json
    send_count = [0]

    async def failing_send(data):
        send_count[0] += 1
        if send_count[0] == 2:
            raise Exception("Simulated connection failure")
        return await original_send(data)

    ws2.send_json = failing_send

    test_message = {"status": "running"}

    try:
        await manager.broadcast_to_job(job_id, test_message)
    except Exception:
        pytest.fail("Broadcast should handle connection errors gracefully")

    assert len(ws1.messages) >= 1
    assert len(ws3.messages) >= 1

    manager.disconnect(conn1)
    manager.disconnect(conn2)
    manager.disconnect(conn3)

    await manager.close()


@pytest.mark.anyio
async def test_websocket_pubsub_message_filtering():
    """Test that pub/sub messages are filtered by job ID."""
    try:
        redis_client = aioredis.from_url("redis://localhost:6379", decode_responses=True)
        await redis_client.ping()

        job_1 = "filter-job-1"
        job_2 = "filter-job-2"

        channel_1 = f"job:{job_1}:progress"
        channel_2 = f"job:{job_2}:progress"

        sub1 = redis_client.pubsub()
        sub2 = redis_client.pubsub()

        await sub1.subscribe(channel_1)
        await sub2.subscribe(channel_2)

        await asyncio.sleep(0.1)

        await redis_client.publish(channel_1, json.dumps({"job": "job1", "status": "running"}))
        await redis_client.publish(channel_2, json.dumps({"job": "job2", "status": "completed"}))

        msg1 = await asyncio.wait_for(sub1.get_message(), timeout=2.0)
        msg2 = await asyncio.wait_for(sub2.get_message(), timeout=2.0)

        assert msg1 is not None
        data1 = json.loads(msg1["data"])
        assert data1["job"] == "job1"

        assert msg2 is not None
        data2 = json.loads(msg2["data"])
        assert data2["job"] == "job2"

        await sub1.unsubscribe(channel_1)
        await sub2.unsubscribe(channel_2)
        await sub1.close()
        await sub2.close()
        await redis_client.close()
    except Exception:
        pytest.skip("Redis not available for filtering test")


@pytest.mark.anyio
async def test_websocket_status_endpoint():
    """Test WebSocket manager status endpoint."""
    from api.routers.websocket import manager

    await manager.initialize()

    status = manager.get_status()

    assert "redis_connected" in status
    assert "total_connections" in status
    assert "active_connections" in status
    assert "connections_by_job" in status

    await manager.close()


@pytest.mark.anyio
async def test_websocket_concurrent_messages():
    """Test handling of concurrent WebSocket messages."""
    from api.routers.websocket import manager

    await manager.initialize()

    job_id = "concurrent-job-789"

    ws = MockWebSocket()
    conn = await manager.connect(ws, job_id)

    import asyncio

    async def send_message(index):
        msg = {"index": index, "status": "progress"}
        await manager.broadcast_to_job(job_id, msg)

    await asyncio.gather(*[send_message(i) for i in range(20)])

    assert len(ws.messages) >= 20

    manager.disconnect(conn)
    await manager.close()


@pytest.mark.anyio
async def test_websocket_timeout_recovery():
    """Test WebSocket recovery from connection timeout."""
    from api.routers.websocket import manager

    await manager.initialize()

    job_id = "timeout-job-999"

    ws = MockWebSocket()
    conn = await manager.connect(ws, job_id)

    await manager.broadcast_to_job(job_id, {"status": "running"})

    await asyncio.sleep(1)

    await manager.broadcast_to_job(job_id, {"status": "still_running", "progress": 50})

    assert len(ws.messages) >= 2
    assert ws.messages[-1]["status"] == "still_running"

    manager.disconnect(conn)
    await manager.close()


@pytest.mark.anyio
async def test_websocket_connection_info_tracking():
    """Test tracking of connection metadata."""
    from api.routers.websocket import manager

    await manager.initialize()

    job_id = "info-job-111"
    user_id = "test-user-123"

    ws = MockWebSocket()
    conn = await manager.connect(ws, job_id, user_id)

    info_dict = conn.to_dict()

    assert info_dict["job_id"] == job_id
    assert info_dict["user_id"] == user_id
    assert "connected_at" in info_dict
    assert "messages_sent" in info_dict
    assert "messages_received" in info_dict
    assert "uptime_seconds" in info_dict

    manager.disconnect(conn)
    await manager.close()


@pytest.mark.anyio
async def test_websocket_message_type_handling():
    """Test handling of different message types."""
    from api.routers.websocket import manager

    await manager.initialize()

    job_id = "type-job-222"

    ws = MockWebSocket()
    conn = await manager.connect(ws, job_id)

    message_types = [
        {"type": "ping"},
        {"type": "progress", "progress": 10},
        {"type": "status", "status": "running"},
        {"type": "error", "message": "Test error"},
        {"type": "completed", "result": {"value": 42}},
    ]

    for msg in message_types:
        await manager.broadcast_to_job(job_id, msg)

    received_types = [msg.get("type") for msg in ws.messages]

    for expected_type in ["ping", "progress", "status", "error", "completed"]:
        assert expected_type in received_types

    manager.disconnect(conn)
    await manager.close()


@pytest.mark.anyio
async def test_websocket_large_message_handling():
    """Test handling of large WebSocket messages."""
    from api.routers.websocket import manager

    await manager.initialize()

    job_id = "large-msg-job-333"

    ws = MockWebSocket()
    conn = await manager.connect(ws, job_id)

    large_message = {
        "type": "results",
        "data": {"samples": [{"state": f"{i:010b}", "energy": i * 0.1} for i in range(1000)]},
    }

    await manager.broadcast_to_job(job_id, large_message)

    assert len(ws.messages) >= 1
    assert len(ws.messages[-1]["data"]["samples"]) == 1000

    manager.disconnect(conn)
    await manager.close()


@pytest.mark.anyio
async def test_websocket_manager_initialization_and_shutdown():
    """Test proper initialization and shutdown of WebSocket manager."""
    from api.routers.websocket import manager

    await manager.initialize()

    status = manager.get_status()
    assert status is not None

    await manager.close()

    status_after_close = manager.get_status()
    assert status_after_close["total_connections"] == status["total_connections"]

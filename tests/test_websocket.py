"""
WebSocket connection and job progress streaming tests.
"""

import asyncio
import json
import os

import pytest

# Disable rate limiting in test environment
os.environ["TESTING"] = "1"
os.environ["DEMO_MODE"] = "true"

from fastapi.websockets import WebSocketState
from httpx import ASGITransport, AsyncClient

from api.main import app


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
    """Mock WebSocket for testing that matches FastAPI WebSocket interface."""

    def __init__(self):
        self.messages = []
        self.closed = False
        self.accepted = False
        self._close_code = None
        self.client_state = WebSocketState.CONNECTED

    async def accept(self):
        self.accepted = True

    async def send_text(self, data: str):
        self.messages.append(json.loads(data))

    async def send_json(self, data: dict):
        self.messages.append(data)

    async def receive_text(self):
        # Simulate client sending ping
        await asyncio.sleep(0.1)
        return json.dumps({"type": "ping"})

    async def receive_json(self):
        await asyncio.sleep(0.1)
        return {"type": "ping"}

    async def close(self, code: int = 1000, reason: str = None):
        self.closed = True
        self._close_code = code
        self.client_state = WebSocketState.DISCONNECTED


@pytest.mark.anyio
async def test_websocket_connection_manager_add_remove():
    """Test WebSocket connection manager add/remove operations."""
    from api.routers.websocket import connection_manager

    ws = MockWebSocket()
    job_id = "test-job-123"

    # Add connection - returns ConnectionInfo
    conn_info = await connection_manager.connect(ws, job_id)
    assert job_id in connection_manager.active_connections
    assert conn_info in connection_manager.active_connections[job_id]

    # Remove connection - takes ConnectionInfo
    connection_manager.disconnect(conn_info)
    # After disconnect, job_id might be removed if empty
    if job_id in connection_manager.active_connections:
        assert conn_info not in connection_manager.active_connections[job_id]


@pytest.mark.anyio
async def test_websocket_broadcast_to_job():
    """Test broadcasting messages to job subscribers."""
    from api.routers.websocket import connection_manager

    ws1 = MockWebSocket()
    ws2 = MockWebSocket()
    job_id = "broadcast-test-job"

    # Connect two websockets to same job
    conn1 = await connection_manager.connect(ws1, job_id)
    conn2 = await connection_manager.connect(ws2, job_id)

    # Broadcast message
    test_message = {"status": "running", "progress": 50}
    await connection_manager.broadcast_to_job(job_id, test_message)

    # Both should receive the message
    assert len(ws1.messages) >= 1
    assert len(ws2.messages) >= 1
    assert ws1.messages[-1] == test_message
    assert ws2.messages[-1] == test_message

    # Cleanup
    connection_manager.disconnect(conn1)
    connection_manager.disconnect(conn2)


@pytest.mark.anyio
async def test_websocket_send_job_update():
    """Test sending job status updates via WebSocket using broadcast_to_job."""
    from api.routers.websocket import connection_manager

    ws = MockWebSocket()
    job_id = "update-test-job"

    conn_info = await connection_manager.connect(ws, job_id)

    # Use broadcast_to_job to send update (send_job_update doesn't exist)
    update_message = {
        "type": "job_update",
        "job_id": job_id,
        "status": "running",
        "progress": 75,
        "message": "Processing optimization",
    }
    await connection_manager.broadcast_to_job(job_id, update_message)

    # Verify message format
    assert len(ws.messages) >= 1
    last_msg = ws.messages[-1]
    assert last_msg["type"] == "job_update"
    assert last_msg["job_id"] == job_id
    assert last_msg["status"] == "running"
    assert last_msg["progress"] == 75

    connection_manager.disconnect(conn_info)


@pytest.mark.anyio
async def test_websocket_disconnect_cleanup():
    """Test that disconnection properly cleans up resources."""
    from api.routers.websocket import connection_manager

    ws = MockWebSocket()
    job_id = "cleanup-test-job"

    conn_info = await connection_manager.connect(ws, job_id)
    assert job_id in connection_manager.active_connections

    connection_manager.disconnect(conn_info)

    # Job should be removed when no connections remain
    if job_id in connection_manager.active_connections:
        assert len(connection_manager.active_connections[job_id]) == 0


@pytest.mark.anyio
async def test_websocket_multiple_jobs():
    """Test WebSocket connections to multiple different jobs."""
    from api.routers.websocket import connection_manager

    ws1 = MockWebSocket()
    ws2 = MockWebSocket()
    job_id_1 = "multi-job-1"
    job_id_2 = "multi-job-2"

    conn1 = await connection_manager.connect(ws1, job_id_1)
    conn2 = await connection_manager.connect(ws2, job_id_2)

    # Send to job 1 only
    await connection_manager.broadcast_to_job(job_id_1, {"status": "job1"})

    # Only ws1 should have the message
    job1_msgs = [m for m in ws1.messages if m.get("status") == "job1"]
    job2_msgs = [m for m in ws2.messages if m.get("status") == "job1"]

    assert len(job1_msgs) >= 1
    assert len(job2_msgs) == 0

    # Cleanup
    connection_manager.disconnect(conn1)
    connection_manager.disconnect(conn2)


@pytest.mark.anyio
async def test_websocket_error_handling():
    """Test WebSocket handles errors gracefully."""
    from api.routers.websocket import connection_manager

    # Create a websocket that fails on send
    class FailingWebSocket(MockWebSocket):
        async def send_json(self, data: dict):
            raise Exception("Connection lost")

    ws = FailingWebSocket()
    job_id = "error-test-job"

    conn_info = await connection_manager.connect(ws, job_id)

    # Broadcasting should not raise even if websocket fails
    try:
        await connection_manager.broadcast_to_job(job_id, {"test": "data"})
    except Exception:
        pytest.fail("broadcast_to_job should handle errors gracefully")

    # Cleanup
    connection_manager.disconnect(conn_info)


@pytest.mark.anyio
async def test_websocket_job_completion_notification():
    """Test WebSocket sends completion notification when job finishes."""
    from api.routers.websocket import connection_manager

    ws = MockWebSocket()
    job_id = "completion-test-job"

    conn_info = await connection_manager.connect(ws, job_id)

    # Simulate job completion via broadcast
    completion_message = {
        "type": "job_update",
        "job_id": job_id,
        "status": "completed",
        "progress": 100,
        "result": {"optimal_value": -3.5},
    }
    await connection_manager.broadcast_to_job(job_id, completion_message)

    # Verify completion message
    completion_msgs = [m for m in ws.messages if m.get("status") == "completed"]
    assert len(completion_msgs) >= 1
    assert completion_msgs[-1]["progress"] == 100
    assert "result" in completion_msgs[-1]

    connection_manager.disconnect(conn_info)


@pytest.mark.anyio
async def test_websocket_ping_pong():
    """Test WebSocket ping/pong keepalive mechanism."""
    from api.routers.websocket import connection_manager

    ws = MockWebSocket()
    job_id = "ping-test-job"

    conn_info = await connection_manager.connect(ws, job_id)

    # Send ping
    await connection_manager.broadcast_to_job(job_id, {"type": "ping"})

    # Should receive ping
    ping_msgs = [m for m in ws.messages if m.get("type") == "ping"]
    assert len(ping_msgs) >= 1

    connection_manager.disconnect(conn_info)


@pytest.mark.anyio
async def test_websocket_connection_count():
    """Test tracking of active connection counts."""
    from api.routers.websocket import connection_manager

    job_id = "count-test-job"
    websockets = [MockWebSocket() for _ in range(5)]
    conn_infos = []

    # Connect all
    for ws in websockets:
        conn_info = await connection_manager.connect(ws, job_id)
        conn_infos.append(conn_info)

    assert len(connection_manager.active_connections.get(job_id, [])) == 5

    # Disconnect some
    for conn_info in conn_infos[:3]:
        connection_manager.disconnect(conn_info)

    assert len(connection_manager.active_connections.get(job_id, [])) == 2

    # Cleanup remaining
    for conn_info in conn_infos[3:]:
        connection_manager.disconnect(conn_info)

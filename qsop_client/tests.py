"""
Tests for QSOP Client SDK.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from qsop_client import (
    QSOPClient,
    SyncQSOPClient,
    QSOPClientError,
    Job,
    KeyPair,
    User,
)


class TestJob:
    def test_job_from_dict(self):
        data = {
            "id": "job-123",
            "problem_type": "QAOA",
            "status": "completed",
            "created_at": "2024-01-01T00:00:00Z",
            "progress": 1.0,
            "result": {"optimal_value": -10.5},
        }
        job = Job.from_dict(data)

        assert job.id == "job-123"
        assert job.problem_type == "QAOA"
        assert job.status == "completed"
        assert job.progress == 1.0
        assert job.result == {"optimal_value": -10.5}

    def test_job_defaults(self):
        data = {"id": "job-123", "created_at": "2024-01-01"}
        job = Job.from_dict(data)

        assert job.status == "pending"
        assert job.progress == 0.0


class TestKeyPair:
    def test_keypair_from_dict(self):
        data = {
            "key_id": "key-123",
            "public_key": "abc123",
            "key_type": "kem",
            "algorithm": "ML-KEM-768",
            "created_at": "2024-01-01",
            "expires_at": "2025-01-01",
        }
        key = KeyPair.from_dict(data)

        assert key.key_id == "key-123"
        assert key.algorithm == "ML-KEM-768"


class TestUser:
    def test_user_from_dict(self):
        data = {
            "user_id": "user-123",
            "username": "testuser",
            "email": "test@example.com",
            "roles": ["admin", "user"],
            "created_at": "2024-01-01",
        }
        user = User.from_dict(data)

        assert user.user_id == "user-123"
        assert user.username == "testuser"
        assert user.roles == ["admin", "user"]


class TestQSOPClientError:
    def test_error_message(self):
        error = QSOPClientError("Something went wrong")
        assert str(error) == "Something went wrong"

    def test_error_with_status(self):
        error = QSOPClientError("Not found", status_code=404)
        assert str(error) == "[404] Not found"
        assert error.status_code == 404


class TestQSOPClient:
    @pytest.mark.asyncio
    async def test_context_manager(self):
        async with QSOPClient() as client:
            assert client._client is None

        # Client should be closed after context
        assert client._client is None

    @pytest.mark.asyncio
    async def test_get_headers_without_token(self):
        client = QSOPClient()
        headers = client._get_headers()

        assert "Authorization" not in headers
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_get_headers_with_token(self):
        client = QSOPClient()
        client._token = "test-token"
        headers = client._get_headers()

        assert headers["Authorization"] == "Bearer test-token"


class TestSyncQSOPClient:
    def test_context_manager(self):
        with SyncQSOPClient() as client:
            assert client._async_client is not None

    def test_run_async(self):
        client = SyncQSOPClient()

        async def async_func():
            return 42

        result = client._run(async_func())
        assert result == 42


@pytest.mark.integration
class TestIntegration:
    """Integration tests that require a running API server."""

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health endpoint."""
        async with QSOPClient(base_url="http://localhost:8000") as client:
            health = await client.health_check()
            assert "status" in health

    @pytest.mark.asyncio
    async def test_login_and_get_jobs(self):
        """Test login and job listing."""
        import os

        async with QSOPClient(base_url="http://localhost:8000") as client:
            await client.login("admin", os.getenv("ADMIN_PASSWORD", "admin123!"))
            jobs = await client.get_jobs()
            assert isinstance(jobs, list)

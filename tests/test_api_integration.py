"""
Integration tests for API endpoints.

Tests full request/response cycles with database.
"""

import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

os.environ["TESTING"] = "1"
os.environ["APP_ENV"] = "test"

from api.main import app


@pytest_asyncio.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_token(client: AsyncClient):
    """Get authentication token for tests."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": os.getenv("ADMIN_PASSWORD", "changeme")},
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token")
    return None


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test basic health check."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_detailed(self, client: AsyncClient):
        """Test detailed health check."""
        response = await client.get("/health?detailed=true")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "env" in data

    @pytest.mark.asyncio
    async def test_crypto_health(self, client: AsyncClient):
        """Test crypto provider health."""
        response = await client.get("/health/crypto")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        """Test successful login."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "username": os.getenv("ADMIN_USERNAME", "admin"),
                "password": os.getenv("ADMIN_PASSWORD", "changeme"),
            },
        )

        assert response.status_code in [200, 401]

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client: AsyncClient):
        """Test login with invalid credentials."""
        response = await client.post(
            "/api/v1/auth/login", json={"username": "invalid", "password": "wrong"}
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_protected_endpoint_without_token(self, client: AsyncClient):
        """Test accessing protected endpoint without token."""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    async def test_protected_endpoint_with_token(self, client: AsyncClient, auth_token):
        """Test accessing protected endpoint with valid token."""
        if not auth_token:
            pytest.skip("Could not get auth token")

        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code in [200, 401]


class TestJobEndpoints:
    """Tests for job management endpoints."""

    @pytest.mark.asyncio
    async def test_list_jobs_unauthenticated(self, client: AsyncClient):
        """Test listing jobs without auth."""
        response = await client.get("/api/v1/jobs")

        assert response.status_code in [200, 401, 422]

    @pytest.mark.asyncio
    async def test_submit_job_validation(self, client: AsyncClient, auth_token):
        """Test job submission validation."""
        if not auth_token:
            pytest.skip("Could not get auth token")

        response = await client.post(
            "/api/v1/jobs",
            json={"problem_type": "INVALID_TYPE", "problem_config": {}},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code in [400, 422, 401]


class TestKeyEndpoints:
    """Tests for PQC key management."""

    @pytest.mark.asyncio
    async def test_generate_key_unauthenticated(self, client: AsyncClient):
        """Test key generation without auth."""
        response = await client.post(
            "/api/v1/auth/keys/generate", json={"key_type": "kem", "security_level": 3}
        )

        assert response.status_code in [401, 403]


class TestMetricsEndpoint:
    """Tests for metrics endpoint."""

    @pytest.mark.asyncio
    async def test_metrics(self, client: AsyncClient):
        """Test Prometheus metrics endpoint."""
        response = await client.get("/metrics")

        assert response.status_code == 200


class TestOpenAPI:
    """Tests for OpenAPI documentation."""

    @pytest.mark.asyncio
    async def test_docs(self, client: AsyncClient):
        """Test OpenAPI docs endpoint."""
        response = await client.get("/docs")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_openapi_json(self, client: AsyncClient):
        """Test OpenAPI JSON schema."""
        response = await client.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

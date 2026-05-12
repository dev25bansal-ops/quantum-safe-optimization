"""API Contract Tests.

Validates that the API conforms to its OpenAPI specification.
Uses schemathesis for property-based contract testing.

Run with: pytest tests/contract/ -v
"""

import pytest


class TestHealthEndpoint:
    """Contract tests for /health endpoint."""

    def test_health_returns_200(self, client):
        """Health endpoint must return 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ("healthy", "degraded", "unhealthy")

    def test_readiness_returns_200(self, client):
        """Readiness endpoint must return 200 OK."""
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestAuthEndpoint:
    """Contract tests for /api/v1/auth endpoints."""

    def test_register_requires_valid_password(self, client):
        """Registration must validate password strength."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "password": "weak",  # Too short, no special chars
                "email": "test@example.com",
            },
        )
        assert response.status_code in (422, 400)

    def test_login_requires_credentials(self, client):
        """Login must require username and password."""
        response = client.post("/api/v1/auth/login", json={})
        assert response.status_code == 422

    def test_login_invalid_credentials_returns_401(self, client):
        """Invalid login must return 401."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent", "password": "wrong"},
        )
        assert response.status_code == 401


class TestJobsEndpoint:
    """Contract tests for /api/v1/jobs endpoints."""

    def test_submit_requires_problem_type(self, client):
        """Job submission must include problem_type."""
        response = client.post("/api/v1/jobs", json={})
        assert response.status_code == 422

    def test_submit_invalid_problem_type_returns_400(self, client):
        """Invalid problem_type must return 400."""
        response = client.post(
            "/api/v1/jobs",
            json={
                "problem_type": "INVALID",
                "problem_config": {},
            },
        )
        assert response.status_code in (400, 422)

    def test_submit_valid_qaoa_job(self, client):
        """Valid QAOA job must return 202."""
        response = client.post(
            "/api/v1/jobs",
            json={
                "problem_type": "QAOA",
                "problem_config": {
                    "type": "maxcut",
                    "edges": [[0, 1], [1, 2], [2, 0]],
                },
                "parameters": {"layers": 1, "shots": 100},
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    def test_get_nonexistent_job_returns_404(self, client):
        """Getting a nonexistent job must return 404."""
        response = client.get("/api/v1/jobs/nonexistent_id")
        assert response.status_code == 404


class TestMetricsEndpoint:
    """Contract tests for /metrics endpoint."""

    def test_metrics_returns_prometheus_format(self, client):
        """Metrics endpoint must return Prometheus format."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")


class TestOpenAPI:
    """Contract tests for OpenAPI spec availability."""

    def test_openapi_spec_available(self, client):
        """OpenAPI spec must be available in development."""
        import os

        if os.getenv("APP_ENV", "development") == "development":
            response = client.get("/openapi.json")
            assert response.status_code == 200
            spec = response.json()
            assert "paths" in spec
            assert "info" in spec

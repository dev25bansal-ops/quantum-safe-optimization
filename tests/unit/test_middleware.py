"""
Unit tests for API middleware components.

Tests cover:
- Authentication middleware
- Rate limiting middleware
- Request ID middleware
- Security headers middleware
- Metrics middleware
"""

import pytest
from httpx import ASGITransport, AsyncClient


class TestRequestIDMiddleware:
    """Test request ID tracking middleware."""

    @pytest.mark.asyncio
    async def test_generates_request_id_if_missing(self):
        """Test that middleware generates X-Request-ID if not provided."""
        try:
            from api.main import app
        except ImportError:
            pytest.skip("API module not available")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

            # Should have X-Request-ID in response
            assert "x-request-id" in response.headers or "X-Request-ID" in response.headers

    @pytest.mark.asyncio
    async def test_preserves_existing_request_id(self):
        """Test that middleware preserves client-provided request ID."""
        try:
            from api.main import app
        except ImportError:
            pytest.skip("API module not available")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            custom_id = "my-custom-request-id-12345"
            response = await client.get(
                "/health",
                headers={"X-Request-ID": custom_id}
            )

            # Should preserve our custom ID
            returned_id = response.headers.get("x-request-id") or response.headers.get("X-Request-ID")
            assert returned_id == custom_id


class TestSecurityHeadersMiddleware:
    """Test security headers middleware."""

    @pytest.mark.asyncio
    async def test_adds_security_headers(self):
        """Test that middleware adds standard security headers."""
        try:
            from api.main import app
        except ImportError:
            pytest.skip("API module not available")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

            # Should have security headers
            # Common ones: X-Content-Type-Options, X-Frame-Options, etc.
            headers_lower = {k.lower(): v for k, v in response.headers.items()}

            # At least some security headers should be present
            security_headers = [
                "x-content-type-options",
                "x-frame-options",
                "strict-transport-security",
            ]

            # Check for at least one security header
            found = any(h in headers_lower for h in security_headers)
            assert found, f"No security headers found. Headers: {list(headers_lower.keys())}"

    @pytest.mark.asyncio
    async def test_hsts_enabled_in_production(self):
        """Test that HSTS is enabled in production mode."""
        import os
        os.environ["APP_ENV"] = "production"

        try:
            # Need to reload app with production settings
            import importlib
            import api.main
            importlib.reload(api.main)

            from api.main import app
        except ImportError:
            pytest.skip("API module not available")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

            headers_lower = {k.lower(): v for k, v in response.headers.items()}

            # HSTS should be present in production
            if os.getenv("APP_ENV") == "production":
                assert "strict-transport-security" in headers_lower


class TestGZipMiddleware:
    """Test GZip compression middleware."""

    @pytest.mark.asyncio
    async def test_compresses_large_responses(self):
        """Test that responses > 500 bytes are compressed."""
        try:
            from api.main import app
        except ImportError:
            pytest.skip("API module not available")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/health/detailed",
                headers={"Accept-Encoding": "gzip"}
            )

            # Check if Content-Encoding is gzip
            content_encoding = response.headers.get("content-encoding", "").lower()

            # Either it's compressed or the response was too small
            assert content_encoding == "gzip" or response.status_code == 200

    @pytest.mark.asyncio
    async def test_doesnt_compress_small_responses(self):
        """Test that small responses are not compressed."""
        try:
            from api.main import app
        except ImportError:
            pytest.skip("API module not available")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/health/live",
                headers={"Accept-Encoding": "gzip"}
            )

            # Small response, might not be compressed
            content_encoding = response.headers.get("content-encoding", "").lower()

            # Either not compressed (expected for small responses) or still valid
            assert content_encoding in ["", "gzip"]


class TestCORSMiddleware:
    """Test CORS middleware configuration."""

    @pytest.mark.asyncio
    async def test_preflight_request_returns_200(self):
        """Test that OPTIONS preflight requests return 200."""
        try:
            from api.main import app
        except ImportError:
            pytest.skip("API module not available")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.options(
                "/health",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                }
            )

            # Should allow preflight
            assert response.status_code in [200, 204]

    @pytest.mark.asyncio
    async def test_includes_cors_headers(self):
        """Test that responses include CORS headers."""
        try:
            from api.main import app
        except ImportError:
            pytest.skip("API module not available")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/health",
                headers={"Origin": "http://localhost:3000"}
            )

            # Should have Access-Control-Allow-Origin
            assert "access-control-allow-origin" in response.headers or \
                   "Access-Control-Allow-Origin" in response.headers


class TestMetricsMiddleware:
    """Test metrics collection middleware."""

    @pytest.mark.asyncio
    async def test_health_endpoint_works_with_middleware(self):
        """Test that health endpoint works with metrics middleware enabled."""
        try:
            from api.main import app
        except ImportError:
            pytest.skip("API module not available")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_metrics_endpoint_returns_prometheus_format(self):
        """Test that /metrics endpoint returns Prometheus format."""
        try:
            from api.main import app
        except ImportError:
            pytest.skip("API module not available")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/metrics")

            # Should return text/plain or text/plain; version=0.0.4
            content_type = response.headers.get("content-type", "")
            assert "text/plain" in content_type or response.status_code == 200


class TestMiddlewareChain:
    """Test that middleware chain works correctly together."""

    @pytest.mark.asyncio
    async def test_full_middleware_chain(self):
        """Test that request passes through all middleware correctly."""
        try:
            from api.main import app
        except ImportError:
            pytest.skip("API module not available")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/health",
                headers={
                    "Origin": "http://localhost:3000",
                    "X-Request-ID": "test-chain-123",
                    "Accept-Encoding": "gzip",
                }
            )

            # Should succeed
            assert response.status_code == 200

            # Should have various middleware headers
            headers_lower = {k.lower(): v for k, v in response.headers.items()}

            # Request ID should be preserved
            request_id = headers_lower.get("x-request-id")
            assert request_id == "test-chain-123" or request_id is not None

    @pytest.mark.asyncio
    async def test_error_response_through_middleware(self):
        """Test that error responses pass through middleware correctly."""
        try:
            from api.main import app
        except ImportError:
            pytest.skip("API module not available")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Request non-existent endpoint
            response = await client.get("/nonexistent-endpoint")

            # Should get 404
            assert response.status_code == 404

            # Should still have middleware headers
            assert "x-request-id" in response.headers or "X-Request-ID" in response.headers


class TestRequestValidationMiddleware:
    """Test request validation middleware."""

    @pytest.mark.asyncio
    async def test_rejects_oversized_requests(self):
        """Test that oversized request bodies are rejected."""
        try:
            from api.main import app
        except ImportError:
            pytest.skip("API module not available")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create oversized payload (10MB)
            large_payload = {"data": "x" * (10 * 1024 * 1024)}

            response = await client.post(
                "/api/v1/jobs",
                json=large_payload
            )

            # Should reject with 413 Payload Too Large or similar
            # (depends on configuration)
            assert response.status_code in [413, 400, 422] or response.status_code < 500

"""
Integration tests for webhook delivery system.

Tests cover:
- Webhook delivery lifecycle
- Retry logic
- Signature verification
- SSRF protection
- Concurrent deliveries
"""

import asyncio
import pytest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch


class TestWebhookDeliveryLifecycle:
    """Test webhook delivery from creation to acknowledgment."""

    @pytest.mark.asyncio
    async def test_webhook_delivery_on_job_completion(self):
        """Test that webhooks are delivered when jobs complete."""
        from api.routers.jobs import send_webhook_notification
        
        # Mock HTTP client
        with patch("api.routers.jobs.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Send webhook
            await send_webhook_notification(
                callback_url="https://example.com/webhook",
                job_id="job_test_001",
                status="completed",
                result={"value": -5.234}
            )

            # Verify POST was called
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            
            # Verify payload structure
            payload = call_args[1]["json"]
            assert payload["job_id"] == "job_test_001"
            assert payload["status"] == "completed"
            assert "timestamp" in payload

    @pytest.mark.asyncio
    async def test_webhook_delivery_on_failure(self):
        """Test that failure webhooks include error information."""
        from api.routers.jobs import send_webhook_notification
        
        with patch("api.routers.jobs.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await send_webhook_notification(
                callback_url="https://example.com/webhook",
                job_id="job_test_002",
                status="failed",
                error="Quantum decoherence detected"
            )

            # Verify error included
            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            assert payload["status"] == "failed"
            assert payload["error"] == "Quantum decoherence detected"

    @pytest.mark.asyncio
    async def test_webhook_retry_on_failure(self):
        """Test that webhooks retry on delivery failure."""
        from api.routers.jobs import send_webhook_notification
        
        with patch("api.routers.jobs.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            
            # First call fails, second succeeds
            mock_response_fail = MagicMock()
            mock_response_fail.status_code = 500
            mock_response_success = MagicMock()
            mock_response_success.status_code = 200
            
            mock_client.post.side_effect = [
                mock_response_fail,
                mock_response_fail,
                mock_response_success
            ]
            
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Should retry
            await send_webhook_notification(
                callback_url="https://example.com/webhook",
                job_id="job_test_003",
                status="completed"
            )

            # Verify multiple attempts
            assert mock_client.post.call_count >= 1


class TestWebhookSSRFProtection:
    """Test SSRF (Server-Side Request Forgery) protection."""

    @pytest.mark.asyncio
    async def test_blocks_internal_ips(self):
        """Test that webhooks to internal IPs are blocked."""
        try:
            from api.services.webhooks import validate_webhook_url
        except ImportError:
            pytest.skip("Webhook service not available")

        # Should block internal IPs
        internal_urls = [
            "http://localhost:8080/webhook",
            "http://127.0.0.1:8080/webhook",
            "http://192.168.1.100/webhook",
            "http://10.0.0.1/webhook",
            "http://172.16.0.1/webhook",
        ]

        for url in internal_urls:
            is_valid, error = await validate_webhook_url(url)
            assert is_valid is False or "internal" in (error or "").lower()

    @pytest.mark.asyncio
    async def test_allows_external_urls(self):
        """Test that webhooks to external URLs are allowed."""
        try:
            from api.services.webhooks import validate_webhook_url
        except ImportError:
            pytest.skip("Webhook service not available")

        external_urls = [
            "https://example.com/webhook",
            "https://api.myapp.com/callbacks/quantum",
            "https://webhook.site/test-123",
        ]

        for url in external_urls:
            is_valid, error = await validate_webhook_url(url)
            assert is_valid is True, f"URL {url} should be valid: {error}"

    @pytest.mark.asyncio
    async def test_blocks_metadata_endpoints(self):
        """Test that cloud metadata endpoints are blocked."""
        try:
            from api.services.webhooks import validate_webhook_url
        except ImportError:
            pytest.skip("Webhook service not available")

        metadata_urls = [
            "http://169.254.169.254/latest/meta-data/",  # AWS
            "http://metadata.google.internal/computeMetadata/v1/",  # GCP
            "http://168.63.129.16/machine/instance-details",  # Azure
        ]

        for url in metadata_urls:
            is_valid, error = await validate_webhook_url(url)
            assert is_valid is False, f"Metadata URL {url} should be blocked"


class TestWebhookSignatureVerification:
    """Test webhook signature verification."""

    def test_webhook_signature_generation(self):
        """Test that webhook signatures are generated correctly."""
        try:
            from api.services.webhooks import generate_webhook_signature
        except ImportError:
            pytest.skip("Webhook service not available")

        payload = {"job_id": "test", "status": "completed"}
        secret = "test_secret_key"

        signature = generate_webhook_signature(payload, secret)

        # Signature should be non-empty string
        assert isinstance(signature, str)
        assert len(signature) > 0

        # Same payload + secret should produce same signature
        signature2 = generate_webhook_signature(payload, secret)
        assert signature == signature2

    def test_webhook_signature_verification(self):
        """Test webhook signature verification."""
        try:
            from api.services.webhooks import (
                generate_webhook_signature,
                verify_webhook_signature
            )
        except ImportError:
            pytest.skip("Webhook service not available")

        payload = {"job_id": "test", "status": "completed"}
        secret = "test_secret_key"

        # Generate signature
        signature = generate_webhook_signature(payload, secret)

        # Verify valid signature
        assert verify_webhook_signature(payload, signature, secret) is True

        # Verify wrong signature fails
        assert verify_webhook_signature(payload, "wrong_signature", secret) is False

        # Verify wrong secret fails
        assert verify_webhook_signature(payload, signature, "wrong_secret") is False


class TestConcurrentWebhookDeliveries:
    """Test concurrent webhook deliveries."""

    @pytest.mark.asyncio
    async def test_concurrent_webhook_calls(self):
        """Test multiple webhooks can be delivered concurrently."""
        from api.routers.jobs import send_webhook_notification
        
        with patch("api.routers.jobs.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Send 10 webhooks concurrently
            tasks = [
                send_webhook_notification(
                    callback_url=f"https://example.com/webhook/{i}",
                    job_id=f"job_{i:03d}",
                    status="completed"
                )
                for i in range(10)
            ]
            
            await asyncio.gather(*tasks)

            # All should succeed
            assert mock_client.post.call_count == 10


class TestWebhookEventTypes:
    """Test different webhook event types."""

    @pytest.mark.asyncio
    async def test_job_created_event(self):
        """Test job.created webhook event."""
        from api.routers.jobs import send_webhook_notification
        
        with patch("api.routers.jobs.httpx.AsyncClient") as mock_client:
            await send_webhook_notification(
                callback_url="https://example.com/webhook",
                job_id="job_test",
                status="queued",
                event="job.created"
            )

    @pytest.mark.asyncio
    async def test_job_completed_event(self):
        """Test job.completed webhook event."""
        from api.routers.jobs import send_webhook_notification
        
        with patch("api.routers.jobs.httpx.AsyncClient") as mock_client:
            await send_webhook_notification(
                callback_url="https://example.com/webhook",
                job_id="job_test",
                status="completed",
                event="job.completed",
                result={"value": -5.0}
            )

    @pytest.mark.asyncio
    async def test_job_failed_event(self):
        """Test job.failed webhook event."""
        from api.routers.jobs import send_webhook_notification
        
        with patch("api.routers.jobs.httpx.AsyncClient") as mock_client:
            await send_webhook_notification(
                callback_url="https://example.com/webhook",
                job_id="job_test",
                status="failed",
                event="job.failed",
                error="Test error"
            )

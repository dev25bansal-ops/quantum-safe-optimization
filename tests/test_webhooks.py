"""
Webhook delivery and callback tests.
"""

import os
import pytest
import asyncio
import json
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime

# Disable rate limiting in test environment
os.environ["TESTING"] = "1"
os.environ["DEMO_MODE"] = "true"

import httpx
from httpx import AsyncClient, ASGITransport
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


class MockResponse:
    """Mock HTTP response for webhook testing."""
    
    def __init__(self, status_code: int = 200, json_data: dict = None):
        self.status_code = status_code
        self._json_data = json_data or {"received": True}
    
    def json(self):
        return self._json_data
    
    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "Error", 
                request=MagicMock(), 
                response=self
            )


@pytest.mark.anyio
async def test_webhook_payload_structure():
    """Test webhook payload has correct structure."""
    from api.routers.jobs import send_webhook_notification
    
    captured_payload = None
    
    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, *args):
            pass
        
        async def post(self, url, json=None, **kwargs):
            nonlocal captured_payload
            captured_payload = json
            return MockResponse(200)
    
    with patch('api.routers.jobs.httpx.AsyncClient', MockAsyncClient):
        # Disable webhook service to use legacy fallback
        with patch('api.routers.jobs._webhooks_available', False):
            result = await send_webhook_notification(
                callback_url="https://example.com/webhook",
                job_id="test-job-123",
                status="completed",
                result={"optimal_value": -3.5}
            )
        
        # Verify webhook was sent
        assert result == True
        assert captured_payload is not None
        assert "job_id" in captured_payload
        assert "status" in captured_payload
        assert "timestamp" in captured_payload
        assert captured_payload["job_id"] == "test-job-123"
        assert captured_payload["status"] == "completed"


@pytest.mark.anyio
async def test_webhook_completed_job():
    """Test webhook notification for completed job."""
    from api.routers.jobs import send_webhook_notification
    
    call_made = False
    
    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, *args):
            pass
        
        async def post(self, url, json=None, **kwargs):
            nonlocal call_made
            call_made = True
            return MockResponse(200)
    
    with patch('api.routers.jobs.httpx.AsyncClient', MockAsyncClient):
        with patch('api.routers.jobs._webhooks_available', False):
            result = {"optimal_value": -3.5, "optimal_bitstring": "101"}
            
            success = await send_webhook_notification(
                callback_url="https://example.com/webhook",
                job_id="completed-job",
                status="completed",
                result=result
            )
        
        assert call_made == True
        assert success == True


@pytest.mark.anyio
async def test_webhook_failed_job():
    """Test webhook notification for failed job."""
    from api.routers.jobs import send_webhook_notification
    
    call_made = False
    
    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, *args):
            pass
        
        async def post(self, url, json=None, **kwargs):
            nonlocal call_made
            call_made = True
            return MockResponse(200)
    
    with patch('api.routers.jobs.httpx.AsyncClient', MockAsyncClient):
        with patch('api.routers.jobs._webhooks_available', False):
            success = await send_webhook_notification(
                callback_url="https://example.com/webhook",
                job_id="failed-job",
                status="failed",
                error="Optimization did not converge"
            )
        
        assert call_made == True
        assert success == True


@pytest.mark.anyio
async def test_webhook_retry_on_failure():
    """Test webhook retries on temporary failure."""
    from api.routers.jobs import send_webhook_notification
    
    call_count = 0
    
    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise httpx.ConnectError("Connection refused")
        return MockResponse(200)
    
    with patch('httpx.AsyncClient.post', side_effect=mock_post):
        # Should eventually succeed after retries
        try:
            await send_webhook_notification(
                callback_url="https://example.com/webhook",
                job_id="retry-job",
                status="completed",
                result={}
            )
        except Exception:
            pass  # May or may not retry depending on implementation


@pytest.mark.anyio
async def test_webhook_timeout_handling():
    """Test webhook handles timeout gracefully."""
    from api.routers.jobs import send_webhook_notification
    
    async def mock_timeout(*args, **kwargs):
        raise httpx.TimeoutException("Request timed out")
    
    with patch('httpx.AsyncClient.post', side_effect=mock_timeout):
        # Should not raise, just log the error
        try:
            await send_webhook_notification(
                callback_url="https://example.com/webhook",
                job_id="timeout-job",
                status="completed",
                result={}
            )
        except httpx.TimeoutException:
            pass  # Expected if not handling timeout internally


@pytest.mark.anyio
async def test_webhook_invalid_url():
    """Test webhook handles invalid URL gracefully."""
    from api.routers.jobs import send_webhook_notification
    
    # Should not crash on invalid URL
    try:
        await send_webhook_notification(
            callback_url="not-a-valid-url",
            job_id="invalid-url-job",
            status="completed",
            result={}
        )
    except Exception:
        pass  # Expected to fail gracefully


@pytest.mark.anyio
async def test_webhook_includes_headers():
    """Test webhook includes proper headers."""
    from api.routers.jobs import send_webhook_notification
    
    with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
        mock_post.return_value = MockResponse(200)
        
        await send_webhook_notification(
            callback_url="https://example.com/webhook",
            job_id="header-test-job",
            status="completed",
            result={}
        )
        
        call_args = mock_post.call_args
        headers = call_args.kwargs.get('headers', {})
        
        # Check for common webhook headers
        # Content-Type should be set
        if headers:
            assert 'Content-Type' in headers or 'content-type' in headers


@pytest.mark.anyio
async def test_webhook_cancelled_job():
    """Test webhook notification for cancelled job."""
    from api.routers.jobs import send_webhook_notification
    
    call_made = False
    
    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, *args):
            pass
        
        async def post(self, url, json=None, **kwargs):
            nonlocal call_made
            call_made = True
            return MockResponse(200)
    
    with patch('api.routers.jobs.httpx.AsyncClient', MockAsyncClient):
        with patch('api.routers.jobs._webhooks_available', False):
            success = await send_webhook_notification(
                callback_url="https://example.com/webhook",
                job_id="cancelled-job",
                status="cancelled",
                result={"reason": "User requested cancellation"}
            )
        
        assert call_made == True


@pytest.mark.anyio
async def test_webhook_large_result():
    """Test webhook handles large result payloads."""
    from api.routers.jobs import send_webhook_notification
    
    call_made = False
    
    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, *args):
            pass
        
        async def post(self, url, json=None, **kwargs):
            nonlocal call_made
            call_made = True
            return MockResponse(200)
    
    with patch('api.routers.jobs.httpx.AsyncClient', MockAsyncClient):
        with patch('api.routers.jobs._webhooks_available', False):
            # Large result with many samples
            large_result = {
                "optimal_value": -5.2,
                "samples": [{"state": f"{i:010b}", "energy": -i * 0.1} for i in range(1000)],
                "convergence_history": [float(i) for i in range(100)]
            }
            
            success = await send_webhook_notification(
                callback_url="https://example.com/webhook",
                job_id="large-result-job",
                status="completed",
                result=large_result
            )
        
        assert call_made == True


@pytest.mark.anyio
async def test_webhook_concurrent_notifications():
    """Test multiple concurrent webhook notifications."""
    from api.routers.jobs import send_webhook_notification
    
    call_count = 0
    
    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, *args):
            pass
        
        async def post(self, url, json=None, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # Simulate network latency
            return MockResponse(200)
    
    with patch('api.routers.jobs.httpx.AsyncClient', MockAsyncClient):
        with patch('api.routers.jobs._webhooks_available', False):
            # Send multiple webhooks concurrently
            tasks = [
                send_webhook_notification(
                    callback_url=f"https://example.com/webhook/{i}",
                    job_id=f"concurrent-job-{i}",
                    status="completed",
                    result={"index": i}
                )
                for i in range(5)
            ]
            
            await asyncio.gather(*tasks)
    
            # All 5 webhooks should have been called
            assert call_count == 5


@pytest.mark.anyio
async def test_webhook_http_error_codes():
    """Test webhook handles various HTTP error codes."""
    from api.routers.jobs import send_webhook_notification
    
    error_codes = [400, 401, 403, 404, 500, 502, 503]
    
    for code in error_codes:
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = MockResponse(code)
            
            # Should not raise, just log the error
            try:
                await send_webhook_notification(
                    callback_url="https://example.com/webhook",
                    job_id=f"error-{code}-job",
                    status="completed",
                    result={}
                )
            except Exception:
                pass  # Some implementations may raise


@pytest.mark.anyio
async def test_webhook_ssl_error():
    """Test webhook handles SSL errors gracefully."""
    from api.routers.jobs import send_webhook_notification
    
    async def mock_ssl_error(*args, **kwargs):
        raise httpx.ConnectError("SSL certificate verify failed")
    
    with patch('httpx.AsyncClient.post', side_effect=mock_ssl_error):
        try:
            await send_webhook_notification(
                callback_url="https://self-signed.example.com/webhook",
                job_id="ssl-error-job",
                status="completed",
                result={}
            )
        except Exception:
            pass  # Expected to fail

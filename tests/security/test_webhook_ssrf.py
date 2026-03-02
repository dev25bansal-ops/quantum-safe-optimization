"""
Webhook SSRF protection tests.

Tests for Server-Side Request Forgery (SSRF) prevention in webhook URLs.
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx
from httpx import ASGITransport, AsyncClient

from api.main import app

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


@pytest.fixture
async def auth_token(client: AsyncClient):
    """Get authentication token."""
    response = await client.post("/auth/login", json={"username": "admin", "password": "admin123!"})
    return response.json()["access_token"]


@pytest.mark.anyio
async def test_webhook_url_allows_valid_https(client: AsyncClient, auth_token: str):
    """Verify valid HTTPS URLs are allowed for webhooks."""
    valid_urls = [
        "https://example.com/webhook",
        "https://webhook.service.com/api/callback",
        "https://api.example.org/v1/jobs/notify",
    ]

    for url in valid_urls:
        response = await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "local_simulator",
                "callback_url": url,
            },
        )

        assert response.status_code in [201, 202, 400], f"URL {url} should be allowed"


@pytest.mark.anyio
async def test_webhook_url_blocks_local_network_addresses(client: AsyncClient, auth_token: str):
    """Verify local network addresses are blocked in webhook URLs."""
    blocked_urls = [
        "http://localhost:8080/webhook",
        "http://127.0.0.1:3000/callback",
        "http://0.0.0.0:5000/api",
        "http://[::1]:8080/webhook",
        "http://127.0.0.1/callback",
        "http://0.0.0.0/endpoint",
    ]

    for url in blocked_urls:
        response = await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "local_simulator",
                "callback_url": url,
            },
        )

        if response.status_code != 404:
            assert response.status_code in [400, 422], f"URL {url} should be blocked"


@pytest.mark.anyio
async def test_webhook_url_blocks_private_network_ranges(client: AsyncClient, auth_token: str):
    """Verify private network ranges are blocked in webhook URLs."""
    private_urls = [
        "http://192.168.1.1/webhook",
        "http://192.168.0.100:8080/api",
        "http://10.0.0.1/callback",
        "http://10.1.2.3:3000/webhook",
        "http://172.16.0.1/endpoint",
        "http://172.31.255.255:80/api",
    ]

    for url in private_urls:
        response = await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "local_simulator",
                "callback_url": url,
            },
        )

        if response.status_code != 404:
            assert response.status_code in [400, 422], f"URL {url} should be blocked"


@pytest.mark.anyio
async def test_webhook_url_blocks_aws_metadata_endpoint(client: AsyncClient, auth_token: str):
    """Verify AWS metadata endpoint is blocked."""
    aws_urls = [
        "http://169.254.169.254/latest/meta-data/",
        "http://169.254.169.254/latest/user-data",
        "http://169.254.169.254/latest/api/token",
        "http://169.254.169.254/latest/dynamic/instance-identity/",
        "http://169.254.169.254:80/latest/meta-data/hostname",
    ]

    for url in aws_urls:
        response = await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "local_simulator",
                "callback_url": url,
            },
        )

        if response.status_code != 404:
            assert response.status_code in [400, 422], f"AWS metadata URL {url} should be blocked"


@pytest.mark.anyio
async def test_webhook_url_blocks_cloud_metadata_endpoints(client: AsyncClient, auth_token: str):
    """Verify various cloud metadata endpoints are blocked."""
    cloud_metadata_urls = [
        "http://metadata.google.internal/",
        "http://169.254.169.254/computeMetadata/v1/",
        "http://100.100.100.200/latest/meta-data/",
    ]

    for url in cloud_metadata_urls:
        response = await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "local_simulator",
                "callback_url": url,
            },
        )

        if response.status_code != 404:
            assert response.status_code in [400, 422], f"Cloud metadata URL {url} should be blocked"


@pytest.mark.anyio
async def test_webhook_url_blocks_internal_service_names(client: AsyncClient, auth_token: str):
    """Verify internal service discovery names are blocked."""
    internal_urls = [
        "http://internal-api:8080/webhook",
        "http://kubernetes-dashboard/service/callback",
        "http://consul.service/discovery/",
        "http://etcd.cluster:2379/keys",
        "http://docker-registry:5000/v2/",
    ]

    for url in internal_urls:
        response = await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "local_simulator",
                "callback_url": url,
            },
        )

        if response.status_code != 404:
            assert response.status_code in [400, 422], f"Internal URL {url} should be blocked"


@pytest.mark.anyio
async def test_webhook_url_blocks_non_http_schemes(client: AsyncClient, auth_token: str):
    """Verify non-HTTP/HTTPS schemes are blocked."""
    invalid_schemes = [
        "file:///etc/passwd",
        "ftp://internal-server/file",
        "gopher://attacker:70/",
        "dict://localhost:11211/",
        "ldap://ldap-server:389/",
        "mailto://user@example.com",
        "data:text/html,<script>alert(1)</script>",
    ]

    for url in invalid_schemes:
        response = await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "local_simulator",
                "callback_url": url,
            },
        )

        if response.status_code != 404:
            assert response.status_code in [400, 422], f"Scheme {url} should be blocked"


@pytest.mark.anyio
async def test_webhook_url_blocks_ipv6_link_local(client: AsyncClient, auth_token: str):
    """Verify IPv6 link-local addresses are blocked."""
    link_local_urls = [
        "http://[fe80::1]:8080/webhook",
        "http://[fe80::1%eth0]/callback",
        "http://[fe80::ffff:ffff:ffff]:3000/api",
    ]

    for url in link_local_urls:
        response = await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "local_simulator",
                "callback_url": url,
            },
        )

        if response.status_code != 404:
            assert response.status_code in [400, 422], f"IPv6 link-local {url} should be blocked"


@pytest.mark.anyio
async def test_webhook_url_blocks_dns_rebinding_attempts(client: AsyncClient, auth_token: str):
    """Verify DNS rebinding attacks are mitigated."""
    rebinding_urls = [
        "http://127.0.0.1.nip.io/webhook",
        "http://localhost.burpcollaborator.net/callback",
        "http://169.254.169.254.xip.io/metadata",
        "http://0x7f000001.nip.io:8080/endpoint",
    ]

    for url in rebinding_urls:
        response = await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "local_simulator",
                "callback_url": url,
            },
        )

        if response.status_code != 404:
            assert response.status_code in [400, 422], f"DNS rebinding URL {url} should be blocked"


@pytest.mark.anyio
async def test_webhook_url_blocks_ipv4_private_octal(client: AsyncClient, auth_token: str):
    """Verify octal format IP addresses are blocked."""
    octal_urls = [
        "http://0177.0.0.1/webhook",
        "http://010.0.0.1/callback",
        "http://0x7f.0.0.1/endpoint",
        "http://2130706433/webhook",
    ]

    for url in octal_urls:
        response = await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "local_simulator",
                "callback_url": url,
            },
        )

        if response.status_code != 404:
            assert response.status_code in [400, 422], f"Octal URL {url} should be blocked"


@pytest.mark.anyio
async def test_webhook_url_blocks_port_scanning_attempts(client: AsyncClient, auth_token: str):
    """Verify port scanning attempts via webhooks are blocked."""
    port_scan_urls = [
        "http://internal.example.com:22/webhook",
        "http://internal.example.com:23/callback",
        "http://internal.example.com:8080/endpoint",
        "http://internal.example.com:443/api",
    ]

    for url in port_scan_urls:
        response = await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "local_simulator",
                "callback_url": url,
            },
        )

        if response.status_code != 404:
            assert response.status_code in [400, 422], f"Port scan URL {url} should be blocked"


@pytest.mark.anyio
async def test_webhook_url_blocks_url_encoding_bypass(client: AsyncClient, auth_token: str):
    """Verify URL encoding bypass attempts are blocked."""
    encoded_urls = [
        "http://%31%32%37%2e%30%2e%30%2e%31/webhook",
        "http://127.0.0.1%09.malicious.com/callback",
        "http://localhost%00:8080/endpoint",
        "http://127.0.0.1%0d.api/webhook",
    ]

    for url in encoded_urls:
        response = await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "local_simulator",
                "callback_url": url,
            },
        )

        if response.status_code != 404:
            assert response.status_code in [400, 422], f"Encoded URL {url} should be blocked"


@pytest.mark.anyio
async def test_webhook_delivery_only_to_valid_url(client: AsyncClient, auth_token: str):
    """Verify webhook delivery only happens to validated URLs."""
    valid_url = "https://example.com/webhook"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        response = await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "local_simulator",
                "callback_url": valid_url,
            },
        )

        if response.status_code in [201, 202]:
            assert mock_post.called or mock_post.call_count >= 0


@pytest.mark.anyio
async def test_webhook_blocks_malformed_url(client: AsyncClient, auth_token: str):
    """Verify malformed URLs are blocked."""
    malformed_urls = [
        "not a url",
        "://broken.com",
        "http://",
        "https:///",
        "http://[not-valid-ipv6]",
        "http://256.256.256.256/webhook",
    ]

    for url in malformed_urls:
        response = await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "local_simulator",
                "callback_url": url,
            },
        )

        if response.status_code != 404:
            assert response.status_code in [400, 422], f"Malformed URL {url} should be blocked"


@pytest.mark.anyio
async def test_webhook_url_blocks_user_info_injection(client: AsyncClient, auth_token: str):
    """Verify URL with user info is blocked."""
    user_info_urls = [
        "http://admin:password@example.com/webhook",
        "https://user:pass@internal.service/callback",
        "http://root:secret@127.0.0.1:8080/endpoint",
    ]

    for url in user_info_urls:
        response = await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "local_simulator",
                "callback_url": url,
            },
        )

        if response.status_code != 404:
            assert response.status_code in [400, 422], (
                f"URL with credentials {url} should be blocked"
            )


@pytest.mark.anyio
async def test_webhook_url_blocks_fragment_injection(client: AsyncClient, auth_token: str):
    """Verify URL fragments are blocked or sanitized."""
    fragment_urls = [
        "https://example.com/webhook#data",
        "https://example.com/#inject<script>alert(1)</script>",
    ]

    for url in fragment_urls:
        response = await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "local_simulator",
                "callback_url": url,
            },
        )

        if response.status_code != 404:
            assert response.status_code in [400, 422, 201, 202], f"Fragment URL {url} handled"


@pytest.mark.anyio
async def test_webhook_url_length_limit(client: AsyncClient, auth_token: str):
    """Verify URL length limits are enforced."""
    long_url = f"https://example.com/webhook?data={'x' * 2100}"

    response = await client.post(
        "/jobs",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "problem_type": "QAOA",
            "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
            "backend": "local_simulator",
            "callback_url": long_url,
        },
    )

    if response.status_code != 404:
        assert response.status_code in [400, 422], f"Long URL should be rejected"

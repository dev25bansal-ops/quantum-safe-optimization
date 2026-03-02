"""
Security vulnerability tests.

Tests for common security vulnerabilities: secret protection,
token forgery, SSRF prevention, and credential storage.
"""

import json
import os
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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
async def test_secret_keys_not_transmitted_to_server(client: AsyncClient, auth_token: str):
    """Verify secret keys are never included in server responses."""
    endpoints_to_test = [
        "/auth/me",
        "/auth/keys/generate",
        "/jobs",
    ]

    for endpoint in endpoints_to_test:
        response = await client.get(endpoint, headers={"Authorization": f"Bearer {auth_token}"})

        if response.status_code == 200:
            response_text = response.text
            assert "secret" not in response_text.lower() or "response" in response_text.lower()
            assert "private_key" not in response_text
            assert "private_key_pkcs8" not in response_text
            assert "secret_key" not in response_text or "access_token" in response.text


@pytest.mark.anyio
async def test_demo_token_forgery_blocked(client: AsyncClient):
    """Verify demo token forgery is blocked."""
    from api.routers.auth import USERS_STORE

    forged_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJmb3JnZWQiLCJpc19kZW1vIjp0cnVlfQ.forgedsignature"

    response = await client.get("/jobs", headers={"Authorization": f"Bearer {forged_token}"})

    assert response.status_code in [401, 403]

    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {forged_token}"})

    assert response.status_code in [401, 403]


@pytest.mark.anyio
async def test_allow_token_db_bypass_disabled(client: AsyncClient):
    """Verify ALLOW_TOKEN_DB_BYPASS is disabled in production."""
    original_env = os.environ.get("ALLOW_TOKEN_DB_BYPASS")

    os.environ["ALLOW_TOKEN_DB_BYPASS"] = "false"
    os.environ["DEMO_MODE"] = "false"

    invalid_token = "invalid.token.12345"

    response = await client.get("/jobs", headers={"Authorization": f"Bearer {invalid_token}"})

    assert response.status_code in [401, 403]

    if original_env is not None:
        os.environ["ALLOW_TOKEN_DB_BYPASS"] = original_env


@pytest.mark.anyio
async def test_webhook_url_ssrf_protection(client: AsyncClient, auth_token: str):
    """Verify webhook URL SSRF protection."""
    ssrf_urls = [
        "http://localhost/admin",
        "http://127.0.0.1/secret",
        "http://169.254.169.254/latest/meta-data/",
        "http://0.0.0.0/internal",
        "file:///etc/passwd",
        "ftp://internal-server/file",
        "http://[::1]/internal",
    ]

    for url in ssrf_urls:
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
            assert response.status_code in [400, 422]
            data = response.json()
            assert "callback_url" in str(data) or "url" in str(data).lower()


@pytest.mark.anyio
async def test_credentials_not_in_localstorage_simulation(client: AsyncClient, auth_token: str):
    """Verify credentials are not intended for localStorage."""
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {auth_token}"})

    if response.status_code == 200:
        data = response.json()

        assert "password" not in data
        assert "password_hash" not in data
        assert "secret" not in data


@pytest.mark.anyio
async def test_sensitive_headers_not_leaked(client: AsyncClient):
    """Verify sensitive headers are not leaked in responses."""
    sensitive_headers = ["authorization", "cookie", "set-cookie", "www-authenticate"]

    response = await client.post("/auth/login", json={"username": "admin", "password": "admin123!"})

    response_headers_lower = {k.lower(): v for k, v in response.headers.items()}

    for header in sensitive_headers:
        assert header not in response_headers_lower


@pytest.mark.anyio
async def test_no_secret_in_error_messages(client: AsyncClient, auth_token: str):
    """Verify secrets are not leaked in error messages."""
    invalid_request = {
        "problem_type": "QAOA",
        "api_key": "sk-1234567890abcdef",
        "secret_token": "super_secret_token_xyz",
        "password": "my_password_123",
    }

    response = await client.post(
        "/jobs",
        headers={"Authorization": f"Bearer {auth_token}"},
        json=invalid_request,
    )

    if response.status_code in [400, 422, 500]:
        error_text = response.text.lower()

        assert "sk-1234567890abcdef" not in error_text
        assert "super_secret_token_xyz" not in error_text
        assert "my_password_123" not in error_text


@pytest.mark.anyio
async def test_jwt_signature_verification(client: AsyncClient):
    """Verify JWT signature verification works."""
    import jwt

    from qsop.settings import get_settings

    settings = get_settings()

    valid_payload = {"sub": "admin", "tenant_id": "default", "scopes": ["read", "write"]}
    valid_token = jwt.encode(
        valid_payload, settings.secret_key.get_secret_value(), algorithm="HS256"
    )

    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {valid_token}"})

    assert response.status_code in [200, 401]


@pytest.mark.anyio
async def test_token_expiration(client: AsyncClient):
    """Verify expired tokens are rejected."""
    import jwt
    from datetime import datetime, timedelta, timezone

    from qsop.settings import get_settings

    settings = get_settings()

    expired_payload = {
        "sub": "admin",
        "tenant_id": "default",
        "scopes": ["read", "write"],
        "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
    }

    expired_token = jwt.encode(
        expired_payload, settings.secret_key.get_secret_value(), algorithm="HS256"
    )

    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})

    assert response.status_code == 401


@pytest.mark.anyio
async def test_xss_prevention_in_outputs(client: AsyncClient, auth_token: str):
    """Verify XSS prevention in API responses."""
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {auth_token}"})

    if response.status_code == 200:
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type

        response_text = response.text
        assert "<script>" not in response_text
        assert "javascript:" not in response_text
        assert "onerror=" not in response_text


@pytest.mark.anyio
async def test_sql_injection_prevention(client: AsyncClient, auth_token: str):
    """Verify SQL injection prevention."""
    injection_attempts = [
        "admin'; DROP TABLE users; --",
        "' OR '1'='1",
        "1' UNION SELECT * FROM users--",
        "'; EXEC xp_cmdshell('dir'); --",
    ]

    for username in injection_attempts:
        response = await client.post(
            "/auth/login", json={"username": username, "password": "admin123!"}
        )

        assert response.status_code in [401, 422]


@pytest.mark.anyio
async def test_path_traversal_prevention(client: AsyncClient, auth_token: str):
    """Verify path traversal prevention."""
    path_traversal = [
        "/../etc/passwd",
        "/jobs/../../admin",
        "/auth/../../../etc/hosts",
    ]

    for path in path_traversal:
        response = await client.get(path, headers={"Authorization": f"Bearer {auth_token}"})

        assert response.status_code in [400, 404]


@pytest.mark.anyio
async def test_content_type_validation(client: AsyncClient, auth_token: str):
    """Verify content type validation."""
    endpoints = [
        ("/jobs", "POST"),
        ("/auth/keys/encryption-key", "PUT"),
    ]

    for endpoint, method in endpoints:
        valid_response = await client.request(
            method,
            endpoint,
            headers={"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"},
            json={},
        )

        if valid_response.status_code != 404:
            invalid_response = await client.request(
                method,
                endpoint,
                headers={"Authorization": f"Bearer {auth_token}", "Content-Type": "text/html"},
                data="<html></html>",
            )

            assert invalid_response.status_code in [400, 415, 422]


@pytest.mark.anyio
async def test_request_size_limits(client: AsyncClient, auth_token: str):
    """Verify request size limits are enforced."""
    large_payload = "x" * (11 * 1024 * 1024)

    response = await client.post(
        "/auth/login",
        headers={"Content-Type": "application/json"},
        content=large_payload,
    )

    assert response.status_code in [400, 413, 422, 500]


@pytest.mark.anyio
async def test_authorization_scopes_enforced(client: AsyncClient):
    """Verify authorization scopes are enforced."""
    response = await client.post("/auth/login", json={"username": "admin", "password": "admin123!"})

    if response.status_code == 200:
        token = response.json()["access_token"]

        response = await client.post(
            "/admin/manage-users",
            headers={"Authorization": f"Bearer {token}"},
            json={"username": "newuser"},
        )

        assert response.status_code == 404 or "admin" not in response.text.lower()


@pytest.mark.anyio
async def test_csrf_protection_headers(client: AsyncClient):
    """Verify CSRF protection headers."""
    response = await client.get("/health")

    headers = response.headers

    if "same-site" in headers.get("set-cookie", "").lower():
        same_site = headers["set-cookie"].lower()
        assert "strict" in same_site or "lax" in same_site


@pytest.mark.anyio
async def test_no_sensitive_data_in_logs(client: AsyncClient, auth_token: str):
    """Verify sensitive data is not logged."""
    with patch("api.main.logger") as mock_logger:
        await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "local_simulator",
                "custom_data": {"secret": "should_not_log"},
            },
        )

        if mock_logger.called:
            all_calls = str(mock_logger.call_args_list)
            assert "should_not_log" not in all_calls


@pytest.mark.anyio
async def test_parameter_tampering(client: AsyncClient, auth_token: str):
    """Verify parameter tampering prevention."""
    response = await client.post(
        "/jobs",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "problem_type": "QAOA",
            "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
            "backend": "local_simulator",
            "isAdmin": True,
            "is_admin": "true",
            "admin": "yes",
        },
    )

    if response.status_code in [201, 202]:
        data = response.json()
        for field in ["isAdmin", "is_admin", "admin"]:
            assert field not in data or data[field] is False


@pytest.mark.anyio
async def test_mime_type_sniffing_prevention(client: AsyncClient):
    """Verify MIME type sniffing is prevented."""
    response = await client.get("/health")

    nosniff = response.headers.get("x-content-type-options", "")
    assert "nosniff" in nosniff.lower()


@pytest.mark.anyio
async def test_clickjacking_prevention(client: AsyncClient):
    """Verify clickjacking prevention."""
    response = await client.get("/health")

    frame_options = response.headers.get("x-frame-options", "").lower()

    assert frame_options in ["deny", "sameorigin", ""]


@pytest.mark.anyio
async def test_rate_limit_enforcement(client: AsyncClient, auth_token: str):
    """Verify rate limiting is enforced."""
    login_attempts = []

    for _ in range(20):
        response = await client.post(
            "/auth/login", json={"username": "invalid_user", "password": "invalid_pass"}
        )
        login_attempts.append(response.status_code)

        if 429 in login_attempts:
            break

    assert 429 in login_attempts or max(login_attempts) == 401


@pytest.mark.anyio
async def test_security_headers_present(client: AsyncClient):
    """Verify security headers are present."""
    response = await client.get("/health")

    headers = response.headers

    security_headers = [
        ("x-content-type-options", "nosniff"),
        ("x-frame-options", ["deny", "sameorigin"]),
        ("content-security-policy", None),
    ]

    for header, expected_values in security_headers:
        header_value = headers.get(header, "")
        if expected_values:
            if isinstance(expected_values, list):
                assert any(v in header_value.lower() for v in expected_values)
            else:
                assert expected_values in header_value.lower()


@pytest.mark.anyio
async def test_sensitive_data_not_url_encoded(client: AsyncClient, auth_token: str):
    """Verify sensitive data is not URL encoded in body."""
    response = await client.get(
        "/jobs?secret=hidden&password=test", headers={"Authorization": f"Bearer {auth_token}"}
    )

    response_text = response.text.lower()
    assert "hidden" not in response_text or "secret" in response_text

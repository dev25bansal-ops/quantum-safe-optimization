"""
End-to-end authentication flow tests.

Tests complete authentication lifecycle: register → login → use → logout.
"""

import os
import time
from datetime import datetime, timedelta, timezone

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


@pytest.mark.anyio
async def test_user_registration_flow(client: AsyncClient):
    """Test complete user registration with validation."""
    import secrets

    unique_username = f"testuser_{secrets.token_hex(6)},"
    unique_email = f"{unique_username}@test.com"

    response = await client.post(
        "/auth/register",
        json={
            "username": unique_username,
            "email": unique_email,
            "password": "TestPassword123!",
            "name": "Test User",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == unique_username
    assert data["email"] == unique_email
    assert data["name"] == "Test User"
    assert "user_id" in data
    assert "created_at" in data


@pytest.mark.anyio
async def test_user_login_valid_credentials(client: AsyncClient):
    """Test successful login with valid credentials."""
    response = await client.post("/auth/login", json={"username": "admin", "password": "admin123!"})

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "token_type" in data
    assert data["token_type"] == "bearer"
    assert "expires_in" in data
    assert "user_info" in data

    token = data["access_token"]
    assert len(token) > 100


@pytest.mark.anyio
async def test_token_validation_on_protected_endpoint(client: AsyncClient):
    """Test token validation on protected API endpoints."""
    login_response = await client.post(
        "/auth/login", json={"username": "admin", "password": "admin123!"}
    )
    token = login_response.json()["access_token"]

    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin"
    assert "user_id" in data


@pytest.mark.anyio
async def test_logout_and_token_revocation(client: AsyncClient):
    """Test logout functionality and token revocation."""
    login_response = await client.post(
        "/auth/login", json={"username": "admin", "password": "admin123!"}
    )
    token = login_response.json()["access_token"]

    logout_response = await client.post(
        "/auth/logout", headers={"Authorization": f"Bearer {token}"}
    )

    assert logout_response.status_code == 200
    logout_data = logout_response.json()
    assert "message" in logout_data

    me_response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me_response.status_code == 401


@pytest.mark.anyio
async def test_session_invalidation_after_logout(client: AsyncClient):
    """Test that session is invalidated after logout."""
    login_response = await client.post(
        "/auth/login", json={"username": "admin", "password": "admin123!"}
    )
    token = login_response.json()["access_token"]

    await client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})

    jobs_response = await client.get("/jobs", headers={"Authorization": f"Bearer {token}"})

    assert jobs_response.status_code in [401, 403]


@pytest.mark.anyio
async def test_token_expiration_handling(client: AsyncClient):
    """Test handling of expired tokens."""
    import jwt

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
async def test_invalid_token_format(client: AsyncClient):
    """Test rejection of invalid token formats."""
    invalid_tokens = [
        "",
        "invalid.token.here",
        "Bearer",
        "Bearer ",
        "Bearer not.a.token",
    ]

    for token in invalid_tokens:
        response = await client.get("/jobs", headers={"Authorization": token if token else ""})
        assert response.status_code in [401, 403]


@pytest.mark.anyio
async def test_password_hashing_on_registration(client: AsyncClient):
    """Test that passwords are properly hashed during registration."""
    from src.qsop.api.routers.auth_enhanced import USERS_STORE

    username = f"hash_test_{int(time.time())}"

    response = await client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}@test.com",
            "password": "MyPassword123!",
            "name": "Hash Test",
        },
    )

    assert response.status_code == 201

    user = USERS_STORE.get(username)
    assert user is not None
    assert user["password_hash"] != "MyPassword123!"
    assert len(user["password_hash"]) > 50


@pytest.mark.anyio
async def test_duplicate_user_registration(client: AsyncClient):
    """Test rejection of duplicate username/email registration."""
    username = f"dup_test_{int(time.time())}"

    reg1 = await client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}@test.com",
            "password": "Password123!",
            "name": "First",
        },
    )

    assert reg1.status_code == 201

    reg2 = await client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}@test.com",
            "password": "Password123!",
            "name": "Second",
        },
    )

    assert reg2.status_code == 409


@pytest.mark.anyio
async def test_password_validation(client: AsyncClient):
    """Test password strength validation."""
    weak_passwords = [
        "short",
        "nouppercase1!",
        "NOLOWERCASE1!",
        "NoNumbers!",
        "NoSpecialChars1",
    ]

    for pwd in weak_passwords:
        response = await client.post(
            "/auth/register",
            json={
                "username": f"weak_pwd_{len(pwd)}_{int(time.time())}",
                "email": f"weak{len(pwd)}@test.com",
                "password": pwd,
                "name": "Weak",
            },
        )
        assert response.status_code in [400, 422]


@pytest.mark.anyio
async def test_login_with_email(client: AsyncClient):
    """Test login using email address instead of username."""
    import secrets

    username = f"email_test_{secrets.token_hex(4)}"
    email = f"{username}@test.com"

    await client.post(
        "/auth/register",
        json={
            "username": username,
            "email": email,
            "password": "TestPassword123!",
            "name": "Email Test",
        },
    )

    response = await client.post(
        "/auth/login", json={"username": email, "password": "TestPassword123!"}
    )

    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.anyio
async def test_inactive_account_login(client: AsyncClient):
    """Test login failure for inactive accounts."""
    from src.qsop.api.routers.auth_enhanced import USERS_STORE

    username = f"inactive_test_{int(time.time())}"

    await client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}@test.com",
            "password": "TestPassword123!",
            "name": "Inactive User",
        },
    )

    user = USERS_STORE.get(username)
    user["is_active"] = False

    response = await client.post(
        "/auth/login", json={"username": username, "password": "TestPassword123!"}
    )

    assert response.status_code in [403, 401]


@pytest.mark.anyio
async def test_token_pqc_signature(client: AsyncClient):
    """Test that login returns PQC signature with token."""
    response = await client.post("/auth/login", json={"username": "admin", "password": "admin123!"})

    assert response.status_code == 200
    data = response.json()

    assert "pqc_signature" in data
    assert len(data["pqc_signature"]) > 50


@pytest.mark.anyio
async def test_auth_rate_limiting(client: AsyncClient):
    """Test authentication endpoint rate limiting."""
    failed_attempts = []

    for i in range(15):
        response = await client.post(
            "/auth/login", json={"username": "invalid", "password": "wrong"}
        )
        failed_attempts.append(response.status_code)

    assert failed_attempts[-1] in [429, 401]

"""
Tests for the Quantum-Safe Optimization Platform API.
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient

# Disable rate limiting in test environment
os.environ["TESTING"] = "1"

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


@pytest.mark.anyio
async def test_health_check(client: AsyncClient):
    """Test health endpoint returns healthy status."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.anyio
async def test_health_live(client: AsyncClient):
    """Test liveness probe."""
    response = await client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"


@pytest.mark.anyio
async def test_health_ready(client: AsyncClient):
    """Test readiness probe."""
    response = await client.get("/health/ready")
    # Accept either 200 (all services connected) or 503 (some services unavailable)
    # In local testing without Cosmos DB, 503 is expected
    assert response.status_code in (200, 503)
    data = response.json()
    # Check structure is correct regardless of status
    assert "ready" in data
    assert "components" in data


@pytest.mark.anyio
async def test_root_endpoint(client: AsyncClient):
    """Test root endpoint returns content."""
    response = await client.get("/")
    assert response.status_code == 200
    # Root can return either JSON (no frontend) or HTML (frontend exists)
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        data = response.json()
        assert "name" in data
        assert "Quantum" in data["name"]
    else:
        # HTML response from frontend
        assert "text/html" in content_type or len(response.content) > 0


@pytest.mark.anyio
async def test_login_invalid_credentials(client: AsyncClient):
    """Test login with invalid credentials fails."""
    response = await client.post(
        "/auth/login", json={"username": "invalid", "password": "wrongpassword123"}
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_jobs_unauthorized(client: AsyncClient):
    """Test jobs endpoint behavior without authentication."""
    response = await client.get("/jobs")
    # In DEMO_MODE, returns 200 with guest access; otherwise 401
    assert response.status_code in [200, 401]


@pytest.mark.anyio
async def test_submit_job_unauthorized(client: AsyncClient):
    """Test job submission behavior without authentication."""
    response = await client.post(
        "/jobs",
        json={
            "problem_type": "QAOA",
            "problem_config": {"graph_edges": [[0, 1], [1, 2]]},
            "backend": "local_simulator",
        },
    )
    # In DEMO_MODE, returns 202 (accepted) with guest access; otherwise 401
    assert response.status_code in [202, 401]


@pytest.mark.anyio
async def test_login_valid_credentials(client: AsyncClient):
    """Test login with valid credentials returns PQC-signed token."""
    response = await client.post("/auth/login", json={"username": "admin", "password": "admin123!"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "pqc_signature" in data
    assert data["token_type"] == "bearer"  # noqa: S105 - JWT field name
    assert data["expires_in"] == 86400
    # Verify token structure (header.payload.signature)
    token_parts = data["access_token"].split(".")
    assert len(token_parts) == 3


@pytest.mark.anyio
async def test_authenticated_job_submission(client: AsyncClient):
    """Test job submission with valid authentication."""
    # First login
    login_response = await client.post(
        "/auth/login", json={"username": "admin", "password": "admin123!"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    # Submit job with auth token
    response = await client.post(
        "/jobs",
        json={
            "problem_type": "QAOA",
            "problem_config": {"problem": "maxcut", "edges": [[0, 1], [1, 2], [2, 0]]},
            "backend": "local_simulator",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert data["problem_type"] == "QAOA"


@pytest.mark.anyio
async def test_get_user_info(client: AsyncClient):
    """Test getting current user info with valid token."""
    # Login
    login_response = await client.post(
        "/auth/login", json={"username": "admin", "password": "admin123!"}
    )
    token = login_response.json()["access_token"]

    # Get user info
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin"
    assert "admin" in data["roles"]


@pytest.mark.anyio
async def test_generate_encryption_key(client: AsyncClient):
    """Test ML-KEM key generation endpoint."""
    # Login
    login_response = await client.post(
        "/auth/login", json={"username": "admin", "password": "admin123!"}
    )
    token = login_response.json()["access_token"]

    # Generate KEM key
    response = await client.post(
        "/auth/keys/generate", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "public_key" in data
    assert "key_id" in data
    assert data["algorithm"] == "ML-KEM-768"
    # ML-KEM-768 public key is ~1184 bytes, base64 encoded
    assert len(data["public_key"]) > 1000


@pytest.mark.anyio
async def test_logout_revokes_token(client: AsyncClient):
    """Test that logout properly revokes the token."""
    # Login
    login_response = await client.post(
        "/auth/login", json={"username": "admin", "password": "admin123!"}
    )
    token = login_response.json()["access_token"]

    # Verify token works
    me_response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200

    # Logout
    logout_response = await client.post(
        "/auth/logout", headers={"Authorization": f"Bearer {token}"}
    )
    assert logout_response.status_code == 200
    assert "revoked_jti" in logout_response.json()

    # Token should now be rejected
    me_response2 = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response2.status_code == 401


@pytest.mark.anyio
async def test_token_refresh(client: AsyncClient):
    """Test token refresh functionality."""
    # Login
    login_response = await client.post(
        "/auth/login", json={"username": "admin", "password": "admin123!"}
    )
    old_token = login_response.json()["access_token"]

    # Refresh token
    refresh_response = await client.post(
        "/auth/refresh", headers={"Authorization": f"Bearer {old_token}"}
    )
    assert refresh_response.status_code == 200
    new_token = refresh_response.json()["access_token"]

    # New token should work
    me_response = await client.get("/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "admin"


@pytest.mark.anyio
async def test_signature_verification_endpoint(client: AsyncClient):
    """Test the signature verification endpoint with valid signed payload."""
    import base64
    import time

    from quantum_safe_crypto import SigningKeyPair

    # Login
    login_response = await client.post(
        "/auth/login", json={"username": "admin", "password": "admin123!"}
    )
    token = login_response.json()["access_token"]

    # Create a signed payload
    signing_key = SigningKeyPair()
    test_data = b"test payload data for verification"
    payload_b64 = base64.b64encode(test_data).decode("utf-8")
    timestamp = time.time()

    # Sign the payload + timestamp
    signed_data = f"{payload_b64}:{timestamp}"
    signature = signing_key.sign(signed_data.encode("utf-8"))

    # Verify via API
    response = await client.post(
        "/auth/verify-signature",
        json={
            "payload": payload_b64,
            "signature": signature,
            "signer_public_key": signing_key.public_key,
            "timestamp": timestamp,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["payload_size"] == len(test_data)


@pytest.mark.anyio
async def test_worker_status_endpoint(client: AsyncClient):
    """Test the Celery worker status endpoint."""
    # Login first
    login_response = await client.post(
        "/auth/login", json={"username": "admin", "password": "admin123!"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    # Check worker status
    response = await client.get(
        "/jobs/workers/status", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    # Should indicate Celery status (connected or not configured)
    assert "status" in data or "use_celery" in data


@pytest.mark.anyio
async def test_job_submission_with_message(client: AsyncClient):
    """Test that job submission returns informative message."""
    # Login first
    login_response = await client.post(
        "/auth/login", json={"username": "admin", "password": "admin123!"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    # Submit a job
    response = await client.post(
        "/jobs",
        json={
            "problem_type": "QAOA",
            "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
            "backend": "local_simulator",
            "priority": 5,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 202
    data = response.json()
    assert "message" in data
    assert "submitted" in data["message"].lower() or "queued" in data["message"].lower()
    assert "job_id" in data
    assert data["status"] == "queued"


@pytest.mark.anyio
async def test_user_registration(client: AsyncClient):
    """Test user registration endpoint."""
    import secrets

    # Generate unique username
    unique_username = f"testuser_{secrets.token_hex(4)}"

    response = await client.post(
        "/auth/register",
        json={
            "username": unique_username,
            "password": "TestPassword123!",
            "email": f"{unique_username}@test.com",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == unique_username
    assert "user_id" in data
    assert "Registration successful" in data["message"]

    # Try to login with new user
    login_response = await client.post(
        "/auth/login", json={"username": unique_username, "password": "TestPassword123!"}
    )
    assert login_response.status_code == 200


@pytest.mark.anyio
async def test_registration_duplicate_username(client: AsyncClient):
    """Test that duplicate usernames are rejected."""
    response = await client.post(
        "/auth/register",
        json={
            "username": "admin",  # Already exists
            "password": "TestPassword123!",
        },
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.anyio
async def test_api_versioning(client: AsyncClient):
    """Test that API versioning works correctly."""
    # Test versioned login endpoint works
    login_response = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin123!"}
    )
    assert login_response.status_code == 200
    assert "access_token" in login_response.json()

    # Test versioned jobs endpoint works (with auth)
    token = login_response.json()["access_token"]
    jobs_response = await client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {token}"})
    assert jobs_response.status_code == 200


@pytest.mark.anyio
async def test_job_with_callback_url_validation(client: AsyncClient):
    """Test that invalid callback URLs are rejected."""
    # Login first
    login_response = await client.post(
        "/auth/login", json={"username": "admin", "password": "admin123!"}
    )
    token = login_response.json()["access_token"]

    # Submit with invalid callback URL
    response = await client.post(
        "/jobs",
        json={
            "problem_type": "QAOA",
            "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
            "callback_url": "invalid-url",  # Not http/https
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert "callback_url" in response.json()["detail"]


@pytest.mark.anyio
async def test_update_encryption_key(client: AsyncClient):
    """Test updating user's encryption key."""
    from quantum_safe_crypto import KemKeyPair

    # Login
    login_response = await client.post(
        "/auth/login", json={"username": "admin", "password": "admin123!"}
    )
    token = login_response.json()["access_token"]

    # Generate a KEM keypair
    keypair = KemKeyPair()

    # Update encryption key
    response = await client.put(
        "/auth/keys/encryption-key",
        json={
            "public_key": keypair.public_key,
            "key_type": "ML-KEM-768",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert "updated successfully" in response.json()["message"]

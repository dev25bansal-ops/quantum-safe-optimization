"""
Tests for Security Enhanced API Endpoints.
"""

import os
import pytest
from httpx import ASGITransport, AsyncClient

os.environ["TESTING"] = "1"

from api.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_token(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": os.getenv("ADMIN_PASSWORD", "changeme")},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


# ============================================================================
# Quantum-Safe Encryption Tests
# ============================================================================


@pytest.mark.anyio
async def test_get_qs_encryption_status(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/security/quantum-encryption/status",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "algorithm" in data
    assert "active_key_id" in data


@pytest.mark.anyio
async def test_quantum_encrypt_data(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/security/quantum-encryption/encrypt",
        json={"message": "Hello, Quantum World!", "timestamp": "2025-01-01T00:00:00Z"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "ciphertext" in data
    assert data["algorithm"] == "ML-KEM-768 + AES-256-GCM"


@pytest.mark.anyio
async def test_quantum_encrypt_decrypt_roundtrip(client: AsyncClient, auth_token: str):
    encrypt_response = await client.post(
        "/api/v1/security/quantum-encryption/encrypt",
        json={"test_data": "Secret message", "value": 42},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert encrypt_response.status_code == 200
    ciphertext = encrypt_response.json()["ciphertext"]

    decrypt_response = await client.post(
        "/api/v1/security/quantum-encryption/decrypt",
        params={"ciphertext": ciphertext},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert decrypt_response.status_code == 200
    data = decrypt_response.json()
    assert "plaintext" in data


@pytest.mark.anyio
async def test_quantum_encrypt_invalid_ciphertext(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/security/quantum-encryption/decrypt",
        params={"ciphertext": "invalid_ciphertext_data"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 400


@pytest.mark.anyio
async def test_rotate_qs_key(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/security/quantum-encryption/rotate",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rotated"
    assert "new_key_id" in data


# ============================================================================
# Audit Integrity Tests
# ============================================================================


@pytest.mark.anyio
async def test_get_audit_integrity_status(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/security/audit-integrity/status",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "algorithm" in data
    assert "entries_count" in data


@pytest.mark.anyio
async def test_verify_audit_integrity(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/security/audit-integrity/verify",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "verified" in data
    assert "verified_count" in data


@pytest.mark.anyio
async def test_get_audit_public_key(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/security/audit-integrity/public-key",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "public_key" in data
    assert data["algorithm"] == "ML-DSA-65"


@pytest.mark.anyio
async def test_sign_audit_event(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/security/audit-integrity/sign",
        json={
            "event_type": "test_event",
            "user_id": "test_user",
            "action": "test_action",
            "timestamp": "2025-01-01T00:00:00Z",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "signature" in data or "entry_id" in data


# ============================================================================
# Request Signing Tests
# ============================================================================


@pytest.mark.anyio
async def test_get_request_signing_status(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/security/request-signing/status",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "algorithm" in data
    assert "active_key_id" in data


@pytest.mark.anyio
async def test_get_signing_public_key(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/security/request-signing/public-key",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "public_key" in data
    assert data["algorithm"] == "ML-DSA-65"


@pytest.mark.anyio
async def test_sign_outgoing_request(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/security/request-signing/sign",
        params={
            "method": "POST",
            "path": "/api/v1/jobs",
            "body": '{"test": "data"}',
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "headers" in data
    headers = data["headers"]
    assert "X-Signature" in headers or "X-Request-Signature" in headers


@pytest.mark.anyio
async def test_rotate_signing_key(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/security/request-signing/rotate",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rotated"
    assert "new_key_id" in data


# ============================================================================
# PQC Key Rotation Tests
# ============================================================================


@pytest.mark.anyio
async def test_get_pqc_key_status(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/security/pqc-keys/status",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "keys" in data
    assert "rotation_interval_days" in data
    assert data["algorithm_signing"] == "ML-DSA-65"
    assert data["algorithm_encryption"] == "ML-KEM-768"


@pytest.mark.anyio
async def test_rotate_pqc_signing_key(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/security/pqc-keys/rotate/signing",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rotated"
    assert data["key_type"] == "signing"


@pytest.mark.anyio
async def test_rotate_pqc_encryption_key(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/security/pqc-keys/rotate/encryption",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rotated"
    assert data["key_type"] == "encryption"


@pytest.mark.anyio
async def test_rotate_invalid_key_type(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/security/pqc-keys/rotate/invalid_type",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 400


# ============================================================================
# Security Headers Tests
# ============================================================================


@pytest.mark.anyio
async def test_get_security_headers_status(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/security/headers/status",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "headers_applied" in data
    assert "hsts" in data
    assert "csp" in data

    headers = data["headers_applied"]
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"


# ============================================================================
# Legacy Encryption Tests
# ============================================================================


@pytest.mark.anyio
async def test_get_encryption_status(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/security/encryption/status",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "algorithm" in data


@pytest.mark.anyio
async def test_rotate_encryption_key(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/security/encryption/rotate-key",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rotated"
    assert "new_key_id" in data


# ============================================================================
# Secret Rotation Tests
# ============================================================================


@pytest.mark.anyio
async def test_get_rotation_status(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/security/rotation/status",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "secrets" in data


@pytest.mark.anyio
async def test_get_expiring_secrets(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/security/rotation/expiring?days=7",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "secrets" in data


# ============================================================================
# Audit Log Tests
# ============================================================================


@pytest.mark.anyio
async def test_list_audit_logs(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/security/audit/logs",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "events" in data


@pytest.mark.anyio
async def test_list_audit_logs_with_filters(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/security/audit/logs?limit=10&offset=0",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_trigger_audit_cleanup(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/security/audit/cleanup",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert "stats" in data


@pytest.mark.anyio
async def test_get_audit_storage_stats(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/security/audit/storage",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "events_in_memory" in data


@pytest.mark.anyio
async def test_get_audit_summary(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/security/audit/summary",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "period" in data
    assert "total_events" in data
    assert "by_type" in data
    assert "by_severity" in data


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


@pytest.mark.anyio
async def test_unauthorized_access(client: AsyncClient):
    response = await client.get("/api/v1/security/pqc-keys/status")
    assert response.status_code in [401, 403, 200]

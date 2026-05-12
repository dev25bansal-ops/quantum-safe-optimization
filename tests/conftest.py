"""Shared pytest fixtures for the Quantum-Safe Secure Optimization Platform."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock

# Set test environment before any imports
os.environ["TESTING"] = "1"
os.environ["APP_ENV"] = "test"
os.environ["DEMO_MODE"] = "false"


@pytest.fixture
def mock_signing_keypair():
    """Mock PQC signing keypair for tests."""
    keypair = MagicMock()
    keypair.sign = MagicMock(return_value="mock-signature-base64")
    keypair.verify = MagicMock(return_value=True)
    keypair.public_key = "mock-public-key-base64"
    return keypair


@pytest.fixture
def mock_kem_keypair():
    """Mock PQC KEM keypair for tests."""
    keypair = MagicMock()
    keypair.public_key = "mock-kem-public-base64"
    keypair.secret_key = "mock-kem-secret-base64"
    keypair.encrypt = MagicMock(return_value=MagicMock(to_json=MagicMock(return_value='{"ciphertext":"mock"}')))
    keypair.decrypt = MagicMock(return_value=b'{"result": "mock"}')
    return keypair


@pytest.fixture
def sample_user():
    """Sample user data for tests."""
    return {
        "user_id": "usr_test123",
        "id": "usr_test123",
        "username": "testuser",
        "email": "test@example.com",
        "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$mock$hash",
        "roles": ["user"],
        "is_active": True,
        "created_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_admin_user():
    """Sample admin user data for tests."""
    return {
        "user_id": "usr_admin123",
        "id": "usr_admin123",
        "username": "admin",
        "email": "admin@example.com",
        "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$mock$hash",
        "roles": ["admin", "user"],
        "is_active": True,
        "created_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_job():
    """Sample job data for tests."""
    return {
        "job_id": "job_test123",
        "id": "job_test123",
        "user_id": "usr_test123",
        "problem_type": "QAOA",
        "problem_config": {
            "type": "maxcut",
            "edges": [[0, 1], [1, 2], [2, 0]],
            "weights": [1, 1, 1],
        },
        "parameters": {"layers": 2, "optimizer": "COBYLA", "shots": 1000},
        "backend": "local_simulator",
        "status": "queued",
        "priority": 5,
        "created_at": "2024-01-01T00:00:00Z",
        "started_at": None,
        "completed_at": None,
        "result": None,
        "error": None,
    }


@pytest.fixture
def mock_job_store():
    """Mock job store for tests."""
    store = AsyncMock()
    store.upsert = AsyncMock(return_value={})
    store.get = AsyncMock(return_value=None)
    store.list = AsyncMock(return_value=[])
    store.count = AsyncMock(return_value=0)
    store.delete = AsyncMock(return_value=True)
    return store


@pytest.fixture
def mock_redis():
    """Mock Redis client for tests."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.ping = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def app_state(mock_signing_keypair):
    """Mock app state for tests."""
    state = MagicMock()
    state.signing_keypair = mock_signing_keypair
    state.signing_key_id = "key_test123"
    return state


@pytest.fixture
def sample_token_payload():
    """Sample JWT token payload for tests."""
    return {
        "sub": "usr_test123",
        "username": "testuser",
        "roles": ["user"],
        "iat": 1704067200,
        "exp": 1704153600,
        "jti": "mock-jti-123",
    }

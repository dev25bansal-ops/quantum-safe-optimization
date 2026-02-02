"""
Tests for database repository layer.

Tests the repository abstraction layer with in-memory fallback
and validates proper CRUD operations for jobs, users, keys, and tokens.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Import repository components
import sys
sys.path.insert(0, "D:/Quantum")

from api.db.repository import (
    BaseStore,
    InMemoryJobStore,
    InMemoryUserStore,
    InMemoryKeyStore,
    InMemoryTokenStore,
    get_job_store,
    get_user_store,
    get_key_store,
    get_token_store,
    reset_stores,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def reset_stores_before_each_test():
    """Reset all stores before each test."""
    reset_stores()
    yield
    reset_stores()


@pytest.fixture
def sample_user() -> Dict[str, Any]:
    """Create a sample user for testing."""
    return {
        "id": "usr_test123",
        "user_id": "usr_test123",
        "username": "testuser",
        "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$test$hash",
        "email": "test@example.com",
        "roles": ["user"],
        "created_at": datetime.utcnow().isoformat(),
        "kem_public_key": None,
    }


@pytest.fixture
def sample_job() -> Dict[str, Any]:
    """Create a sample job for testing."""
    return {
        "id": "job_test123",
        "job_id": "job_test123",
        "user_id": "usr_test123",
        "problem_type": "portfolio_optimization",
        "status": "queued",
        "created_at": datetime.utcnow().isoformat(),
        "parameters": {"assets": 5, "risk_tolerance": 0.5},
    }


@pytest.fixture
def sample_key() -> Dict[str, Any]:
    """Create a sample key for testing."""
    return {
        "id": "key_test123",
        "user_id": "usr_test123",
        "public_key": "base64encodedpublickey",
        "algorithm": "ML-KEM-768",
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(days=30),
    }


@pytest.fixture
def sample_token() -> Dict[str, Any]:
    """Create a sample token for testing."""
    return {
        "id": "token_test123",
        "token": "token_test123",
        "user_id": "usr_test123",
        "username": "testuser",
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
    }


# ============================================================================
# InMemoryJobStore Tests
# ============================================================================

class TestInMemoryJobStore:
    """Tests for InMemoryJobStore."""

    @pytest.mark.asyncio
    async def test_create_job(self, sample_job):
        """Test creating a new job."""
        store = InMemoryJobStore()
        
        result = await store.create(sample_job)
        
        assert result["job_id"] == sample_job["job_id"]
        assert result["status"] == "queued"
        assert store.is_cosmos is False

    @pytest.mark.asyncio
    async def test_get_job(self, sample_job):
        """Test retrieving a job by ID."""
        store = InMemoryJobStore()
        await store.create(sample_job)
        
        result = await store.get(sample_job["job_id"], sample_job["user_id"])
        
        assert result is not None
        assert result["job_id"] == sample_job["job_id"]

    @pytest.mark.asyncio
    async def test_get_nonexistent_job(self):
        """Test retrieving a job that doesn't exist."""
        store = InMemoryJobStore()
        
        result = await store.get("nonexistent", "user123")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_update_job(self, sample_job):
        """Test updating an existing job."""
        store = InMemoryJobStore()
        await store.create(sample_job)
        
        sample_job["status"] = "running"
        result = await store.update(sample_job)
        
        assert result["status"] == "running"
        
        # Verify persistence
        retrieved = await store.get(sample_job["job_id"], sample_job["user_id"])
        assert retrieved["status"] == "running"

    @pytest.mark.asyncio
    async def test_upsert_creates_new_job(self, sample_job):
        """Test upsert creates a new job if it doesn't exist."""
        store = InMemoryJobStore()
        
        result = await store.upsert(sample_job)
        
        assert result["job_id"] == sample_job["job_id"]
        
        retrieved = await store.get(sample_job["job_id"], sample_job["user_id"])
        assert retrieved is not None

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_job(self, sample_job):
        """Test upsert updates an existing job."""
        store = InMemoryJobStore()
        await store.create(sample_job)
        
        sample_job["status"] = "completed"
        await store.upsert(sample_job)
        
        retrieved = await store.get(sample_job["job_id"], sample_job["user_id"])
        assert retrieved["status"] == "completed"

    @pytest.mark.asyncio
    async def test_delete_job(self, sample_job):
        """Test deleting a job."""
        store = InMemoryJobStore()
        await store.create(sample_job)
        
        result = await store.delete(sample_job["job_id"], sample_job["user_id"])
        
        assert result is True
        
        retrieved = await store.get(sample_job["job_id"], sample_job["user_id"])
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_job(self):
        """Test deleting a job that doesn't exist."""
        store = InMemoryJobStore()
        
        result = await store.delete("nonexistent", "user123")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_list_jobs_by_user(self, sample_job):
        """Test listing jobs filtered by user."""
        store = InMemoryJobStore()
        
        # Create jobs for different users
        await store.create(sample_job)
        
        other_job = {**sample_job, "job_id": "job_other", "id": "job_other", "user_id": "other_user"}
        await store.create(other_job)
        
        # List jobs for specific user
        results = await store.list(sample_job["user_id"])
        
        assert len(results) == 1
        assert results[0]["job_id"] == sample_job["job_id"]

    @pytest.mark.asyncio
    async def test_list_jobs_with_status_filter(self, sample_job):
        """Test listing jobs with status filter."""
        store = InMemoryJobStore()
        
        await store.create(sample_job)
        
        completed_job = {
            **sample_job,
            "job_id": "job_completed",
            "id": "job_completed",
            "status": "completed"
        }
        await store.create(completed_job)
        
        # Filter by status
        results = await store.list(
            sample_job["user_id"],
            filters={"status": "completed"}
        )
        
        assert len(results) == 1
        assert results[0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_list_jobs_excludes_deleted(self, sample_job):
        """Test that deleted jobs are excluded from list."""
        store = InMemoryJobStore()
        
        await store.create(sample_job)
        
        deleted_job = {
            **sample_job,
            "job_id": "job_deleted",
            "id": "job_deleted",
            "deleted": True
        }
        await store.create(deleted_job)
        
        results = await store.list(sample_job["user_id"])
        
        assert len(results) == 1
        assert results[0]["job_id"] == sample_job["job_id"]

    @pytest.mark.asyncio
    async def test_count_jobs(self, sample_job):
        """Test counting jobs for a user."""
        store = InMemoryJobStore()
        
        await store.create(sample_job)
        await store.create({**sample_job, "job_id": "job_2", "id": "job_2"})
        
        count = await store.count(sample_job["user_id"])
        
        assert count == 2


# ============================================================================
# InMemoryUserStore Tests
# ============================================================================

class TestInMemoryUserStore:
    """Tests for InMemoryUserStore."""

    @pytest.mark.asyncio
    async def test_has_default_admin_user(self):
        """Test that admin user exists by default."""
        store = InMemoryUserStore()
        
        admin = await store.get_by_username("admin")
        
        assert admin is not None
        assert admin["username"] == "admin"
        assert "admin" in admin["roles"]

    @pytest.mark.asyncio
    async def test_create_user(self, sample_user):
        """Test creating a new user."""
        store = InMemoryUserStore()
        
        result = await store.create(sample_user)
        
        assert result["username"] == sample_user["username"]
        assert store.is_cosmos is False

    @pytest.mark.asyncio
    async def test_get_user_by_username(self, sample_user):
        """Test retrieving user by username."""
        store = InMemoryUserStore()
        await store.create(sample_user)
        
        result = await store.get_by_username(sample_user["username"])
        
        assert result is not None
        assert result["email"] == sample_user["email"]

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, sample_user):
        """Test retrieving user by ID."""
        store = InMemoryUserStore()
        await store.create(sample_user)
        
        result = await store.get(sample_user["user_id"], sample_user["user_id"])
        
        assert result is not None
        assert result["username"] == sample_user["username"]

    @pytest.mark.asyncio
    async def test_update_user(self, sample_user):
        """Test updating a user."""
        store = InMemoryUserStore()
        await store.create(sample_user)
        
        sample_user["email"] = "updated@example.com"
        result = await store.update(sample_user)
        
        assert result["email"] == "updated@example.com"

    @pytest.mark.asyncio
    async def test_update_user_changes_username_index(self, sample_user):
        """Test that updating username updates the index."""
        store = InMemoryUserStore()
        await store.create(sample_user)
        
        old_username = sample_user["username"]
        sample_user["username"] = "newusername"
        await store.update(sample_user)
        
        # Old username should not find the user
        old_result = await store.get_by_username(old_username)
        assert old_result is None
        
        # New username should find the user
        new_result = await store.get_by_username("newusername")
        assert new_result is not None

    @pytest.mark.asyncio
    async def test_delete_user(self, sample_user):
        """Test deleting a user."""
        store = InMemoryUserStore()
        await store.create(sample_user)
        
        result = await store.delete(sample_user["user_id"], sample_user["user_id"])
        
        assert result is True
        
        # Username index should be cleared
        retrieved = await store.get_by_username(sample_user["username"])
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_list_users(self, sample_user):
        """Test listing all users."""
        store = InMemoryUserStore()
        await store.create(sample_user)
        
        results = await store.list()
        
        # Should include admin + our test user
        assert len(results) >= 2
        usernames = [u["username"] for u in results]
        assert sample_user["username"] in usernames
        assert "admin" in usernames

    @pytest.mark.asyncio
    async def test_count_users(self, sample_user):
        """Test counting users."""
        store = InMemoryUserStore()
        initial_count = await store.count()
        
        await store.create(sample_user)
        
        new_count = await store.count()
        
        assert new_count == initial_count + 1


# ============================================================================
# InMemoryKeyStore Tests
# ============================================================================

class TestInMemoryKeyStore:
    """Tests for InMemoryKeyStore."""

    @pytest.mark.asyncio
    async def test_create_key(self, sample_key):
        """Test creating a key record."""
        store = InMemoryKeyStore()
        
        result = await store.create(sample_key)
        
        assert result["id"] == sample_key["id"]
        assert result["algorithm"] == "ML-KEM-768"

    @pytest.mark.asyncio
    async def test_get_key(self, sample_key):
        """Test retrieving a key."""
        store = InMemoryKeyStore()
        await store.create(sample_key)
        
        result = await store.get(sample_key["id"], sample_key["user_id"])
        
        assert result is not None
        assert result["public_key"] == sample_key["public_key"]

    @pytest.mark.asyncio
    async def test_get_key_by_user(self, sample_key):
        """Test retrieving key by user ID."""
        store = InMemoryKeyStore()
        await store.create(sample_key)
        
        result = await store.get_by_user(sample_key["user_id"])
        
        assert result is not None
        assert result["id"] == sample_key["id"]

    @pytest.mark.asyncio
    async def test_upsert_key(self, sample_key):
        """Test upserting a key."""
        store = InMemoryKeyStore()
        
        # Create
        await store.upsert(sample_key)
        
        # Update
        sample_key["public_key"] = "updatedkey"
        await store.upsert(sample_key)
        
        result = await store.get(sample_key["id"], sample_key["user_id"])
        assert result["public_key"] == "updatedkey"

    @pytest.mark.asyncio
    async def test_delete_key(self, sample_key):
        """Test deleting a key."""
        store = InMemoryKeyStore()
        await store.create(sample_key)
        
        result = await store.delete(sample_key["id"], sample_key["user_id"])
        
        assert result is True
        
        retrieved = await store.get(sample_key["id"], sample_key["user_id"])
        assert retrieved is None


# ============================================================================
# InMemoryTokenStore Tests
# ============================================================================

class TestInMemoryTokenStore:
    """Tests for InMemoryTokenStore."""

    @pytest.mark.asyncio
    async def test_create_token(self, sample_token):
        """Test creating a token record."""
        store = InMemoryTokenStore()
        
        result = await store.create(sample_token)
        
        assert result["token"] == sample_token["token"]

    @pytest.mark.asyncio
    async def test_get_token(self, sample_token):
        """Test retrieving a token."""
        store = InMemoryTokenStore()
        await store.create(sample_token)
        
        result = await store.get(sample_token["token"], None)
        
        assert result is not None
        assert result["user_id"] == sample_token["user_id"]

    @pytest.mark.asyncio
    async def test_delete_token(self, sample_token):
        """Test deleting a token."""
        store = InMemoryTokenStore()
        await store.create(sample_token)
        
        result = await store.delete(sample_token["token"], None)
        
        assert result is True


# ============================================================================
# Factory Function Tests
# ============================================================================

class TestFactoryFunctions:
    """Tests for store factory functions."""

    @pytest.mark.asyncio
    async def test_get_job_store_returns_inmemory_fallback(self):
        """Test that get_job_store returns in-memory when Cosmos not configured."""
        store = await get_job_store()
        
        # Should return InMemoryJobStore as fallback
        assert store is not None
        assert store.is_cosmos is False

    @pytest.mark.asyncio
    async def test_get_user_store_returns_inmemory_fallback(self):
        """Test that get_user_store returns in-memory when Cosmos not configured."""
        store = await get_user_store()
        
        assert store is not None
        assert store.is_cosmos is False

    @pytest.mark.asyncio
    async def test_get_key_store_returns_inmemory_fallback(self):
        """Test that get_key_store returns in-memory when Cosmos not configured."""
        store = await get_key_store()
        
        assert store is not None
        assert store.is_cosmos is False

    @pytest.mark.asyncio
    async def test_get_token_store_returns_inmemory_fallback(self):
        """Test that get_token_store returns in-memory when Cosmos not configured."""
        store = await get_token_store()
        
        assert store is not None
        assert store.is_cosmos is False

    @pytest.mark.asyncio
    async def test_stores_are_singletons(self):
        """Test that factory functions return the same instance."""
        store1 = await get_job_store()
        store2 = await get_job_store()
        
        assert store1 is store2

    @pytest.mark.asyncio
    async def test_reset_stores_clears_singletons(self):
        """Test that reset_stores clears all singletons."""
        store1 = await get_job_store()
        reset_stores()
        store2 = await get_job_store()
        
        assert store1 is not store2


# ============================================================================
# Integration Tests
# ============================================================================

class TestStoreIntegration:
    """Integration tests for store interactions."""

    @pytest.mark.asyncio
    async def test_user_with_jobs_workflow(self, sample_user, sample_job):
        """Test creating a user and associating jobs."""
        user_store = InMemoryUserStore()
        job_store = InMemoryJobStore()
        
        # Create user
        user = await user_store.create(sample_user)
        
        # Create job for user
        sample_job["user_id"] = user["user_id"]
        job = await job_store.create(sample_job)
        
        # Verify relationship
        user_jobs = await job_store.list(user["user_id"])
        assert len(user_jobs) == 1
        assert user_jobs[0]["job_id"] == job["job_id"]

    @pytest.mark.asyncio
    async def test_user_with_keys_workflow(self, sample_user, sample_key):
        """Test creating a user and associating keys."""
        user_store = InMemoryUserStore()
        key_store = InMemoryKeyStore()
        
        # Create user
        user = await user_store.create(sample_user)
        
        # Create key for user
        sample_key["user_id"] = user["user_id"]
        key = await key_store.create(sample_key)
        
        # Verify relationship
        user_key = await key_store.get_by_user(user["user_id"])
        assert user_key is not None
        assert user_key["id"] == key["id"]

    @pytest.mark.asyncio
    async def test_full_job_lifecycle(self, sample_job):
        """Test complete job lifecycle: create, update, complete, delete."""
        store = InMemoryJobStore()
        
        # Create
        job = await store.create(sample_job)
        assert job["status"] == "queued"
        
        # Start processing
        job["status"] = "running"
        job["started_at"] = datetime.utcnow().isoformat()
        await store.update(job)
        
        retrieved = await store.get(job["job_id"], job["user_id"])
        assert retrieved["status"] == "running"
        
        # Complete
        job["status"] = "completed"
        job["completed_at"] = datetime.utcnow().isoformat()
        job["result"] = {"optimal_weights": [0.3, 0.3, 0.4]}
        await store.update(job)
        
        retrieved = await store.get(job["job_id"], job["user_id"])
        assert retrieved["status"] == "completed"
        assert "result" in retrieved
        
        # Soft delete (mark as deleted)
        job["deleted"] = True
        await store.update(job)
        
        # Should not appear in list
        jobs = await store.list(job["user_id"])
        assert len(jobs) == 0

    @pytest.mark.asyncio
    async def test_concurrent_job_creation(self, sample_job):
        """Test creating multiple jobs concurrently."""
        store = InMemoryJobStore()
        
        async def create_job(i: int):
            job = {**sample_job, "job_id": f"job_{i}", "id": f"job_{i}"}
            return await store.create(job)
        
        # Create 10 jobs concurrently
        tasks = [create_job(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 10
        
        # Verify all jobs exist
        jobs = await store.list(sample_job["user_id"])
        assert len(jobs) == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

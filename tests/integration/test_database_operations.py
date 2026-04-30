"""
Integration tests for database operations.

Tests cover:
- User store operations with indexes
- Job store CRUD operations
- Key store operations
- Multi-tenant isolation
- Concurrent access
"""

import asyncio
import pytest
from datetime import UTC, datetime
from typing import Any


class TestUserStoreIntegration:
    """Test user store operations with optimized indexes."""

    @pytest.fixture
    def store(self):
        """Create test user store."""
        import os
        os.environ["ADMIN_PASSWORD"] = "test_admin_pass_123"
        os.environ["APP_ENV"] = "test"
        
        from api.auth_stores import InMemoryUserStore
        return InMemoryUserStore()

    @pytest.mark.asyncio
    async def test_full_user_lifecycle(self, store):
        """Test complete user lifecycle: create, read, update, delete."""
        # Create
        user = {
            "username": "testuser",
            "user_id": "usr_test_001",
            "email": "test@example.com",
            "password_hash": "hashed_password",
            "roles": ["user"],
            "created_at": datetime.now(UTC).isoformat(),
        }
        saved = await store.save(user)
        assert saved["username"] == "testuser"

        # Read by username
        by_username = await store.get_by_username("testuser")
        assert by_username is not None
        assert by_username["user_id"] == "usr_test_001"

        # Read by ID (uses index)
        by_id = await store.get_by_id("usr_test_001")
        assert by_id is not None
        assert by_id["username"] == "testuser"

        # Read by email (uses index)
        by_email = await store.get_by_email("test@example.com")
        assert by_email is not None
        assert by_email["username"] == "testuser"

        # Update
        user["email"] = "updated@example.com"
        await store.save(user)

        # Verify old email removed from index
        assert await store.email_exists("test@example.com") is False
        # Verify new email in index
        assert await store.email_exists("updated@example.com") is True

        # Delete
        deleted = await store.delete("testuser")
        assert deleted is True

        # Verify cleaned up
        assert await store.get_by_username("testuser") is None
        assert await store.get_by_id("usr_test_001") is None
        assert await store.email_exists("updated@example.com") is False

    @pytest.mark.asyncio
    async def test_concurrent_user_creation(self, store):
        """Test concurrent user creation doesn't corrupt indexes."""
        async def create_user(i: int):
            user = {
                "username": f"concurrent_user_{i}",
                "user_id": f"usr_concurrent_{i:04d}",
                "email": f"user{i}@example.com",
                "password_hash": "hashed",
                "created_at": datetime.now(UTC).isoformat(),
            }
            return await store.save(user)

        # Create 100 users concurrently
        tasks = [create_user(i) for i in range(100)]
        await asyncio.gather(*tasks)

        # Verify all users exist
        for i in range(100):
            assert await store.email_exists(f"user{i}@example.com") is True
            assert await store.get_by_id(f"usr_concurrent_{i:04d}") is not None

        # Count should be correct (100 + admin)
        count = await store.count()
        assert count == 101

    @pytest.mark.asyncio
    async def test_email_uniqueness(self, store):
        """Test that duplicate emails update correctly."""
        # Create first user
        user1 = {
            "username": "user1",
            "user_id": "usr_dup_001",
            "email": "shared@example.com",
            "password_hash": "hash1",
        }
        await store.save(user1)

        # Create second user with same email
        user2 = {
            "username": "user2",
            "user_id": "usr_dup_002",
            "email": "shared@example.com",
            "password_hash": "hash2",
        }
        await store.save(user2)

        # Email should point to latest user
        retrieved = await store.get_by_email("shared@example.com")
        assert retrieved["username"] == "user2"

    @pytest.mark.asyncio
    async def test_bulk_operations(self, store):
        """Test bulk user operations."""
        # Bulk create
        users = [
            {
                "username": f"bulk_user_{i}",
                "user_id": f"usr_bulk_{i:04d}",
                "email": f"bulk{i}@example.com",
                "password_hash": "hashed",
                "created_at": datetime.now(UTC).isoformat(),
            }
            for i in range(50)
        ]

        for user in users:
            await store.save(user)

        # Verify bulk create
        count = await store.count()
        assert count == 51  # 50 + admin

        # List with pagination
        page1 = await store.list(limit=10)
        assert len(page1) <= 10

        page2 = await store.list(limit=10, offset=10)
        assert len(page2) <= 10


class TestJobStoreIntegration:
    """Test job store operations."""

    @pytest.mark.asyncio
    async def test_bounded_store_lifecycle(self):
        """Test bounded job store complete lifecycle."""
        from api.stores.bounded_memory_stores import BoundedInMemoryJobStore

        store = BoundedInMemoryJobStore(max_size=100, default_ttl_seconds=3600)

        # Create
        job_data = {
            "id": "job_test_001",
            "user_id": "usr_001",
            "problem_type": "QAOA",
            "status": "queued",
            "created_at": datetime.now(UTC).isoformat(),
        }
        await store.set("job_test_001", job_data)

        # Read
        retrieved = await store.get("job_test_001")
        assert retrieved is not None
        assert retrieved["status"] == "queued"

        # Update
        await store.update("job_test_001", {"status": "running", "started_at": datetime.now(UTC).isoformat()})
        updated = await store.get("job_test_001")
        assert updated["status"] == "running"

        # Delete
        deleted = await store.delete("job_test_001")
        assert deleted is True

        # Verify deleted
        assert await store.get("job_test_001") is None

    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        """Test that jobs expire after TTL."""
        from api.stores.bounded_memory_stores import BoundedInMemoryJobStore

        # Very short TTL for testing
        store = BoundedInMemoryJobStore(max_size=100, default_ttl_seconds=2)

        # Add job
        await store.set("job_short_ttl", {"id": "job_short_ttl"}, ttl=2)
        assert await store.get("job_short_ttl") is not None

        # Wait for expiration
        await asyncio.sleep(2.5)

        # Should be expired
        assert await store.get("job_short_ttl") is None

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        """Test LRU eviction when store is full."""
        from api.stores.bounded_memory_stores import BoundedInMemoryJobStore

        store = BoundedInMemoryJobStore(max_size=10, default_ttl_seconds=3600)

        # Fill store to capacity
        for i in range(10):
            await store.set(f"job_{i:03d}", {"id": f"job_{i:03d}"})

        # Add one more (should evict oldest)
        await store.set("job_new", {"id": "job_new"})

        # Count should be at max
        count = await store.count()
        assert count <= 10

        # Oldest job should be evicted
        assert await store.get("job_000") is None

    @pytest.mark.asyncio
    async def test_job_listing_with_filters(self):
        """Test job listing with filters."""
        from api.stores.bounded_memory_stores import BoundedInMemoryJobStore

        store = BoundedInMemoryJobStore(max_size=100, default_ttl_seconds=3600)

        # Create jobs with different statuses
        statuses = ["queued", "running", "completed", "failed"]
        for i, status in enumerate(statuses * 5):  # 20 jobs total
            await store.set(
                f"job_{i:03d}",
                {
                    "id": f"job_{i:03d}",
                    "user_id": "usr_001",
                    "status": status,
                    "problem_type": "QAOA" if i % 2 == 0 else "VQE",
                }
            )

        # List all
        all_jobs = await store.list(limit=100)
        assert len(all_jobs) == 20

        # List with filter (completed only)
        def filter_completed(job):
            return job.get("status") == "completed"

        completed = await store.list(limit=100, filter_fn=filter_completed)
        assert len(completed) == 5


class TestKeyStoreIntegration:
    """Test key store operations with user index."""

    @pytest.fixture
    def store(self):
        """Create test key store."""
        from api.auth_stores import InMemoryKeyStore
        return InMemoryKeyStore()

    @pytest.mark.asyncio
    async def test_key_lifecycle(self, store):
        """Test complete key lifecycle."""
        user_id = "usr_keys_001"

        # Create keys
        for i in range(3):
            key = {
                "key_id": f"key_{i:03d}",
                "user_id": user_id,
                "type": "api_key",
                "created_at": f"2024-01-{i+1:02d}T00:00:00",
            }
            await store.save(key)

        # List for user (should use index)
        keys = await store.list_for_user(user_id)
        assert len(keys) == 3

        # Should be sorted by created_at (newest first)
        assert keys[0]["key_id"] == "key_002"
        assert keys[1]["key_id"] == "key_001"

        # Get specific key
        key = await store.get("key_001")
        assert key is not None
        assert key["user_id"] == user_id

        # Delete key
        deleted = await store.delete("key_001")
        assert deleted is True

        # Verify index updated
        count = await store.count_for_user(user_id)
        assert count == 2

    @pytest.mark.asyncio
    async def test_multi_user_isolation(self, store):
        """Test key isolation between users."""
        # Add keys for user1
        for i in range(5):
            await store.save({"key_id": f"key_u1_{i}", "user_id": "usr_001"})

        # Add keys for user2
        for i in range(3):
            await store.save({"key_id": f"key_u2_{i}", "user_id": "usr_002"})

        # Verify isolation
        keys_u1 = await store.list_for_user("usr_001")
        keys_u2 = await store.list_for_user("usr_002")

        assert len(keys_u1) == 5
        assert len(keys_u2) == 3
        assert all(k["user_id"] == "usr_001" for k in keys_u1)
        assert all(k["user_id"] == "usr_002" for k in keys_u2)


class TestMultiTenantIsolation:
    """Test multi-tenant data isolation."""

    @pytest.mark.asyncio
    async def test_tenant_isolation(self):
        """Test that tenants cannot access each other's data."""
        from api.stores.bounded_memory_stores import BoundedInMemoryJobStore

        store = BoundedInMemoryJobStore(max_size=1000, default_ttl_seconds=3600)

        # Create jobs for tenant1
        for i in range(10):
            await store.set(
                f"job_t1_{i:03d}",
                {
                    "id": f"job_t1_{i:03d}",
                    "user_id": f"usr_t1_{i:03d}",
                    "tenant_id": "tenant_1",
                    "status": "completed",
                }
            )

        # Create jobs for tenant2
        for i in range(10):
            await store.set(
                f"job_t2_{i:03d}",
                {
                    "id": f"job_t2_{i:03d}",
                    "user_id": f"usr_t2_{i:03d}",
                    "tenant_id": "tenant_2",
                    "status": "completed",
                }
            )

        # Verify total count
        count = await store.count()
        assert count == 20

        # Verify tenant isolation (filter by tenant)
        def filter_tenant1(job):
            return job.get("tenant_id") == "tenant_1"

        tenant1_jobs = await store.list(limit=100, filter_fn=filter_tenant1)
        assert len(tenant1_jobs) == 10
        assert all(j["tenant_id"] == "tenant_1" for j in tenant1_jobs)


class TestConcurrentAccess:
    """Test concurrent access patterns."""

    @pytest.mark.asyncio
    async def test_concurrent_reads_and_writes(self):
        """Test concurrent reads and writes don't corrupt data."""
        from api.stores.bounded_memory_stores import BoundedInMemoryJobStore

        store = BoundedInMemoryJobStore(max_size=1000, default_ttl_seconds=3600)

        # Pre-populate
        for i in range(50):
            await store.set(f"job_{i:03d}", {"id": f"job_{i:03d}", "status": "queued"})

        async def read_write(i: int):
            # Read
            job = await store.get(f"job_{i:03d}")
            if job:
                # Update
                await store.update(f"job_{i:03d}", {"status": "running"})

        # Run concurrent operations
        tasks = [read_write(i) for i in range(50)]
        await asyncio.gather(*tasks)

        # Verify all jobs updated
        for i in range(50):
            job = await store.get(f"job_{i:03d}")
            if job:
                assert job["status"] == "running"

    @pytest.mark.asyncio
    async def test_concurrent_count(self):
        """Test concurrent count operations return consistent results."""
        from api.stores.bounded_memory_stores import BoundedInMemoryJobStore

        store = BoundedInMemoryJobStore(max_size=1000, default_ttl_seconds=3600)

        # Add jobs
        for i in range(100):
            await store.set(f"job_{i:03d}", {"id": f"job_{i:03d}"})

        async def get_count():
            return await store.count()

        # Run concurrent counts
        counts = await asyncio.gather(*[get_count() for _ in range(10)])

        # All should return same count
        assert len(set(counts)) == 1
        assert counts[0] == 100

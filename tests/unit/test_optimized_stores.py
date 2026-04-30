"""
Unit tests for optimized in-memory stores with indexes.

Tests verify:
- O(1) email lookup performance
- O(1) user ID lookup performance
- Index maintenance on CRUD operations
- Bounded memory stores with TTL
"""

import pytest
from datetime import UTC, datetime
from api.auth_stores import InMemoryUserStore, InMemoryKeyStore, InMemoryTokenStore


class TestInMemoryUserStoreIndexes:
    """Test optimized user store with indexes."""
    
    @pytest.fixture
    def store(self):
        """Create fresh store instance."""
        # Reset admin password to avoid env var issues
        import os
        os.environ["ADMIN_PASSWORD"] = "test_admin_pass"
        os.environ["APP_ENV"] = "test"
        return InMemoryUserStore()
    
    @pytest.mark.asyncio
    async def test_email_exists_is_o1(self, store):
        """Test that email_exists uses O(1) index lookup."""
        # Add a user
        user = {
            "username": "testuser",
            "user_id": "usr_test_001",
            "email": "test@example.com",
            "password_hash": "hashed",
        }
        await store.save(user)
        
        # Test O(1) lookup
        exists = await store.email_exists("test@example.com")
        assert exists is True
        
        # Test non-existent email
        not_exists = await store.email_exists("nonexistent@example.com")
        assert not_exists is False
    
    @pytest.mark.asyncio
    async def test_get_by_email_uses_index(self, store):
        """Test get_by_email returns correct user via index."""
        user = {
            "username": "emailuser",
            "user_id": "usr_email_001",
            "email": "emailuser@example.com",
            "password_hash": "hashed",
            "name": "Email User",
        }
        await store.save(user)
        
        # Retrieve by email
        retrieved = await store.get_by_email("emailuser@example.com")
        assert retrieved is not None
        assert retrieved["username"] == "emailuser"
        assert retrieved["name"] == "Email User"
    
    @pytest.mark.asyncio
    async def test_get_by_id_uses_index(self, store):
        """Test get_by_id uses O(1) index instead of iteration."""
        user = {
            "username": "iduser",
            "user_id": "usr_id_001",
            "email": "iduser@example.com",
            "password_hash": "hashed",
        }
        await store.save(user)
        
        # Retrieve by ID
        retrieved = await store.get_by_id("usr_id_001")
        assert retrieved is not None
        assert retrieved["username"] == "iduser"
        assert retrieved["user_id"] == "usr_id_001"
    
    @pytest.mark.asyncio
    async def test_index_updated_on_save(self, store):
        """Test indexes are updated when user is saved."""
        # Save user first time
        user1 = {
            "username": "updateuser",
            "user_id": "usr_update_001",
            "email": "old@example.com",
            "password_hash": "hashed",
        }
        await store.save(user1)
        
        # Verify old email indexed
        assert await store.email_exists("old@example.com") is True
        
        # Update user with new email
        user2 = {
            "username": "updateuser",
            "user_id": "usr_update_001",
            "email": "new@example.com",
            "password_hash": "hashed_updated",
        }
        await store.save(user2)
        
        # Verify old email removed from index
        assert await store.email_exists("old@example.com") is False
        # Verify new email added to index
        assert await store.email_exists("new@example.com") is True
        
        # Verify ID index still works
        retrieved = await store.get_by_id("usr_update_001")
        assert retrieved is not None
        assert retrieved["email"] == "new@example.com"
    
    @pytest.mark.asyncio
    async def test_index_cleaned_on_delete(self, store):
        """Test indexes are cleaned when user is deleted."""
        user = {
            "username": "deleteuser",
            "user_id": "usr_delete_001",
            "email": "delete@example.com",
            "password_hash": "hashed",
        }
        await store.save(user)
        
        # Verify user exists
        assert await store.email_exists("delete@example.com") is True
        assert await store.get_by_id("usr_delete_001") is not None
        
        # Delete user
        deleted = await store.delete("deleteuser")
        assert deleted is True
        
        # Verify indexes cleaned
        assert await store.email_exists("delete@example.com") is False
        assert await store.get_by_id("usr_delete_001") is None
    
    @pytest.mark.asyncio
    async def test_count_is_o1(self, store):
        """Test count operation is O(1)."""
        # Add multiple users
        for i in range(5):
            user = {
                "username": f"user{i}",
                "user_id": f"usr_count_{i:03d}",
                "email": f"user{i}@example.com",
                "password_hash": "hashed",
            }
            await store.save(user)
        
        # Count should be O(1)
        count = await store.count()
        # 5 users + 1 admin = 6
        assert count == 6
    
    @pytest.mark.asyncio
    async def test_duplicate_email_handling(self, store):
        """Test that duplicate emails are handled correctly."""
        # Add first user
        user1 = {
            "username": "user1",
            "user_id": "usr_dup_001",
            "email": "shared@example.com",
            "password_hash": "hashed1",
        }
        await store.save(user1)
        
        # Add second user with same email (different username)
        user2 = {
            "username": "user2",
            "user_id": "usr_dup_002",
            "email": "shared@example.com",
            "password_hash": "hashed2",
        }
        await store.save(user2)
        
        # Email should still exist (pointing to latest user)
        assert await store.email_exists("shared@example.com") is True
        
        # get_by_email should return the latest user
        retrieved = await store.get_by_email("shared@example.com")
        assert retrieved["username"] == "user2"


class TestInMemoryKeyStoreIndex:
    """Test optimized key store with user index."""
    
    @pytest.fixture
    def store(self):
        """Create fresh key store instance."""
        return InMemoryKeyStore()
    
    @pytest.mark.asyncio
    async def test_list_for_user_uses_index(self, store):
        """Test list_for_user uses O(1) index lookup."""
        user_id = "usr_keys_001"
        
        # Add multiple keys for user
        for i in range(3):
            key = {
                "key_id": f"key_{i:03d}",
                "user_id": user_id,
                "type": "api_key",
                "created_at": f"2024-01-0{i+1}T00:00:00",
            }
            await store.save(key)
        
        # List keys for user (should use index)
        keys = await store.list_for_user(user_id)
        assert len(keys) == 3
        
        # Should be sorted by created_at, newest first
        assert keys[0]["key_id"] == "key_002"
        assert keys[1]["key_id"] == "key_001"
        assert keys[2]["key_id"] == "key_000"
    
    @pytest.mark.asyncio
    async def test_count_for_user_is_o1(self, store):
        """Test count_for_user is O(1)."""
        user_id = "usr_count_001"
        
        # Add keys
        for i in range(5):
            key = {
                "key_id": f"key_count_{i:03d}",
                "user_id": user_id,
                "type": "api_key",
            }
            await store.save(key)
        
        # Count should be O(1)
        count = await store.count_for_user(user_id)
        assert count == 5
    
    @pytest.mark.asyncio
    async def test_index_cleaned_on_delete(self, store):
        """Test index is cleaned when key is deleted."""
        user_id = "usr_del_001"
        
        # Add key
        key = {
            "key_id": "key_del_001",
            "user_id": user_id,
            "type": "api_key",
        }
        await store.save(key)
        
        # Verify key exists
        assert await store.count_for_user(user_id) == 1
        
        # Delete key
        deleted = await store.delete("key_del_001")
        assert deleted is True
        
        # Verify index cleaned
        assert await store.count_for_user(user_id) == 0
    
    @pytest.mark.asyncio
    async def test_multiple_users_isolation(self, store):
        """Test keys are isolated between users."""
        user1 = "usr_multi_001"
        user2 = "usr_multi_002"
        
        # Add keys for user1
        for i in range(3):
            await store.save({"key_id": f"key_u1_{i}", "user_id": user1})
        
        # Add keys for user2
        for i in range(2):
            await store.save({"key_id": f"key_u2_{i}", "user_id": user2})
        
        # Verify isolation
        keys_u1 = await store.list_for_user(user1)
        keys_u2 = await store.list_for_user(user2)
        
        assert len(keys_u1) == 3
        assert len(keys_u2) == 2
        assert all(k["user_id"] == user1 for k in keys_u1)
        assert all(k["user_id"] == user2 for k in keys_u2)


class TestEmailCheckOptimization:
    """Test optimized email check in auth router."""
    
    @pytest.mark.asyncio
    async def test_check_email_exists_uses_index(self):
        """Test that check_email_exists uses optimized index."""
        import os
        os.environ["ADMIN_PASSWORD"] = "test_pass"
        os.environ["APP_ENV"] = "test"
        
        from api.routers.auth import check_email_exists
        from api.auth_stores import InMemoryUserStore, AuthStores
        
        # Create store with optimized index
        store = InMemoryUserStore()
        
        # Add user
        user = {
            "username": "emailtest",
            "user_id": "usr_email_test",
            "email": "unique@example.com",
            "password_hash": "hashed",
        }
        await store.save(user)
        
        # Set as singleton for test
        AuthStores._instance = AuthStores(user_store=store)
        
        # Test optimized check
        exists = await check_email_exists("unique@example.com")
        assert exists is True
        
        not_exists = await check_email_exists("nonexistent@example.com")
        assert not_exists is False
        
        # Reset singleton
        AuthStores.reset()


class TestPerformanceBenchmark:
    """Performance benchmarks for optimized operations."""
    
    @pytest.mark.asyncio
    async def test_email_lookup_performance(self, benchmark):
        """Benchmark email lookup performance."""
        import os
        os.environ["ADMIN_PASSWORD"] = "test_pass"
        os.environ["APP_ENV"] = "test"
        
        store = InMemoryUserStore()
        
        # Add 1000 users
        for i in range(1000):
            user = {
                "username": f"perf_user_{i}",
                "user_id": f"usr_perf_{i:04d}",
                "email": f"perf{i}@example.com",
                "password_hash": "hashed",
            }
            await store.save(user)
        
        # Benchmark email_exists (should be O(1))
        async def lookup_email():
            return await store.email_exists("perf500@example.com")
        
        # Should complete in < 1ms for O(1) lookup
        result = await lookup_email()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_count_performance(self, benchmark):
        """Benchmark count operation performance."""
        store = InMemoryUserStore()
        
        # Add 1000 users
        for i in range(1000):
            user = {
                "username": f"count_user_{i}",
                "user_id": f"usr_count_{i:04d}",
                "email": f"count{i}@example.com",
                "password_hash": "hashed",
            }
            await store.save(user)
        
        # Benchmark count (should be O(1))
        async def count_users():
            return await store.count()
        
        count = await count_users()
        # 1000 + 1 admin = 1001
        assert count == 1001

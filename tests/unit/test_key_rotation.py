"""
Tests for Key Rotation Service and Persistent Key Store.

Tests cover:
- Key generation and metadata
- Key rotation lifecycle
- Expiration detection
- Audit trail
- Persistent storage integration
"""

import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


class TestKeyRotationService:
    """Test KeyRotationService functionality."""

    @pytest.fixture
    def rotation_service(self):
        """Create rotation service with test policy."""
        from api.key_rotation import KeyRotationService, RotationPolicy
        
        policy = RotationPolicy(
            max_age_days=1,  # Short for testing
            rotate_before_days=0,
        )
        return KeyRotationService(rotation_policy=policy)

    @pytest.mark.asyncio
    async def test_generate_key_creates_metadata(self, rotation_service):
        """Test that key generation creates proper metadata."""
        key_meta = await rotation_service.generate_key(
            key_type="signing",
            security_level=3,
        )

        assert key_meta.key_id is not None
        assert key_meta.key_type == "signing"
        assert key_meta.security_level == 3
        assert key_meta.is_active is True
        assert key_meta.expires_at > datetime.now(UTC)

    @pytest.mark.asyncio
    async def test_rotate_key_deactivates_old_key(self, rotation_service):
        """Test that rotation deactivates old key and creates new one."""
        old_key = await rotation_service.generate_key(key_type="signing")
        new_key = await rotation_service.rotate_key(old_key.key_id)

        # Old key should be inactive
        old_key_check = rotation_service.get_key(old_key.key_id)
        assert old_key_check.is_active is False

        # New key should be active
        assert new_key.is_active is True
        assert new_key.rotated_from == old_key.key_id

    @pytest.mark.asyncio
    async def test_get_active_keys_filters_inactive(self, rotation_service):
        """Test that get_active_keys returns only active keys."""
        # Generate and rotate keys
        key1 = await rotation_service.generate_key(key_type="signing")
        key2 = await rotation_service.rotate_key(key1.key_id)

        active_keys = rotation_service.get_active_keys()
        assert len(active_keys) == 1
        assert active_keys[0].key_id == key2.key_id

    @pytest.mark.asyncio
    async def test_get_expiring_keys(self, rotation_service):
        """Test detection of keys near expiration."""
        # Create key expiring soon
        from api.key_rotation import KeyMetadata
        
        expiring_key = KeyMetadata(
            key_id="expiring_key",
            key_type="signing",
            public_key="test",
            security_level=3,
            created_at=datetime.now(UTC) - timedelta(days=1),
            expires_at=datetime.now(UTC) + timedelta(hours=12),  # Expires in 12 hours
        )
        rotation_service._keys["expiring_key"] = expiring_key

        # Should detect as expiring within 1 day
        expiring = rotation_service.get_expiring_keys(within_days=1)
        assert len(expiring) == 1
        assert expiring[0].key_id == "expiring_key"

    @pytest.mark.asyncio
    async def test_rotation_service_status(self, rotation_service):
        """Test status reporting."""
        await rotation_service.generate_key(key_type="signing")
        await rotation_service.generate_key(key_type="kem")

        status = rotation_service.get_status()

        assert status["total_keys"] == 2
        assert status["active_keys"] == 2
        assert status["scheduler_running"] is False


class TestPersistentKeyStore:
    """Test PersistentKeyStore functionality."""

    @pytest.mark.asyncio
    async def test_save_and_load_key(self):
        """Test key persistence."""
        from api.stores.persistent_key_store import PersistentKeyStore
        
        # Mock Redis
        mock_redis = AsyncMock()
        store = PersistentKeyStore(redis_client=mock_redis)

        key_data = {
            "key_id": "test_key_001",
            "key_type": "signing",
            "public_key": "pk_data_here",
            "security_level": 3,
            "created_at": datetime.now(UTC).isoformat(),
            "expires_at": (datetime.now(UTC) + timedelta(days=90)).isoformat(),
            "is_active": True,
        }

        # Save
        result = await store.save_key("test_key_001", key_data)
        assert result is True

        # Verify Redis was called
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_nonexistent_key(self):
        """Test loading a key that doesn't exist."""
        from api.stores.persistent_key_store import PersistentKeyStore
        
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        store = PersistentKeyStore(redis_client=mock_redis)

        result = await store.load_key("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_key(self):
        """Test key deletion."""
        from api.stores.persistent_key_store import PersistentKeyStore
        
        mock_redis = AsyncMock()
        store = PersistentKeyStore(redis_client=mock_redis)

        result = await store.delete_key("test_key_001")
        assert result is True

        # Verify Redis was called
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_active_keys(self):
        """Test listing active keys."""
        from api.stores.persistent_key_store import PersistentKeyStore
        
        mock_redis = AsyncMock()
        mock_redis.smembers.return_value = {"key_001", "key_002"}
        mock_redis.get.return_value = None  # Simulate no keys in Redis
        store = PersistentKeyStore(redis_client=mock_redis)

        keys = await store.list_active_keys()
        assert keys == []  # Empty because Redis returns None

    @pytest.mark.asyncio
    async def test_record_key_operation_audit(self):
        """Test audit trail recording."""
        from api.stores.persistent_key_store import PersistentKeyStore
        
        mock_redis = AsyncMock()
        store = PersistentKeyStore(redis_client=mock_redis)

        result = await store.record_key_operation(
            key_id="test_key_001",
            operation="rotate",
            details={"from_key": "old_key", "to_key": "new_key"}
        )
        assert result is True

        # Verify Redis was called for audit
        mock_redis.lpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_redis_returns_false(self):
        """Test that operations fail gracefully without Redis."""
        from api.stores.persistent_key_store import PersistentKeyStore
        
        store = PersistentKeyStore()  # No Redis client

        assert await store.save_key("key", {}) is False
        assert await store.load_key("key") is None
        assert await store.delete_key("key") is False


class TestKeyRotationIntegration:
    """Test key rotation with persistent store integration."""

    @pytest.mark.asyncio
    async def test_key_persistence_on_rotation(self):
        """Test that rotated keys are persisted."""
        from api.key_rotation import KeyRotationService, RotationPolicy
        from api.stores.persistent_key_store import PersistentKeyStore
        
        # Mock Redis
        mock_redis = AsyncMock()
        persistent_store = PersistentKeyStore(redis_client=mock_redis)
        
        policy = RotationPolicy(max_age_days=90, rotate_before_days=7)
        service = KeyRotationService(
            rotation_policy=policy,
            store=persistent_store,
        )

        # Generate initial key
        key1 = await service.generate_key(key_type="signing")
        assert key1.key_id is not None

        # Rotate key
        key2 = await service.rotate_key(key1.key_id)
        assert key2.key_id != key1.key_id

        # Verify persistence was attempted
        assert mock_redis.set.call_count >= 2  # At least 2 key saves

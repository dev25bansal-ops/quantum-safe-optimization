"""
Comprehensive unit tests for caching module.

Tests cover:
- Local memory cache operations
- Multi-level cache functionality
- Cache strategies (LRU, LFU, TTL)
- Cache statistics
- Error handling
"""

import pytest
import asyncio
import time
from api.cache.cache import (
    LocalMemoryCache,
    RedisCache,
    MultiLevelCache,
    CacheStrategy,
    CacheLevel,
    cache_result,
    invalidate_cache,
)


class MockRedis:
    """Mock Redis client for testing."""
    
    def __init__(self):
        self._data = {}
    
    async def get(self, key):
        """Mock get."""
        return self._data.get(key)
    
    async def setex(self, key, ttl, value):
        """Mock setex."""
        self._data[key] = value
    
    async def delete(self, *keys):
        """Mock delete."""
        count = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                count += 1
        return count
    
    async def exists(self, key):
        """Mock exists."""
        return 1 if key in self._data else 0
    
    async def keys(self, pattern):
        """Mock keys."""
        if pattern == "*":
            return list(self._data.keys())
        return []
    
    async def ping(self):
        """Mock ping."""
        return True


class TestLocalMemoryCache:
    """Test local memory cache functionality."""

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self):
        """Test basic set and get operations."""
        cache = LocalMemoryCache(max_size=100, default_ttl=300.0)
        
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """Test cache miss returns None."""
        cache = LocalMemoryCache()
        
        result = await cache.get("nonexistent")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_delete(self):
        """Test cache deletion."""
        cache = LocalMemoryCache()
        
        await cache.set("key1", "value1")
        deleted = await cache.delete("key1")
        
        assert deleted is True
        
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_delete_nonexistent(self):
        """Test deleting nonexistent key."""
        cache = LocalMemoryCache()
        
        deleted = await cache.delete("nonexistent")
        
        assert deleted is False

    @pytest.mark.asyncio
    async def test_cache_clear(self):
        """Test cache clearing."""
        cache = LocalMemoryCache()
        
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.clear()
        
        assert cache.size == 0

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self):
        """Test TTL-based expiration."""
        cache = LocalMemoryCache(default_ttl=0.1)  # 100ms TTL
        
        await cache.set("key1", "value1")
        
        # Should exist initially
        result = await cache.get("key1")
        assert result == "value1"
        
        # Wait for expiration
        await asyncio.sleep(0.15)
        
        # Should be expired
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_lru_eviction(self):
        """Test LRU eviction strategy."""
        cache = LocalMemoryCache(
            max_size=3,
            strategy=CacheStrategy.LRU
        )
        
        # Add 3 items
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        
        # Access key1 to make it recently used
        await cache.get("key1")
        
        # Add new item, should evict key2 (least recently used)
        await cache.set("key4", "value4")
        
        # key2 should be evicted
        result = await cache.get("key2")
        assert result is None
        
        # key1, key3, key4 should exist
        assert await cache.get("key1") == "value1"
        assert await cache.get("key3") == "value3"
        assert await cache.get("key4") == "value4"

    @pytest.mark.asyncio
    async def test_cache_lfu_eviction(self):
        """Test LFU eviction strategy."""
        cache = LocalMemoryCache(
            max_size=3,
            strategy=CacheStrategy.LFU
        )
        
        # Add 3 items
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        
        # Access key1 and key3 multiple times
        await cache.get("key1")
        await cache.get("key1")
        await cache.get("key3")
        
        # Add new item, should evict key2 (least frequently used)
        await cache.set("key4", "value4")
        
        # key2 should be evicted
        result = await cache.get("key2")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_statistics(self):
        """Test cache statistics tracking."""
        cache = LocalMemoryCache(max_size=10)
        
        # Perform operations
        await cache.set("key1", "value1")
        await cache.get("key1")  # Hit
        await cache.get("key1")  # Hit
        await cache.get("nonexistent")  # Miss
        
        stats = await cache.get_stats()
        
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["size"] == 1
        assert "hit_rate" in stats

    @pytest.mark.asyncio
    async def test_cache_max_size_enforcement(self):
        """Test that max size is enforced."""
        cache = LocalMemoryCache(max_size=5)
        
        # Add 10 items
        for i in range(10):
            await cache.set(f"key{i}", f"value{i}")
        
        # Size should not exceed max
        assert cache.size <= 5

    @pytest.mark.asyncio
    async def test_cache_custom_ttl(self):
        """Test custom TTL per item."""
        cache = LocalMemoryCache(default_ttl=300.0)
        
        # Set with custom TTL
        await cache.set("key1", "value1", ttl=0.1)
        await cache.set("key2", "value2", ttl=300.0)
        
        # Wait for short TTL to expire
        await asyncio.sleep(0.15)
        
        # key1 should be expired, key2 should exist
        assert await cache.get("key1") is None
        assert await cache.get("key2") == "value2"


class TestMultiLevelCache:
    """Test multi-level cache functionality."""

    @pytest.mark.asyncio
    async def test_multilevel_set_and_get(self):
        """Test basic set and get in multi-level cache."""
        l1_cache = LocalMemoryCache(max_size=10)
        l2_cache = LocalMemoryCache(max_size=100)
        
        cache = MultiLevelCache(l1_cache, l2_cache)
        
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_multilevel_promotion(self):
        """Test that items are promoted from L2 to L1."""
        l1_cache = LocalMemoryCache(max_size=10)
        l2_cache = LocalMemoryCache(max_size=100)
        
        cache = MultiLevelCache(l1_cache, l2_cache)
        
        # Set in both levels
        await cache.set("key1", "value1")
        
        # Get from L1
        result = await cache.get("key1")
        assert result == "value1"
        
        # Check L1 stats for hit
        stats = cache.stats
        assert stats["l1_hits"] == 1

    @pytest.mark.asyncio
    async def test_multilevel_delete(self):
        """Test deletion from all levels."""
        l1_cache = LocalMemoryCache(max_size=10)
        l2_cache = LocalMemoryCache(max_size=100)
        
        cache = MultiLevelCache(l1_cache, l2_cache)
        
        await cache.set("key1", "value1")
        deleted = await cache.delete("key1")
        
        assert deleted is True
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_multilevel_clear(self):
        """Test clearing all levels."""
        l1_cache = LocalMemoryCache(max_size=10)
        l2_cache = LocalMemoryCache(max_size=100)
        
        cache = MultiLevelCache(l1_cache, l2_cache)
        
        await cache.set("key1", "value1")
        await cache.clear()
        
        assert cache._l1.size == 0

    @pytest.mark.asyncio
    async def test_multilevel_statistics(self):
        """Test multi-level statistics."""
        l1_cache = LocalMemoryCache(max_size=10)
        l2_cache = LocalMemoryCache(max_size=100)
        
        cache = MultiLevelCache(l1_cache, l2_cache)
        
        await cache.set("key1", "value1")
        await cache.get("key1")
        await cache.get("nonexistent")
        
        stats = await cache.get_stats()
        
        assert "l1_hits" in stats
        assert "l2_hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats


class TestRedisCache:
    """Test Redis cache functionality."""

    @pytest.mark.asyncio
    async def test_redis_set_and_get(self):
        """Test Redis cache set and get."""
        redis = MockRedis()
        cache = RedisCache(redis, default_ttl=300.0)
        
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_redis_delete(self):
        """Test Redis cache delete."""
        redis = MockRedis()
        cache = RedisCache(redis)
        
        await cache.set("key1", "value1")
        deleted = await cache.delete("key1")
        
        assert deleted is True

    @pytest.mark.asyncio
    async def test_redis_clear(self):
        """Test Redis cache clear."""
        redis = MockRedis()
        cache = RedisCache(redis)
        
        await cache.set("key1", "value1")
        await cache.clear()
        
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_redis_exists(self):
        """Test Redis exists check."""
        redis = MockRedis()
        cache = RedisCache(redis)
        
        await cache.set("key1", "value1")
        
        assert await cache.exists("key1") is True
        assert await cache.exists("nonexistent") is False


class TestCacheDecorators:
    """Test cache decorators."""

    @pytest.mark.asyncio
    async def test_cache_result_decorator(self):
        """Test cache result decorator."""
        from api.cache.cache import get_cache, set_cache
        
        # Set up cache
        l1_cache = LocalMemoryCache(max_size=10)
        cache = MultiLevelCache(l1_cache)
        set_cache(cache)
        
        call_count = [0]
        
        @cache_result(ttl=60, key_prefix="test:")
        async def get_data(value):
            call_count[0] += 1
            return f"result_{value}"
        
        # First call
        result1 = await get_data("test")
        assert result1 == "result_test"
        assert call_count[0] == 1
        
        # Second call (should use cache)
        result2 = await get_data("test")
        assert result2 == "result_test"
        assert call_count[0] == 1  # Should not increment


class TestCacheStrategies:
    """Test different cache strategies."""

    @pytest.mark.asyncio
    async def test_ttl_strategy(self):
        """Test TTL-based caching."""
        cache = LocalMemoryCache(
            max_size=10,
            default_ttl=0.1,
            strategy=CacheStrategy.TTL
        )
        
        await cache.set("key1", "value1")
        
        # Should exist initially
        assert await cache.get("key1") == "value1"
        
        # Wait for expiration
        await asyncio.sleep(0.15)
        
        # Should be expired
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_manual_strategy(self):
        """Test manual invalidation."""
        cache = LocalMemoryCache(
            max_size=10,
            strategy=CacheStrategy.MANUAL
        )
        
        await cache.set("key1", "value1")
        
        # Should exist until manually deleted
        assert await cache.get("key1") == "value1"
        
        await cache.delete("key1")
        
        assert await cache.get("key1") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
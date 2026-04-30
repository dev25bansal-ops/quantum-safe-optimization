"""
Comprehensive caching module for improved performance.

Provides multi-level caching with Redis backend, local memory caching,
and intelligent cache invalidation strategies.
"""

import json
import logging
import hashlib
import asyncio
from typing import Any, Dict, Optional, Callable, TypeVar, Union
from datetime import datetime, timedelta
from functools import wraps
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheLevel(Enum):
    """Cache levels for multi-level caching."""
    L1 = "l1"  # Local memory cache (fastest)
    L2 = "l2"  # Redis cache (fast)
    L3 = "l3"  # Database cache (slower)


class CacheStrategy(Enum):
    """Cache invalidation strategies."""
    TTL = "ttl"  # Time-based expiration
    LRU = "lru"  # Least recently used
    LFU = "lfu"  # Least frequently used
    MANUAL = "manual"  # Manual invalidation


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    
    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    ttl: Optional[float] = None
    size: int = 0
    
    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl is None:
            return False
        return (datetime.now() - self.created_at).total_seconds() > self.ttl
    
    @property
    def age(self) -> timedelta:
        """Get the age of this entry."""
        return datetime.now() - self.created_at
    
    def touch(self):
        """Update last accessed time and increment access count."""
        self.last_accessed = datetime.now()
        self.access_count += 1


class LocalMemoryCache:
    """Local in-memory cache (L1 cache)."""
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float = 300.0,
        strategy: CacheStrategy = CacheStrategy.LRU
    ):
        self._cache: Dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._strategy = strategy
        self._lock = asyncio.Lock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "sets": 0,
            "deletes": 0,
        }
    
    @property
    def stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return self._stats.copy()
    
    @property
    def size(self) -> int:
        """Get current cache size."""
        return len(self._cache)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        async with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats["misses"] += 1
                return None
            
            if entry.is_expired:
                await self._remove_entry(key)
                self._stats["misses"] += 1
                return None
            
            entry.touch()
            self._stats["hits"] += 1
            return entry.value
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None
    ) -> None:
        """Set value in cache."""
        async with self._lock:
            # Calculate size (rough estimate)
            size = len(json.dumps(value, default=str)) if value is not None else 0
            
            # Create entry
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                ttl=ttl or self._default_ttl,
                size=size
            )
            
            # Check if we need to evict
            if key not in self._cache and len(self._cache) >= self._max_size:
                await self._evict()
            
            self._cache[key] = entry
            self._stats["sets"] += 1
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        async with self._lock:
            if key in self._cache:
                await self._remove_entry(key)
                self._stats["deletes"] += 1
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            logger.debug("Local memory cache cleared")
    
    async def _remove_entry(self, key: str) -> None:
        """Remove entry from cache."""
        if key in self._cache:
            del self._cache[key]
    
    async def _evict(self) -> None:
        """Evict an entry based on strategy."""
        if not self._cache:
            return
        
        if self._strategy == CacheStrategy.LRU:
            # Evict least recently used
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].last_accessed
            )
            await self._remove_entry(oldest_key)
        
        elif self._strategy == CacheStrategy.LFU:
            # Evict least frequently used
            least_used_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].access_count
            )
            await self._remove_entry(least_used_key)
        
        else:
            # Default: evict oldest
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].created_at
            )
            await self._remove_entry(oldest_key)
        
        self._stats["evictions"] += 1
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get detailed cache statistics."""
        async with self._lock:
            total_size = sum(entry.size for entry in self._cache.values())
            hit_rate = (
                self._stats["hits"] / (self._stats["hits"] + self._stats["misses"])
                if (self._stats["hits"] + self._stats["misses"]) > 0
                else 0.0
            )
            
            return {
                **self._stats,
                "size": len(self._cache),
                "max_size": self._max_size,
                "total_size_bytes": total_size,
                "hit_rate": hit_rate,
                "strategy": self._strategy.value,
            }


class RedisCache:
    """Redis cache implementation (L2 cache)."""
    
    def __init__(
        self,
        redis_client: Any,
        default_ttl: float = 3600.0,
        key_prefix: str = "qsop:"
    ):
        self._redis = redis_client
        self._default_ttl = default_ttl
        self._key_prefix = key_prefix
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0,
        }
    
    @property
    def stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return self._stats.copy()
    
    def _make_key(self, key: str) -> str:
        """Create prefixed key."""
        return f"{self._key_prefix}{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache."""
        try:
            redis_key = self._make_key(key)
            value = await self._redis.get(redis_key)
            
            if value is None:
                self._stats["misses"] += 1
                return None
            
            self._stats["hits"] += 1
            return json.loads(value)
        
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            self._stats["errors"] += 1
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None
    ) -> None:
        """Set value in Redis cache."""
        try:
            redis_key = self._make_key(key)
            serialized = json.dumps(value, default=str)
            expire = ttl or self._default_ttl
            
            await self._redis.setex(redis_key, int(expire), serialized)
            self._stats["sets"] += 1
        
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            self._stats["errors"] += 1
    
    async def delete(self, key: str) -> bool:
        """Delete value from Redis cache."""
        try:
            redis_key = self._make_key(key)
            result = await self._redis.delete(redis_key)
            
            if result > 0:
                self._stats["deletes"] += 1
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            self._stats["errors"] += 1
            return False
    
    async def clear(self, pattern: str = "*") -> None:
        """Clear cache entries matching pattern."""
        try:
            pattern = self._make_key(pattern)
            keys = await self._redis.keys(pattern)
            
            if keys:
                await self._redis.delete(*keys)
                logger.debug(f"Cleared {len(keys)} Redis cache entries")
        
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            redis_key = self._make_key(key)
            return await self._redis.exists(redis_key) > 0
        
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get detailed cache statistics."""
        hit_rate = (
            self._stats["hits"] / (self._stats["hits"] + self._stats["misses"])
            if (self._stats["hits"] + self._stats["misses"]) > 0
            else 0.0
        )
        
        return {
            **self._stats,
            "hit_rate": hit_rate,
            "default_ttl": self._default_ttl,
            "key_prefix": self._key_prefix,
        }


class MultiLevelCache:
    """Multi-level cache combining L1 and L2 caches."""
    
    def __init__(
        self,
        l1_cache: LocalMemoryCache,
        l2_cache: Optional[RedisCache] = None
    ):
        self._l1 = l1_cache
        self._l2 = l2_cache
        self._stats = {
            "l1_hits": 0,
            "l2_hits": 0,
            "misses": 0,
        }
    
    @property
    def stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return self._stats.copy()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from multi-level cache."""
        # Try L1 cache first
        value = await self._l1.get(key)
        if value is not None:
            self._stats["l1_hits"] += 1
            return value
        
        # Try L2 cache
        if self._l2:
            value = await self._l2.get(key)
            if value is not None:
                self._stats["l2_hits"] += 1
                # Promote to L1 cache
                await self._l1.set(key, value)
                return value
        
        # Cache miss
        self._stats["misses"] += 1
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None
    ) -> None:
        """Set value in all cache levels."""
        # Set in L1 cache
        await self._l1.set(key, value, ttl)
        
        # Set in L2 cache if available
        if self._l2:
            await self._l2.set(key, value, ttl)
    
    async def delete(self, key: str) -> bool:
        """Delete value from all cache levels."""
        l1_deleted = await self._l1.delete(key)
        l2_deleted = True
        
        if self._l2:
            l2_deleted = await self._l2.delete(key)
        
        return l1_deleted or l2_deleted
    
    async def clear(self) -> None:
        """Clear all cache levels."""
        await self._l1.clear()
        if self._l2:
            await self._l2.clear()
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get detailed cache statistics."""
        total_requests = (
            self._stats["l1_hits"] + self._stats["l2_hits"] + self._stats["misses"]
        )
        hit_rate = (
            (self._stats["l1_hits"] + self._stats["l2_hits"]) / total_requests
            if total_requests > 0
            else 0.0
        )
        
        return {
            **self._stats,
            "hit_rate": hit_rate,
            "l1_stats": await self._l1.get_stats(),
            "l2_stats": await self._l2.get_stats() if self._l2 else None,
        }


def cache_result(
    ttl: float = 300.0,
    key_prefix: str = "",
    key_func: Optional[Callable] = None
):
    """Decorator for caching function results.
    
    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache keys
        key_func: Custom function to generate cache keys
    
    Usage:
        @cache_result(ttl=60, key_prefix="user:")
        async def get_user(user_id: str) -> User:
            return await db.get_user(user_id)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get cache instance
            from .cache import get_cache
            cache = get_cache()
            
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                key_parts = [key_prefix, func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                key_string = ":".join(key_parts)
                cache_key = hashlib.md5(key_string.encode()).hexdigest()
            
            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            await cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


def invalidate_cache(key_pattern: str):
    """Decorator to invalidate cache after function execution.
    
    Usage:
        @invalidate_cache("user:*")
        async def update_user(user_id: str, data: dict) -> User:
            return await db.update_user(user_id, data)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Execute function
            result = await func(*args, **kwargs)
            
            # Invalidate cache
            from .cache import get_cache
            cache = get_cache()
            await cache.clear(key_pattern)
            
            return result
        
        return wrapper
    return decorator


# Global cache instance
_cache: Optional[MultiLevelCache] = None


def get_cache() -> MultiLevelCache:
    """Get the global cache instance."""
    global _cache
    if _cache is None:
        # Initialize with default configuration
        l1_cache = LocalMemoryCache(max_size=1000, default_ttl=300.0)
        _cache = MultiLevelCache(l1_cache)
    return _cache


def set_cache(cache: MultiLevelCache) -> None:
    """Set the global cache instance."""
    global _cache
    _cache = cache


async def initialize_cache(redis_client: Any = None) -> MultiLevelCache:
    """Initialize cache with optional Redis backend."""
    l1_cache = LocalMemoryCache(max_size=1000, default_ttl=300.0)
    
    l2_cache = None
    if redis_client:
        l2_cache = RedisCache(redis_client, default_ttl=3600.0)
    
    cache = MultiLevelCache(l1_cache, l2_cache)
    set_cache(cache)
    
    logger.info("Cache initialized")
    return cache


async def clear_all_caches() -> None:
    """Clear all cache levels."""
    cache = get_cache()
    await cache.clear()
    logger.info("All caches cleared")
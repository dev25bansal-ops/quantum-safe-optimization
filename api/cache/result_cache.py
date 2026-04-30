"""
Result Caching Layer for Quantum Optimization Jobs.

Caches results of identical quantum optimization problems to avoid redundant computation.
Expected to provide 80%+ speedup for repeated problems.
"""

import hashlib
import json
import logging
from typing import Any, Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class ResultCache:
    """
    Cache quantum optimization results by problem hash.
    
    Features:
    - SHA-256 based problem fingerprinting
    - TTL-based expiration (default 5 minutes)
    - Redis-backed for distributed caching
    - Configurable cache key generation
    - Cache hit/miss metrics
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        ttl: int = 300,  # 5 minutes
        key_prefix: str = "qsop:qresult",
        enable_compression: bool = True,
    ):
        self.redis = redis_client
        self.ttl = ttl
        self.key_prefix = key_prefix
        self.enable_compression = enable_compression
        self._hits = 0
        self._misses = 0
    
    def _generate_cache_key(self, problem_config: dict, parameters: dict, user_id: str | None = None) -> str:
        """
        Generate unique cache key based on problem configuration.
        
        Args:
            problem_config: Problem type and parameters
            parameters: Algorithm parameters (layers, optimizer, shots, etc.)
            user_id: Optional user ID for user-specific caching
            
        Returns:
            SHA-256 hash as cache key
        """
        # Create canonical representation (sorted keys for consistency)
        cache_content = {
            "problem_config": problem_config,
            "parameters": parameters,
        }
        
        # Include user_id if provided (for user-specific caches)
        if user_id:
            cache_content["user_id"] = user_id
        
        # JSON with sorted keys ensures identical problems produce same hash
        content = json.dumps(cache_content, sort_keys=True, default=str)
        hash_val = hashlib.sha256(content.encode()).hexdigest()
        
        return f"{self.key_prefix}:{hash_val}"
    
    async def get(self, problem_config: dict, parameters: dict, user_id: str | None = None) -> dict | None:
        """
        Get cached result for a problem.
        
        Args:
            problem_config: Problem configuration
            parameters: Algorithm parameters
            user_id: Optional user ID
            
        Returns:
            Cached result or None if not found
        """
        cache_key = self._generate_cache_key(problem_config, parameters, user_id)
        
        try:
            cached = await self.redis.get(cache_key)
            if cached:
                self._hits += 1
                logger.debug(
                    "cache_hit",
                    cache_key=cache_key[:16] + "...",
                    total_hits=self._hits,
                    total_misses=self._misses,
                    hit_rate=self.hit_rate,
                )
                return json.loads(cached)
            
            self._misses += 1
            return None
            
        except Exception as e:
            logger.warning("cache_get_error", error=str(e), cache_key=cache_key[:16] + "...")
            return None
    
    async def set(
        self,
        problem_config: dict,
        parameters: dict,
        result: dict,
        user_id: str | None = None,
        ttl: int | None = None,
    ) -> bool:
        """
        Cache a result for a problem.
        
        Args:
            problem_config: Problem configuration
            parameters: Algorithm parameters
            result: Computation result to cache
            user_id: Optional user ID
            ttl: Override default TTL (seconds)
            
        Returns:
            True if cached successfully
        """
        cache_key = self._generate_cache_key(problem_config, parameters, user_id)
        
        try:
            # Serialize result
            serialized = json.dumps(result, default=str)
            
            # Set with TTL
            actual_ttl = ttl or self.ttl
            await self.redis.set(cache_key, serialized, ex=actual_ttl)
            
            logger.debug(
                "cache_set",
                cache_key=cache_key[:16] + "...",
                ttl=actual_ttl,
                result_size=len(serialized),
            )
            
            return True
            
        except Exception as e:
            logger.warning("cache_set_error", error=str(e), cache_key=cache_key[:16] + "...")
            return False
    
    async def invalidate(self, problem_config: dict, parameters: dict, user_id: str | None = None) -> bool:
        """
        Invalidate cached result for a specific problem.
        
        Args:
            problem_config: Problem configuration
            parameters: Algorithm parameters
            user_id: Optional user ID
            
        Returns:
            True if key was deleted
        """
        cache_key = self._generate_cache_key(problem_config, parameters, user_id)
        
        try:
            deleted = await self.redis.delete(cache_key)
            if deleted:
                logger.debug("cache_invalidated", cache_key=cache_key[:16] + "...")
            return deleted > 0
            
        except Exception as e:
            logger.warning("cache_invalidate_error", error=str(e))
            return False
    
    async def invalidate_all_for_user(self, user_id: str) -> int:
        """
        Invalidate all cached results for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Number of keys deleted
        """
        try:
            pattern = f"{self.key_prefix}:*"
            deleted_count = 0
            
            # Scan and delete matching keys
            async for key in self.redis.scan_iter(match=pattern, count=100):
                # Decode key if bytes
                key_str = key.decode() if isinstance(key, bytes) else key
                
                # Try to get and check if it belongs to this user
                cached = await self.redis.get(key)
                if cached:
                    data = json.loads(cached)
                    if data.get("user_id") == user_id:
                        await self.redis.delete(key)
                        deleted_count += 1
            
            if deleted_count > 0:
                logger.info("cache_invalidated_for_user", user_id=user_id, count=deleted_count)
            
            return deleted_count
            
        except Exception as e:
            logger.warning("cache_invalidate_all_error", error=str(e), user_id=user_id)
            return 0
    
    async def get_stats(self) -> dict:
        """Get cache statistics."""
        try:
            # Get Redis info
            info = await self.redis.info()
            
            # Count cache keys
            key_count = 0
            async for _ in self.redis.scan_iter(match=f"{self.key_prefix}:*", count=100):
                key_count += 1
            
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self.hit_rate,
                "total_requests": self._hits + self._misses,
                "cached_results": key_count,
                "ttl_seconds": self.ttl,
                "redis_memory_used": info.get("used_memory_human", "unknown"),
                "redis_connected_clients": info.get("connected_clients", 0),
            }
        except Exception as e:
            logger.warning("cache_stats_error", error=str(e))
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self.hit_rate,
                "total_requests": self._hits + self._misses,
                "error": str(e),
            }
    
    async def clear_all(self) -> int:
        """
        Clear all cached results.
        
        Returns:
            Number of keys deleted
        """
        try:
            pattern = f"{self.key_prefix}:*"
            deleted_count = 0
            
            async for key in self.redis.scan_iter(match=pattern, count=100):
                await self.redis.delete(key)
                deleted_count += 1
            
            logger.info("cache_cleared", count=deleted_count)
            return deleted_count
            
        except Exception as e:
            logger.warning("cache_clear_error", error=str(e))
            return 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return self._hits / total
    
    async def close(self):
        """Close Redis connection."""
        try:
            await self.redis.close()
            logger.info("cache_connection_closed")
        except Exception as e:
            logger.warning("cache_close_error", error=str(e))


class NoOpResultCache:
    """
    No-op cache implementation for when caching is disabled.
    Implements the same interface but does nothing.
    """
    
    def __init__(self):
        self._hits = 0
        self._misses = 0
    
    async def get(self, *args, **kwargs) -> None:
        self._misses += 1
        return None
    
    async def set(self, *args, **kwargs) -> bool:
        return True
    
    async def invalidate(self, *args, **kwargs) -> bool:
        return True
    
    async def invalidate_all_for_user(self, user_id: str) -> int:
        return 0
    
    async def get_stats(self) -> dict:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": 0.0,
            "status": "disabled",
        }
    
    async def clear_all(self) -> int:
        return 0
    
    async def close(self):
        pass


# Module-level cache instance
_cache: ResultCache | NoOpResultCache | None = None


async def init_result_cache(
    redis_url: str | None = None,
    ttl: int = 300,
    enabled: bool = True,
) -> ResultCache | NoOpResultCache:
    """
    Initialize the result cache.
    
    Args:
        redis_url: Redis connection URL
        ttl: Cache TTL in seconds
        enabled: Whether to enable caching
        
    Returns:
        Cache instance
    """
    global _cache
    
    if not enabled:
        logger.info("result_cache_disabled")
        _cache = NoOpResultCache()
        return _cache
    
    if not redis_url:
        logger.warning("result_cache_no_redis_url")
        _cache = NoOpResultCache()
        return _cache
    
    try:
        redis_client = redis.from_url(redis_url, decode_responses=True)
        await redis_client.ping()
        
        _cache = ResultCache(
            redis_client=redis_client,
            ttl=ttl,
        )
        
        logger.info("result_cache_initialized", ttl=ttl)
        return _cache
        
    except Exception as e:
        logger.error("result_cache_init_failed", error=str(e))
        _cache = NoOpResultCache()
        return _cache


def get_result_cache() -> ResultCache | NoOpResultCache:
    """Get the current cache instance."""
    if _cache is None:
        logger.warning("result_cache_not_initialized")
        return NoOpResultCache()
    return _cache


async def close_result_cache():
    """Close the result cache."""
    global _cache
    if _cache:
        await _cache.close()
        _cache = None
        logger.info("result_cache_closed")

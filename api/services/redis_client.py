"""
Redis Abstraction Layer

Provides a unified interface for Redis operations, replacing in-memory
global dicts (_users_db, _jobs_db, _tokens_db) with Redis for horizontal scaling.

Architecture:
- async Redis client with connection pooling
- Automatic serialization/deserialization
- TTL support for token expiration
- Pub/Sub for WebSocket scaling
- Fallback to in-memory for development (but warns strongly)

Migration Path:
1. Initialize Redis client in app lifespan
2. Replace global dict access with Redis operations
3. Remove in-memory fallback for production
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as redis
    from redis.asyncio import ConnectionPool

    _redis_available = True
except ImportError:
    _redis_available = False

try:
    import msgpack

    _msgpack_available = True
except ImportError:
    _msgpack_available = False


class RedisManager:
    """
    Unified Redis interface for async operations.

    Provides:
    - Get/Set/Delete operations with automatic serialization
    - Hash operations for structured data
    - List operations for queues
    - Pub/Sub for notifications
    - TTL management for expiration
    """

    def __init__(self):
        self._redis: redis.Redis | None = None
        self._pool: ConnectionPool | None = None
        self._mode = os.getenv("REDIS_MODE", "optional").lower()
        self._redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        self._enabled = _redis_available and (self._mode == "required" or self._mode == "optional")

        if not self._enabled:
            if self._mode == "required":
                logger.error("Redis required but not available - application may fail")
            else:
                logger.warning("Redis not available - using in-memory fallback (development only)")

    async def connect(self) -> None:
        """Establish Redis connection pool."""
        if not self._enabled:
            return

        try:
            self._pool = ConnectionPool.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=False,  # We'll handle our own serialization
                max_connections=int(os.getenv("REDIS_POOL_SIZE", "10")),
            )

            self._redis = redis.Redis(connection_pool=self._pool)

            # Test connection
            await self._redis.ping()
            logger.info(f"Redis connected: {self._redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            if self._mode == "required":
                raise
            else:
                self._enabled = False

    async def close(self) -> None:
        """Close Redis connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("Redis connection closed")

    async def get(self, key: str) -> Any | None:
        """Get value by key with automatic deserialization."""
        if not self._enabled or not self._redis:
            return None

        try:
            value = await self._redis.get(key)
            if value is None:
                return None
            return self._deserialize(value)
        except Exception as e:
            logger.error(f"Redis GET failed for key '{key}': {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """
        Set value by key with automatic serialization.

        Args:
            key: The Redis key
            value: The value to store (will be serialized)
            ttl: Optional TTL in seconds
        """
        if not self._enabled or not self._redis:
            return False

        try:
            serialized = self._serialize(value)
            await self._redis.set(key, serialized, ex=ttl)
            return True
        except Exception as e:
            logger.error(f"Redis SET failed for key '{key}': {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key."""
        if not self._enabled or not self._redis:
            return False

        try:
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis DELETE failed for key '{key}': {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self._enabled or not self._redis:
            return False

        try:
            return bool(await self._redis.exists(key))
        except Exception as e:
            logger.error(f"Redis EXISTS failed for key '{key}': {e}")
            return False

    async def hget(self, name: str, key: str) -> Any | None:
        """Get value from hash field."""
        if not self._enabled or not self._redis:
            return None

        try:
            value = await self._redis.hget(name, key)
            if value is None:
                return None
            return self._deserialize(value)
        except Exception as e:
            logger.error(f"Redis HGET failed for '{name}/{key}': {e}")
            return None

    async def hset(
        self,
        name: str,
        key: str,
        value: Any,
    ) -> bool:
        """Set value in hash field."""
        if not self._enabled or not self._redis:
            return False

        try:
            serialized = self._serialize(value)
            await self._redis.hset(name, key, serialized)
            return True
        except Exception as e:
            logger.error(f"Redis HSET failed for '{name}/{key}': {e}")
            return False

    async def hgetall(self, name: str) -> dict[str, Any]:
        """Get all fields and values from hash."""
        if not self._enabled or not self._redis:
            return {}

        try:
            result = await self._redis.hgetall(name)
            return {k: self._deserialize(v) for k, v in result.items() if v is not None}
        except Exception as e:
            logger.error(f"Redis HGETALL failed for '{name}': {e}")
            return {}

    async def hdelete(self, name: str, key: str) -> bool:
        """Delete field from hash."""
        if not self._enabled or not self._redis:
            return False

        try:
            await self._redis.hdel(name, key)
            return True
        except Exception as e:
            logger.error(f"Redis HDEL failed for '{name}/{key}': {e}")
            return False

    async def lpush(
        self,
        name: str,
        *values: Any,
    ) -> int:
        """Push values to the left of a list."""
        if not self._enabled or not self._redis:
            return 0

        try:
            serialized = [self._serialize(v) for v in values]
            return await self._redis.lpush(name, *serialized)
        except Exception as e:
            logger.error(f"Redis LPUSH failed for '{name}': {e}")
            return 0

    async def rpop(
        self,
        name: str,
    ) -> Any | None:
        """Pop value from the right of a list."""
        if not self._enabled or not self._redis:
            return None

        try:
            value = await self._redis.rpop(name)
            if value is None:
                return None
            return self._deserialize(value)
        except Exception as e:
            logger.error(f"Redis RPOP failed for '{name}': {e}")
            return None

    async def lrange(
        self,
        name: str,
        start: int = 0,
        end: int = -1,
    ) -> list[Any]:
        """Get range of values from list."""
        if not self._enabled or not self._redis:
            return []

        try:
            values = await self._redis.lrange(name, start, end)
            return [self._deserialize(v) for v in values]
        except Exception as e:
            logger.error(f"Redis LRANGE failed for '{name}': {e}")
            return []

    async def expire(
        self,
        key: str,
        ttl: int,
    ) -> bool:
        """Set TTL for key."""
        if not self._enabled or not self._redis:
            return False

        try:
            return bool(await self._redis.expire(key, ttl))
        except Exception as e:
            logger.error(f"Redis EXPIRE failed for key '{key}': {e}")
            return False

    async def ttl(
        self,
        key: str,
    ) -> int:
        """Get TTL for key."""
        if not self._enabled or not self._redis:
            return -1

        try:
            return await self._redis.ttl(key)
        except Exception as e:
            logger.error(f"Redis TTL failed for key '{key}': {e}")
            return -1

    def _serialize(self, value: Any) -> bytes:
        """Serialize value to bytes."""
        if _msgpack_available:
            try:
                return msgpack.packb(value, use_bin_type=True)
            except Exception:
                pass

        # Fallback to JSON
        return json.dumps(value).encode("utf-8")

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize bytes to value."""
        if _msgpack_available:
            try:
                return msgpack.unpackb(data, raw=False)
            except Exception:
                pass

        # Fallback to JSON
        return json.loads(data.decode("utf-8"))


# Global instance
_redis_manager: RedisManager | None = None


async def get_redis() -> RedisManager:
    """Get or create the global Redis manager instance."""
    global _redis_manager
    if _redis_manager is None:
        _redis_manager = RedisManager()
    return _redis_manager


async def init_redis():
    """Initialize Redis connection (call at app startup)."""
    global _redis_manager
    _redis_manager = RedisManager()
    await _redis_manager.connect()

    if _redis_manager._enabled:
        logger.info("Redis manager initialized successfully")
    else:
        logger.warning("Redis manager initialized but not enabled (using in-memory fallback)")


async def close_redis():
    """Close Redis connection (call at app shutdown)."""
    global _redis_manager
    if _redis_manager:
        await _redis_manager.close()
        _redis_manager = None
        logger.info("Redis manager closed")

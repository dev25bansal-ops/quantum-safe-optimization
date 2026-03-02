"""
Redis Storage Adapter for Global State

Replaces in-memory global dicts (_users_db, _jobs_db, _tokens_db) with
Redis-backed storage for horizontal scaling.

Usage:
    from api.storage.redis_adapter import get_redis_store

    # Users
    users_store = get_redis_store("users")
    await users_store.set(user_id, user_data)
    user = await users_store.get(user_id)

    # Jobs
    jobs_store = get_redis_store("jobs")
    await jobs_store.set(job_id, job_data)
    job = await jobs_store.get(job_id)

    # Tokens
    tokens_store = get_redis_store("tokens")
    await tokens_store.set(token, token_data)
    token = await tokens_store.get(token)
"""

import logging
from typing import Any

from api.services.redis_client import get_redis

logger = logging.getLogger(__name__)


class RedisStore:
    """
    Redis-backed key-value store compatible with dict-like operations.

    Provides async get/set/delete operations with automatic serialization.
    """

    def __init__(self, prefix: str, default_ttl: int | None = None):
        """
        Initialize Redis store.

        Args:
            prefix: Key prefix for this store (e.g., "users", "jobs", "tokens")
            default_ttl: Default TTL for keys in seconds (None for no expiration)
        """
        self._prefix = prefix
        self._default_ttl = default_ttl

    def _key(self, key: str) -> str:
        """Add prefix to key."""
        return f"{self._prefix}:{key}"

    async def get(self, key: str) -> Any | None:
        """Get value by key."""
        redis = await get_redis()
        return await redis.get(self._key(key))

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """
        Set value for key.

        Args:
            key: The key
            value: The value (will be serialized)
            ttl: Optional TTL in seconds (overrides default_ttl)
        """
        redis = await get_redis()
        effective_ttl = ttl if ttl is not None else self._default_ttl
        return await redis.set(self._key(key), value, ttl=effective_ttl)

    async def delete(self, key: str) -> bool:
        """Delete key."""
        redis = await get_redis()
        return await redis.delete(self._key(key))

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        redis = await get_redis()
        return await redis.exists(self._key(key))

    async def keys(self, pattern: str = "*") -> list[str]:
        """Get all keys matching pattern."""
        redis = await get_redis()
        raw_keys = await redis._redis.keys(f"{self._prefix}:{pattern}")  # type: ignore
        # Remove prefix from keys
        return [k.decode("utf-8").replace(f"{self._prefix}:", "") for k in raw_keys]

    async def items(self) -> list[tuple[str, Any]]:
        """Get all key-value pairs."""
        keys = await self.keys()
        items = []
        for key in keys:
            value = await self.get(key)
            if value is not None:
                items.append((key, value))
        return items

    async def values(self) -> list[Any]:
        """Get all values."""
        keys = await self.keys()
        values = []
        for key in keys:
            value = await self.get(key)
            if value is not None:
                values.append(value)
        return values

    async def clear(self) -> bool:
        """Delete all keys in this store."""
        keys = await self.keys()
        if keys:
            redis = await get_redis()
            for key in keys:
                await redis.delete(self._key(key))
        return True


# Global store instances
_users_store: RedisStore | None = None
_jobs_store: RedisStore | None = None
_tokens_store: RedisStore | None = None


def get_redis_store(store_type: str) -> RedisStore:
    """
    Get or create a Redis store instance.

    Args:
        store_type: Type of store (users, jobs, tokens, or custom prefix)

    Returns:
        RedisStore instance
    """
    # Known stores with specific TTLs
    store_configs = {
        "users": ("users", None),  # Users don't expire
        "jobs": ("jobs", None),  # Jobs don't expire
        "tokens": ("tokens", 86400),  # Tokens expire in 24 hours
        "sessions": ("sessions", 3600),  # Sessions expire in 1 hour
        "cache": ("cache", 600),  # Cache expires in 10 minutes
    }

    global _users_store, _jobs_store, _tokens_store

    if store_type == "users":
        if _users_store is None:
            _users_store = RedisStore("users")
        return _users_store
    elif store_type == "jobs":
        if _jobs_store is None:
            _jobs_store = RedisStore("jobs")
        return _jobs_store
    elif store_type == "tokens":
        if _tokens_store is None:
            _tokens_store = RedisStore("tokens", default_ttl=86400)
        return _tokens_store
    elif store_type in store_configs:
        prefix, ttl = store_configs[store_type]
        return RedisStore(prefix, default_ttl=ttl)
    else:
        # Custom store
        return RedisStore(store_type)


async def migrate_in_memory_to_redis(
    source_dict: dict[str, Any],
    target_store: RedisStore,
) -> int:
    """
    Migrate data from in-memory dict to Redis store.

    Args:
        source_dict: The source dictionary
        target_store: The target Redis store

    Returns:
        Number of items migrated
    """
    count = 0
    for key, value in source_dict.items():
        await target_store.set(key, value)
        count += 1

    logger.info(f"Migrated {count} items to Redis store '{target_store._prefix}'")
    return count

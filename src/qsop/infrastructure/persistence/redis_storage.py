"""
Redis-based storage for users, jobs, and keys.

Mandatory Redis storage with no in-memory fallbacks for production scaling.
All data is persisted in Redis for horizontal scale-out support.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, UTC
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class RedisStorage:
    """
    Redis storage layer for production-grade persistence.

    Provides:
    - Hash-based storage for users, jobs, keys
    - TTL support for tokens
    - Pub/Sub for distributed events
    - No in-memory fallback (enforces production requirements)
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        key_prefix: str = "qsop:",
    ):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        """
        Connect to Redis.

        Raises:
            RuntimeError: If Redis connection fails
        """
        try:
            self._client = aioredis.from_url(
                self.redis_url,
                decode_responses=True,
                encoding="utf-8",
            )
            await self._client.ping()
            logger.info(f"Connected to Redis at {self.redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise RuntimeError(
                f"Redis connection required for production. "
                f"Failed to connect to {self.redis_url}: {e}"
            ) from e

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Disconnected from Redis")

    def _key(self, *parts: str) -> str:
        """Build a Redis key with prefix."""
        return f"{self.key_prefix}{':'.join(parts)}"

    async def user_create(self, username: str, user_data: dict[str, Any]) -> None:
        """
        Create or update a user.

        Args:
            username: User's username (primary key)
            user_data: User data dictionary
        """
        if not self._client:
            raise RuntimeError("Redis not connected")

        key = self._key("users", username)
        await self._client.hset(key, mapping=user_data)
        logger.debug(f"Created/updated user: {username}")

    async def user_get_by_username(self, username: str) -> dict[str, Any] | None:
        """
        Get user by username.

        Args:
            username: User's username

        Returns:
            User data or None if not found
        """
        if not self._client:
            raise RuntimeError("Redis not connected")

        key = self._key("users", username)
        data = await self._client.hgetall(key)

        if not data:
            return None

        return dict(data)

    async def user_get_by_user_id(self, user_id: str) -> dict[str, Any] | None:
        """
        Get user by user_id (requires scanning all users).

        Args:
            user_id: User's ID

        Returns:
            User data or None if not found

        Note:
            In production, maintain a secondary index: users_by_id:{user_id} -> username
        """
        if not self._client:
            raise RuntimeError("Redis not connected")

        pattern = self._key("users", "*")
        async for key in self._client.scan_iter(match=pattern):
            data = await self._client.hgetall(key)
            if data.get("user_id") == user_id:
                return dict(data)

        return None

    async def user_list(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """
        List users with pagination.

        Args:
            limit: Maximum number of users to return
            offset: Number of users to skip

        Returns:
            List of user data dictionaries
        """
        if not self._client:
            raise RuntimeError("Redis not connected")

        users = []
        pattern = self._key("users", "*")
        count = 0
        skipped = 0

        async for key in self._client.scan_iter(match=pattern):
            if skipped < offset:
                skipped += 1
                continue

            if len(users) >= limit:
                break

            data = await self._client.hgetall(key)
            users.append(dict(data))

        return users

    async def job_create(self, job_id: str, job_data: dict[str, Any]) -> None:
        """
        Create or update a job.

        Args:
            job_id: Job ID (primary key)
            job_data: Job data dictionary
        """
        if not self._client:
            raise RuntimeError("Redis not connected")

        key = self._key("jobs", job_id)
        await self._client.hset(key, mapping=job_data)

        # Index by user_id for listing
        user_id = job_data.get("user_id")
        if user_id:
            user_jobs_key = self._key("user_jobs", user_id)
            await self._client.sadd(user_jobs_key, job_id)

        logger.debug(f"Created/updated job: {job_id}")

    async def job_get(self, job_id: str) -> dict[str, Any] | None:
        """
        Get job by ID.

        Args:
            job_id: Job ID

        Returns:
            Job data or None if not found
        """
        if not self._client:
            raise RuntimeError("Redis not connected")

        key = self._key("jobs", job_id)
        data = await self._client.hgetall(key)

        if not data:
            return None

        return dict(data)

    async def job_delete(self, job_id: str) -> bool:
        """
        Delete a job.

        Args:
            job_id: Job ID

        Returns:
            True if deleted, False if not found
        """
        if not self._client:
            raise RuntimeError("Redis not connected")

        key = self._key("jobs", job_id)
        data = await self._client.hgetall(key)

        if data:
            user_id = data.get("user_id")
            if user_id:
                user_jobs_key = self._key("user_jobs", user_id)
                await self._client.srem(user_jobs_key, job_id)

        result = await self._client.delete(key)
        return result > 0

    async def job_list(
        self,
        user_id: str,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        List jobs for a user with optional filters and pagination.

        Args:
            user_id: User ID
            filters: Optional filters (e.g., {"status": "completed"})
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip

        Returns:
            List of job data dictionaries
        """
        if not self._client:
            raise RuntimeError("Redis not connected")

        # Check if filters require full scan
        needs_scan = filters and any(k != "status" for k in filters.keys())

        jobs = []

        if filters and "status" in filters and not needs_scan:
            # Optimized: scan user's jobs and filter by status
            user_jobs_key = self._key("user_jobs", user_id)
            job_ids = await self._client.smembers(user_jobs_key)

            for job_id in job_ids:
                if len(jobs) >= limit:
                    break

                data = await self.job_get(job_id)
                if data and data.get("status") == filters["status"]:
                    jobs.append(data)
        else:
            # Full scan mode
            pattern = self._key("jobs", "*")
            count = 0
            skipped = 0

            async for key in self._client.scan_iter(match=pattern):
                if skipped < offset:
                    skipped += 1
                    continue

                if len(jobs) >= limit:
                    break

                data = await self._client.hgetall(key)

                # Filter by user_id
                if data.get("user_id") != user_id:
                    continue

                # Apply additional filters
                if filters:
                    matches = True
                    for k, v in filters.items():
                        if data.get(k) != v:
                            matches = False
                            break
                    if not matches:
                        continue

                jobs.append(dict(data))

        return jobs

    async def job_count(
        self,
        user_id: str,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """
        Count jobs for a user with optional filters.

        Args:
            user_id: User ID
            filters: Optional filters

        Returns:
            Number of matching jobs
        """
        if not self._client:
            raise RuntimeError("Redis not connected")

        if filters and "status" in filters and len(filters) == 1:
            # Optimized count
            user_jobs_key = self._key("user_jobs", user_id)
            job_ids = await self._client.smembers(user_jobs_key)

            count = 0
            for job_id in job_ids:
                data = await self.job_get(job_id)
                if data and data.get("status") == filters["status"]:
                    count += 1
            return count

        # Full scan count
        pattern = self._key("jobs", "*")
        total = 0

        async for key in self._client.scan_iter(match=pattern):
            data = await self._client.hgetall(key)

            if data.get("user_id") != user_id:
                continue

            if filters:
                matches = True
                for k, v in filters.items():
                    if data.get(k) != v:
                        matches = False
                        break
                if not matches:
                    continue

            total += 1

        return total

    async def key_create(self, user_id: str, key_data: dict[str, Any]) -> None:
        """
        Create or update encryption keys for a user.

        Args:
            user_id: User ID
            key_data: Key data dictionary
        """
        if not self._client:
            raise RuntimeError("Redis not connected")

        key = self._key("keys", user_id)
        await self._client.hset(key, mapping=key_data)
        logger.debug(f"Created/updated keys for user: {user_id}")

    async def key_get(self, user_id: str) -> dict[str, Any] | None:
        """
        Get encryption keys for a user.

        Args:
            user_id: User ID

        Returns:
            Key data or None if not found
        """
        if not self._client:
            raise RuntimeError("Redis not connected")

        key = self._key("keys", user_id)
        data = await self._client.hgetall(key)

        if not data:
            return None

        return dict(data)

    async def token_create(
        self,
        token: str,
        token_data: dict[str, Any],
        ttl_seconds: int | None = None,
    ) -> None:
        """
        Create a token with optional TTL.

        Args:
            token: Token string
            token_data: Token data dictionary
            ttl_seconds: TTL in seconds (default: 24 hours)
        """
        if not self._client:
            raise RuntimeError("Redis not connected")

        key = self._key("tokens", token)
        await self._client.hset(key, mapping=token_data)

        # Set TTL (24 hours by default)
        ttl = ttl_seconds or 86400
        await self._client.expire(key, ttl)

        # Index by JTI for revocation checking
        jti = token_data.get("jti")
        if jti:
            jti_key = self._key("tokens_by_jti", jti)
            await self._client.set(jti_key, token, ex=ttl)

        logger.debug(f"Created token: {token[:20]}...")

    async def token_get(self, token: str) -> dict[str, Any] | None:
        """
        Get token data.

        Args:
            token: Token string

        Returns:
            Token data or None if not found
        """
        if not self._client:
            raise RuntimeError("Redis not connected")

        key = self._key("tokens", token)
        data = await self._client.hgetall(key)

        if not data:
            return None

        return dict(data)

    async def token_revoke(self, token: str) -> bool:
        """
        Revoke a token by deleting it.

        Args:
            token: Token string

        Returns:
            True if revoked, False if not found
        """
        if not self._client:
            raise RuntimeError("Redis not connected")

        key = self._key("tokens", token)
        data = await self._client.hgetall(key)

        if data:
            jti = data.get("jti")
            if jti:
                jti_key = self._key("tokens_by_jti", jti)
                await self._client.delete(jti_key)

        result = await self._client.delete(key)
        return result > 0

    async def token_revoke_by_jti(self, jti: str) -> bool:
        """
        Revoke a token by JTI (JWT ID).

        Args:
            jti: JWT ID

        Returns:
            True if revoked, False if not found
        """
        if not self._client:
            raise RuntimeError("Redis not connected")

        jti_key = self._key("tokens_by_jti", jti)
        token = await self._client.get(jti_key)

        if token:
            await self._client.delete(jti_key)
            token_key = self._key("tokens", token)
            return await self._client.delete(token_key) > 0

        return False

    async def token_revoke_all_for_user(self, user_id: str) -> int:
        """
        Revoke all tokens for a user.

        Args:
            user_id: User ID

        Returns:
            Number of tokens revoked
        """
        if not self._client:
            raise RuntimeError("Redis not connected")

        count = 0
        pattern = self._key("tokens", "*")

        async for key in self._client.scan_iter(match=pattern):
            data = await self._client.hgetall(key)
            if data.get("user_id") == user_id:
                jti = data.get("jti")
                if jti:
                    jti_key = self._key("tokens_by_jti", jti)
                    await self._client.delete(jti_key)

                await self._client.delete(key)
                count += 1

        return count

    async def publish_event(
        self,
        channel: str,
        event_data: dict[str, Any],
    ) -> None:
        """
        Publish an event to a Redis channel for distributed consumption.

        Args:
            channel: Channel name
            event_data: Event data to publish
        """
        if not self._client:
            raise RuntimeError("Redis not connected")

        await self._client.publish(channel, json.dumps(event_data))
        logger.debug(f"Published event to {channel}: {event_data.get('type')}")

    def create_subscription(self, *channels: str) -> aioredis.client.PubSub:
        """
        Create a Redis pub/sub subscription.

        Args:
            *channels: Channel names to subscribe to

        Returns:
            PubSub object
        """
        if not self._client:
            raise RuntimeError("Redis not connected")

        pubsub = self._client.pubsub()
        for channel in channels:
            pubsub.subscribe(channel)

        return pubsub


# Global storage instance
_global_storage: RedisStorage | None = None


def get_storage() -> RedisStorage:
    """
    Get global Redis storage instance.

    Returns:
        RedisStorage instance

    Raises:
        RuntimeError: If storage not initialized
    """
    global _global_storage
    if _global_storage is None:
        raise RuntimeError(
            "Redis storage not initialized. Call init_storage() during application startup."
        )
    return _global_storage


async def init_storage(
    redis_url: str = "redis://localhost:6379/0",
) -> RedisStorage:
    """
    Initialize global Redis storage.

    Args:
        redis_url: Redis connection URL

    Returns:
        Initialized RedisStorage instance

    Raises:
        RuntimeError: If Redis connection fails
    """
    global _global_storage

    if _global_storage is None:
        _global_storage = RedisStorage(redis_url=redis_url)
        await _global_storage.connect()

    return _global_storage


async def close_storage() -> None:
    """Close global Redis storage."""
    global _global_storage

    if _global_storage:
        await _global_storage.disconnect()
        _global_storage = None


__all__ = [
    "RedisStorage",
    "get_storage",
    "init_storage",
    "close_storage",
]

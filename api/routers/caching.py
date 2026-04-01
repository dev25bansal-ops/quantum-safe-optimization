"""
Result Caching Service with Redis.

Features:
- Redis-backed caching with TTL
- LRU eviction policy
- Cache invalidation patterns
- Cache warming strategies
- Fallback to in-memory cache
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.routers.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cache", tags=["Caching"])

_memory_cache: dict[str, dict] = {}
_cache_stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0}


class CacheEntry(BaseModel):
    """Cache entry."""

    key: str
    value: Any
    created_at: datetime
    expires_at: datetime | None
    ttl_seconds: int | None
    size_bytes: int
    tags: list[str] = []


class CacheStats(BaseModel):
    """Cache statistics."""

    hits: int
    misses: int
    sets: int
    deletes: int
    hit_rate: float
    total_entries: int
    memory_entries: int
    redis_connected: bool


class CacheSetRequest(BaseModel):
    """Request to set a cache value."""

    key: str
    value: Any
    ttl_seconds: int | None = Field(None, ge=1, le=86400, description="TTL in seconds (max 24h)")
    tags: list[str] = Field(default_factory=list)


class CacheBatchSetRequest(BaseModel):
    """Request to set multiple cache values."""

    entries: list[CacheSetRequest]


class CacheKeyPattern(BaseModel):
    """Cache key pattern for deletion."""

    pattern: str


async def get_redis_client():
    """Get Redis client."""
    try:
        from api.services.redis_client import get_redis

        return await get_redis()
    except Exception:
        return None


def compute_hash(data: Any) -> str:
    """Compute a hash of the data for cache key."""
    if isinstance(data, dict):
        data_str = json.dumps(data, sort_keys=True)
    else:
        data_str = str(data)
    return hashlib.sha256(data_str.encode()).hexdigest()[:16]


def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """Generate a cache key from prefix and arguments."""
    key_parts = [prefix]

    for arg in args:
        if isinstance(arg, dict):
            key_parts.append(compute_hash(arg))
        else:
            key_parts.append(str(arg)[:32])

    for k, v in sorted(kwargs.items()):
        if isinstance(v, dict):
            key_parts.append(f"{k}:{compute_hash(v)}")
        else:
            key_parts.append(f"{k}:{str(v)[:32]}")

    return ":".join(key_parts)


async def cache_get(key: str) -> Any | None:
    """Get a value from cache."""
    global _cache_stats

    redis = await get_redis_client()

    if redis:
        try:
            value = await redis.get(f"cache:{key}")
            if value:
                _cache_stats["hits"] += 1
                return json.loads(value)
        except Exception as e:
            logger.warning(f"Redis get error: {e}")

    if key in _memory_cache:
        entry = _memory_cache[key]
        if entry.get("expires_at"):
            expires_at = datetime.fromisoformat(entry["expires_at"])
            if datetime.now(timezone.utc) > expires_at:
                del _memory_cache[key]
                _cache_stats["misses"] += 1
                return None

        _cache_stats["hits"] += 1
        return entry.get("value")

    _cache_stats["misses"] += 1
    return None


async def cache_set(
    key: str,
    value: Any,
    ttl_seconds: int | None = None,
    tags: list[str] | None = None,
) -> bool:
    """Set a value in cache."""
    global _cache_stats

    redis = await get_redis_client()
    tags = tags or []

    now = datetime.now(timezone.utc)
    expires_at = None
    if ttl_seconds:
        expires_at = now + timedelta(seconds=ttl_seconds)

    value_json = json.dumps(value)
    size_bytes = len(value_json.encode())

    if redis:
        try:
            redis_key = f"cache:{key}"

            if ttl_seconds:
                await redis.setex(redis_key, ttl_seconds, value_json)
            else:
                await redis.set(redis_key, value_json)

            for tag in tags:
                await redis.sadd(f"cache_tag:{tag}", key)

            _cache_stats["sets"] += 1
            return True
        except Exception as e:
            logger.warning(f"Redis set error: {e}")

    if len(_memory_cache) >= 10000:
        oldest_key = min(_memory_cache.keys(), key=lambda k: _memory_cache[k].get("created_at", ""))
        del _memory_cache[oldest_key]

    _memory_cache[key] = {
        "value": value,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat() if expires_at else None,
        "ttl_seconds": ttl_seconds,
        "size_bytes": size_bytes,
        "tags": tags,
    }

    _cache_stats["sets"] += 1
    return True


async def cache_delete(key: str) -> bool:
    """Delete a value from cache."""
    global _cache_stats

    redis = await get_redis_client()
    deleted = False

    if redis:
        try:
            result = await redis.delete(f"cache:{key}")
            deleted = result > 0
        except Exception as e:
            logger.warning(f"Redis delete error: {e}")

    if key in _memory_cache:
        del _memory_cache[key]
        deleted = True

    if deleted:
        _cache_stats["deletes"] += 1

    return deleted


async def cache_delete_by_pattern(pattern: str) -> int:
    """Delete cache entries matching a pattern."""
    deleted = 0

    redis = await get_redis_client()

    if redis:
        try:
            keys = []
            async for key in redis.scan_iter(match=f"cache:{pattern}"):
                keys.append(key)
            if keys:
                deleted = await redis.delete(*keys)
        except Exception as e:
            logger.warning(f"Redis pattern delete error: {e}")

    import fnmatch

    for key in list(_memory_cache.keys()):
        if fnmatch.fnmatch(key, pattern):
            del _memory_cache[key]
            deleted += 1

    _cache_stats["deletes"] += deleted
    return deleted


async def cache_delete_by_tag(tag: str) -> int:
    """Delete all cache entries with a specific tag."""
    deleted = 0

    redis = await get_redis_client()

    if redis:
        try:
            keys = await redis.smembers(f"cache_tag:{tag}")
            if keys:
                redis_keys = [f"cache:{k}" for k in keys]
                deleted = await redis.delete(*redis_keys)
                await redis.delete(f"cache_tag:{tag}")
        except Exception as e:
            logger.warning(f"Redis tag delete error: {e}")

    for key, entry in list(_memory_cache.items()):
        if tag in entry.get("tags", []):
            del _memory_cache[key]
            deleted += 1

    _cache_stats["deletes"] += deleted
    return deleted


async def cache_clear() -> int:
    """Clear all cache entries."""
    global _memory_cache

    deleted = 0

    redis = await get_redis_client()

    if redis:
        try:
            keys = []
            async for key in redis.scan_iter(match="cache:*"):
                keys.append(key)
            if keys:
                deleted = await redis.delete(*keys)

            async for key in redis.scan_iter(match="cache_tag:*"):
                await redis.delete(key)
        except Exception as e:
            logger.warning(f"Redis clear error: {e}")

    deleted += len(_memory_cache)
    _memory_cache.clear()

    _cache_stats["deletes"] += deleted
    return deleted


class CachedResult:
    """Decorator for caching function results."""

    def __init__(
        self,
        prefix: str,
        ttl_seconds: int = 300,
        key_builder: callable | None = None,
    ):
        self.prefix = prefix
        self.ttl_seconds = ttl_seconds
        self.key_builder = key_builder

    def __call__(self, func):
        async def wrapper(*args, **kwargs):
            if self.key_builder:
                cache_key = self.key_builder(*args, **kwargs)
            else:
                cache_key = generate_cache_key(self.prefix, *args, **kwargs)

            cached = await cache_get(cache_key)
            if cached is not None:
                return cached

            result = await func(*args, **kwargs)
            await cache_set(cache_key, result, ttl_seconds=self.ttl_seconds)

            return result

        return wrapper


@router.get("/stats", response_model=CacheStats)
async def get_cache_stats(current_user: dict = Depends(get_current_user)):
    """Get cache statistics."""
    total = _cache_stats["hits"] + _cache_stats["misses"]
    hit_rate = _cache_stats["hits"] / max(total, 1)

    redis_connected = False
    redis = await get_redis_client()
    if redis:
        try:
            await redis.ping()
            redis_connected = True
        except Exception:
            pass

    return CacheStats(
        hits=_cache_stats["hits"],
        misses=_cache_stats["misses"],
        sets=_cache_stats["sets"],
        deletes=_cache_stats["deletes"],
        hit_rate=hit_rate,
        total_entries=len(_memory_cache),
        memory_entries=len(_memory_cache),
        redis_connected=redis_connected,
    )


@router.get("/{key}")
async def get_cached_value(
    key: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a cached value."""
    value = await cache_get(key)
    if value is None:
        raise HTTPException(status_code=404, detail="Cache key not found")

    return {"key": key, "value": value}


@router.post("/")
async def set_cached_value(
    request: CacheSetRequest,
    current_user: dict = Depends(get_current_user),
):
    """Set a cached value."""
    success = await cache_set(
        request.key,
        request.value,
        ttl_seconds=request.ttl_seconds,
        tags=request.tags,
    )

    if success:
        return {"message": "Cached successfully", "key": request.key}
    raise HTTPException(status_code=500, detail="Failed to cache value")


@router.post("/batch")
async def set_cached_values_batch(
    request: CacheBatchSetRequest,
    current_user: dict = Depends(get_current_user),
):
    """Set multiple cached values."""
    results = []
    for entry in request.entries:
        success = await cache_set(
            entry.key,
            entry.value,
            ttl_seconds=entry.ttl_seconds,
            tags=entry.tags,
        )
        results.append({"key": entry.key, "success": success})

    return {"results": results, "total": len(results)}


@router.delete("/{key}")
async def delete_cached_value(
    key: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a cached value."""
    deleted = await cache_delete(key)
    if deleted:
        return {"message": "Deleted", "key": key}
    raise HTTPException(status_code=404, detail="Cache key not found")


@router.post("/delete-pattern")
async def delete_by_pattern(
    request: CacheKeyPattern,
    current_user: dict = Depends(get_current_user),
):
    """Delete cache entries matching a pattern."""
    deleted = await cache_delete_by_pattern(request.pattern)
    return {"message": f"Deleted {deleted} entries", "pattern": request.pattern}


@router.post("/delete-tag/{tag}")
async def delete_by_tag(
    tag: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete all cache entries with a specific tag."""
    deleted = await cache_delete_by_tag(tag)
    return {"message": f"Deleted {deleted} entries", "tag": tag}


@router.post("/clear")
async def clear_all_cache(current_user: dict = Depends(get_current_user)):
    """Clear all cache entries."""
    deleted = await cache_clear()
    return {"message": f"Cleared {deleted} cache entries"}


@router.get("/keys")
async def list_cache_keys(
    prefix: str = "",
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
):
    """List cache keys."""
    keys = []

    redis = await get_redis_client()

    if redis:
        try:
            pattern = f"cache:{prefix}*" if prefix else "cache:*"
            async for key in redis.scan_iter(match=pattern, count=limit):
                keys.append(key.replace("cache:", ""))
        except Exception as e:
            logger.warning(f"Redis scan error: {e}")

    for key in _memory_cache:
        if prefix and not key.startswith(prefix):
            continue
        if key not in keys:
            keys.append(key)

    return {"keys": keys[:limit], "total": len(keys)}


@router.post("/warm")
async def warm_cache(current_user: dict = Depends(get_current_user)):
    """Warm cache with frequently accessed data."""
    warmed = 0

    try:
        from api.db.cosmos import get_container

        container = get_container()
        if container:
            popular_jobs = list(
                container.query_items(
                    query="SELECT TOP 10 * FROM c WHERE c.status = 'completed' ORDER BY c.created_at DESC",
                    enable_cross_partition_query=True,
                )
            )
            for job in popular_jobs:
                await cache_set(
                    f"job:{job.get('id')}",
                    job,
                    ttl_seconds=3600,
                    tags=["job", "popular"],
                )
                warmed += 1
    except Exception as e:
        logger.warning(f"Cache warming failed: {e}")

    return {"message": f"Warmed {warmed} cache entries"}


async def get_job_result_cached(job_id: str) -> dict | None:
    """Get cached job result."""
    return await cache_get(f"job_result:{job_id}")


async def cache_job_result(job_id: str, result: dict, ttl_seconds: int = 3600) -> bool:
    """Cache a job result."""
    return await cache_set(
        f"job_result:{job_id}", result, ttl_seconds=ttl_seconds, tags=["job_result"]
    )


async def get_optimization_result_cached(problem_hash: str) -> dict | None:
    """Get cached optimization result by problem hash."""
    return await cache_get(f"opt_result:{problem_hash}")


async def cache_optimization_result(
    problem_hash: str,
    result: dict,
    ttl_seconds: int = 7200,
) -> bool:
    """Cache an optimization result."""
    return await cache_set(
        f"opt_result:{problem_hash}",
        result,
        ttl_seconds=ttl_seconds,
        tags=["optimization_result"],
    )

"""
Query Optimization Module.

Prevents N+1 queries and optimizes database access:
- Batch loading of related entities
- Query result caching
- DataLoader pattern for GraphQL-style batch fetching
- Prefetch related data
"""

import asyncio
import hashlib
import json
import logging
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

K = TypeVar("K")
V = TypeVar("V")


@dataclass
class QueryMetrics:
    """Metrics for query performance tracking."""

    query_count: int = 0
    n_plus_one_detected: int = 0
    batch_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_query_time_ms: float = 0.0


class DataLoader(Generic[K, V]):
    """
    DataLoader for batch loading to prevent N+1 queries.

    Batches multiple requests for the same entity type
    and loads them in a single query.

    Usage:
        loader = DataLoader(batch_load_users)
        user1 = await loader.load("user_1")
        user2 = await loader.load("user_2")
        # Both loaded in single query
    """

    def __init__(
        self,
        batch_load_fn: Callable[[list[K]], list[V] | list[list[V]]],
        max_batch_size: int = 100,
        batch_delay_ms: int = 10,
    ):
        self._batch_load_fn = batch_load_fn
        self._max_batch_size = max_batch_size
        self._batch_delay_ms = batch_delay_ms
        self._queue: list[tuple[K, asyncio.Future]] = []
        self._cache: dict[K, V] = {}
        self._scheduled: bool = False
        self._lock = asyncio.Lock()

    async def load(self, key: K) -> V:
        """Load a single item, batching with other requests."""
        if key in self._cache:
            return self._cache[key]

        future: asyncio.Future = asyncio.get_event_loop().create_future()

        async with self._lock:
            self._queue.append((key, future))

            if not self._scheduled:
                self._scheduled = True
                asyncio.get_event_loop().call_later(
                    self._batch_delay_ms / 1000.0,
                    lambda: asyncio.create_task(self._dispatch()),
                )

        return await future

    async def load_many(self, keys: list[K]) -> list[V]:
        """Load multiple items."""
        return [await self.load(key) for key in keys]

    async def prime(self, key: K, value: V) -> None:
        """Pre-populate the cache with a value."""
        self._cache[key] = value

    def clear(self, key: K) -> None:
        """Clear a single item from cache."""
        self._cache.pop(key, None)

    def clear_all(self) -> None:
        """Clear entire cache."""
        self._cache.clear()

    async def _dispatch(self) -> None:
        """Dispatch batched requests."""
        async with self._lock:
            self._scheduled = False

            if not self._queue:
                return

            batch = self._queue[: self._max_batch_size]
            self._queue = self._queue[self._max_batch_size :]

            if self._queue:
                self._scheduled = True
                asyncio.get_event_loop().call_later(
                    self._batch_delay_ms / 1000.0,
                    lambda: asyncio.create_task(self._dispatch()),
                )

        keys = [k for k, _ in batch]
        futures = [f for _, f in batch]

        try:
            results = await self._batch_load_fn(keys)

            if len(results) != len(keys):
                raise ValueError(
                    f"Batch function returned {len(results)} results for {len(keys)} keys"
                )

            for (key, future), value in zip(batch, results):
                self._cache[key] = value
                future.set_result(value)

        except Exception as e:
            for _, future in batch:
                if not future.done():
                    future.set_exception(e)


class QueryCache:
    """
    Cache for query results with TTL and LRU eviction.

    Features:
    - Time-based expiration (TTL)
    - LRU eviction when max size reached
    - Cache key hashing
    - Metrics tracking
    """

    def __init__(
        self,
        max_size: int = 10000,
        default_ttl_seconds: int = 300,
    ):
        self._cache: dict[str, tuple[Any, float, float]] = {}
        self._access_order: list[str] = []
        self._max_size = max_size
        self._default_ttl = default_ttl_seconds
        self._metrics = QueryMetrics()

    def _hash_key(self, query: str, params: dict[str, Any]) -> str:
        """Generate cache key from query and params."""
        data = json.dumps({"query": query, "params": params}, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def get(self, query: str, params: dict[str, Any]) -> Any | None:
        """Get cached result if valid."""
        key = self._hash_key(query, params)

        if key in self._cache:
            value, expires_at, _ = self._cache[key]

            if time.time() < expires_at:
                self._metrics.cache_hits += 1
                self._touch(key)
                return value
            else:
                del self._cache[key]
                self._access_order.remove(key)

        self._metrics.cache_misses += 1
        return None

    def set(
        self,
        query: str,
        params: dict[str, Any],
        value: Any,
        ttl_seconds: int | None = None,
    ) -> None:
        """Cache a result."""
        key = self._hash_key(query, params)
        ttl = ttl_seconds or self._default_ttl
        expires_at = time.time() + ttl

        if len(self._cache) >= self._max_size:
            self._evict_lru()

        self._cache[key] = (value, expires_at, time.time())
        self._access_order.append(key)

    def _touch(self, key: str) -> None:
        """Mark key as recently used."""
        if key in self._access_order:
            self._access_order.remove(key)
            self._access_order.append(key)

    def _evict_lru(self) -> None:
        """Evict least recently used item."""
        if self._access_order:
            key = self._access_order.pop(0)
            self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cached items."""
        self._cache.clear()
        self._access_order.clear()

    def get_metrics(self) -> dict[str, Any]:
        """Get cache metrics."""
        total = self._metrics.cache_hits + self._metrics.cache_misses
        hit_rate = self._metrics.cache_hits / total if total > 0 else 0

        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "cache_hits": self._metrics.cache_hits,
            "cache_misses": self._metrics.cache_misses,
            "hit_rate": round(hit_rate, 4),
        }


class NPlusOneDetector:
    """
    Detects N+1 query patterns during execution.

    Usage:
        async with detect_n_plus_one("user_jobs") as detector:
            for user in users:
                jobs = await get_jobs(user.id)
    """

    _thresholds: dict[str, int] = defaultdict(lambda: 10)
    _counts: dict[str, int] = defaultdict(int)
    _warnings: list[dict[str, Any]] = []

    @classmethod
    def set_threshold(cls, pattern_name: str, threshold: int):
        """Set warning threshold for a pattern."""
        cls._thresholds[pattern_name] = threshold

    @classmethod
    def increment(cls, pattern_name: str) -> bool:
        """Increment counter and check if threshold exceeded."""
        cls._counts[pattern_name] += 1

        if cls._counts[pattern_name] > cls._thresholds[pattern_name]:
            warning = {
                "pattern": pattern_name,
                "count": cls._counts[pattern_name],
                "threshold": cls._thresholds[pattern_name],
                "timestamp": datetime.now(UTC).isoformat(),
            }
            cls._warnings.append(warning)
            logger.warning(
                f"N+1 query detected: {pattern_name} - {cls._counts[pattern_name]} queries"
            )
            return True

        return False

    @classmethod
    def reset(cls, pattern_name: str):
        """Reset counter for a pattern."""
        cls._counts[pattern_name] = 0

    @classmethod
    def get_warnings(cls) -> list[dict[str, Any]]:
        """Get all N+1 warnings."""
        return cls._warnings


class BatchLoader:
    """
    Utility for batch loading related entities.

    Usage:
        loader = BatchLoader(get_jobs_by_user_ids)
        jobs = await loader.load_for_users(["user_1", "user_2"])
    """

    def __init__(
        self,
        batch_fn: Callable[[list[str]], dict[str, list[Any]]],
        batch_size: int = 100,
    ):
        self._batch_fn = batch_fn
        self._batch_size = batch_size
        self._cache: dict[str, list[Any]] = {}

    async def load_for_users(self, user_ids: list[str]) -> dict[str, list[Any]]:
        """Load data for multiple users efficiently."""
        uncached = [uid for uid in user_ids if uid not in self._cache]

        if uncached:
            for i in range(0, len(uncached), self._batch_size):
                batch = uncached[i : i + self._batch_size]
                results = await self._batch_fn(batch)
                self._cache.update(results)

        return {uid: self._cache.get(uid, []) for uid in user_ids}

    def clear(self):
        """Clear cache."""
        self._cache.clear()


class PrefetchQuery:
    """
    Prefetch related data to avoid N+1 queries.

    Usage:
        jobs = await get_jobs(user_id)
        await prefetch_related(jobs, ["user", "results"])
    """

    @staticmethod
    async def prefetch_related(
        items: list[dict[str, Any]],
        relations: list[str],
        loaders: dict[str, DataLoader],
    ) -> list[dict[str, Any]]:
        """Prefetch related entities for a list of items."""
        for relation in relations:
            if relation not in loaders:
                continue

            loader = loaders[relation]
            keys = set()

            for item in items:
                key = item.get(f"{relation}_id") or item.get(relation, {}).get("id")
                if key:
                    keys.add(key)

            if keys:
                await loader.load_many(list(keys))

        return items


class PaginatedResult(Generic[V]):
    """Paginated result container."""

    def __init__(
        self,
        items: list[V],
        total: int,
        page: int,
        page_size: int,
    ):
        self.items = items
        self.total = total
        self.page = page
        self.page_size = page_size
        self.total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        self.has_next = page < self.total_pages
        self.has_prev = page > 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": self.items,
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "total_pages": self.total_pages,
            "has_next": self.has_next,
            "has_prev": self.has_prev,
        }


async def paginate_query(
    query_fn: Callable[[int, int], list[Any]],
    count_fn: Callable[[], int],
    page: int = 1,
    page_size: int = 20,
    max_page_size: int = 100,
) -> PaginatedResult:
    """
    Execute a paginated query.

    Args:
        query_fn: Function that takes (offset, limit) and returns items
        count_fn: Function that returns total count
        page: Current page (1-indexed)
        page_size: Items per page
        max_page_size: Maximum allowed page size

    Returns:
        PaginatedResult with items and metadata
    """
    page_size = min(page_size, max_page_size)
    page = max(1, page)

    offset = (page - 1) * page_size

    items = await query_fn(offset, page_size)
    total = await count_fn()

    return PaginatedResult(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


class QueryOptimizer:
    """
    Central query optimization manager.

    Features:
    - DataLoader registration
    - Query caching
    - N+1 detection
    - Batch loading
    """

    def __init__(self):
        self._loaders: dict[str, DataLoader] = {}
        self._cache = QueryCache()
        self._batch_loaders: dict[str, BatchLoader] = {}
        self._metrics = QueryMetrics()

    def register_loader(self, name: str, loader: DataLoader) -> None:
        """Register a DataLoader."""
        self._loaders[name] = loader

    def get_loader(self, name: str) -> DataLoader | None:
        """Get a registered DataLoader."""
        return self._loaders.get(name)

    def register_batch_loader(self, name: str, loader: BatchLoader) -> None:
        """Register a batch loader."""
        self._batch_loaders[name] = loader

    def get_batch_loader(self, name: str) -> BatchLoader | None:
        """Get a registered batch loader."""
        return self._batch_loaders.get(name)

    async def cached_query(
        self,
        query: str,
        params: dict[str, Any],
        execute_fn: Callable[[], Any],
        ttl_seconds: int | None = None,
    ) -> Any:
        """Execute query with caching."""
        cached = self._cache.get(query, params)
        if cached is not None:
            return cached

        start_time = time.time()
        result = await execute_fn()
        elapsed_ms = (time.time() - start_time) * 1000

        self._metrics.query_count += 1
        self._metrics.total_query_time_ms += elapsed_ms

        self._cache.set(query, params, result, ttl_seconds)

        return result

    def get_metrics(self) -> dict[str, Any]:
        """Get optimization metrics."""
        return {
            "query_count": self._metrics.query_count,
            "batch_queries": self._metrics.batch_queries,
            "n_plus_one_detected": self._metrics.n_plus_one_detected,
            "total_query_time_ms": round(self._metrics.total_query_time_ms, 2),
            "avg_query_time_ms": round(
                self._metrics.total_query_time_ms / max(1, self._metrics.query_count), 2
            ),
            "cache": self._cache.get_metrics(),
            "n_plus_one_warnings": NPlusOneDetector.get_warnings(),
        }


_query_optimizer: QueryOptimizer | None = None


def get_query_optimizer() -> QueryOptimizer:
    """Get or create the global query optimizer."""
    global _query_optimizer
    if _query_optimizer is None:
        _query_optimizer = QueryOptimizer()
    return _query_optimizer

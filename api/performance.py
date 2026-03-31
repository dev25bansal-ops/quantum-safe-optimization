"""
Performance optimizations for QSOP API.
"""

import asyncio
import functools
import time
from collections import OrderedDict
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class LRUCache:
    """
    Thread-safe LRU cache with TTL support.

    Usage:
        cache = LRUCache(max_size=1000, ttl_seconds=300)
        cache.set("key", value)
        value = cache.get("key")
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = asyncio.Lock()

    def get(self, key: str) -> Any | None:
        """Get value from cache."""
        if key not in self._cache:
            return None

        value, timestamp = self._cache[key]

        if time.time() - timestamp > self.ttl_seconds:
            del self._cache[key]
            return None

        self._cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        """Set value in cache."""
        if key in self._cache:
            del self._cache[key]

        self._cache[key] = (value, time.time())

        while len(self._cache) > self.max_size:
            self._cache.popitem(last=False)

    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def size(self) -> int:
        """Get current cache size."""
        return len(self._cache)


def cached(
    max_size: int = 1000,
    ttl_seconds: float = 300,
    key_fn: Callable[..., str] | None = None,
):
    """
    Decorator for caching function results.

    Usage:
        @cached(max_size=100, ttl_seconds=60)
        def expensive_function(arg):
            return compute(arg)
    """
    cache = LRUCache(max_size=max_size, ttl_seconds=ttl_seconds)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            key = key_fn(*args, **kwargs) if key_fn else str((args, tuple(kwargs.items())))

            result = cache.get(key)
            if result is not None:
                return result

            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        wrapper.cache = cache
        return wrapper

    return decorator


class ConnectionPool:
    """
    Generic connection pool for managing limited resources.

    Usage:
        pool = ConnectionPool(create_connection=lambda: create_db(), max_size=10)
        async with pool.acquire() as conn:
            await conn.execute(query)
    """

    def __init__(
        self,
        create_connection: Callable[[], Any],
        max_size: int = 10,
        timeout_seconds: float = 30,
    ):
        self.create_connection = create_connection
        self.max_size = max_size
        self.timeout_seconds = timeout_seconds
        self._pool: list[Any] = []
        self._in_use: set[int] = set()
        self._semaphore = asyncio.Semaphore(max_size)
        self._lock = asyncio.Lock()

    async def acquire(self) -> Any:
        """Acquire a connection from the pool."""
        await asyncio.wait_for(
            self._semaphore.acquire(),
            timeout=self.timeout_seconds,
        )

        async with self._lock:
            if self._pool:
                conn = self._pool.pop()
                self._in_use.add(id(conn))
                return conn

        conn = self.create_connection()
        async with self._lock:
            self._in_use.add(id(conn))
        return conn

    async def release(self, conn: Any) -> None:
        """Release a connection back to the pool."""
        async with self._lock:
            if id(conn) in self._in_use:
                self._in_use.remove(id(conn))
                self._pool.append(conn)

        self._semaphore.release()


class BatchProcessor:
    """
    Batch multiple operations for efficiency.

    Usage:
        processor = BatchProcessor(
            process_fn=lambda items: bulk_insert(items),
            batch_size=100,
            flush_interval_ms=100
        )
        await processor.add(item1)
        await processor.add(item2)
    """

    def __init__(
        self,
        process_fn: Callable[[list[Any]], Any],
        batch_size: int = 100,
        flush_interval_ms: int = 100,
    ):
        self.process_fn = process_fn
        self.batch_size = batch_size
        self.flush_interval = flush_interval_ms / 1000
        self._batch: list[Any] = []
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None

    async def add(self, item: Any) -> None:
        """Add item to batch."""
        async with self._lock:
            self._batch.append(item)

            if len(self._batch) >= self.batch_size:
                await self._flush()
            elif self._flush_task is None or self._flush_task.done():
                self._flush_task = asyncio.create_task(self._delayed_flush())

    async def _delayed_flush(self) -> None:
        """Flush after delay."""
        await asyncio.sleep(self.flush_interval)
        async with self._lock:
            if self._batch:
                await self._flush()

    async def _flush(self) -> None:
        """Process the current batch."""
        if not self._batch:
            return

        items = self._batch[:]
        self._batch.clear()

        await self.process_fn(items)

    async def flush(self) -> None:
        """Manually flush the batch."""
        async with self._lock:
            await self._flush()


async def gather_with_concurrency(
    n: int,
    *coros,
    return_exceptions: bool = False,
) -> list[Any]:
    """
    Run coroutines with limited concurrency.

    Usage:
        results = await gather_with_concurrency(
            10,
            *[fetch_url(url) for url in urls]
        )
    """
    semaphore = asyncio.Semaphore(n)

    async def sem_coro(coro):
        async with semaphore:
            return await coro

    return await asyncio.gather(
        *[sem_coro(c) for c in coros],
        return_exceptions=return_exceptions,
    )

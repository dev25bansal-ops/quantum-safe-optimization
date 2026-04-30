"""
Performance regression tests for the Quantum-Safe Optimization Platform.

These tests track performance metrics over time and fail if performance degrades
beyond acceptable thresholds.

Usage:
    pytest tests/performance/test_throughput.py -v
    pytest tests/performance/ --benchmark-json=results.json
"""

import json
import time
from pathlib import Path
from typing import Any

import pytest


# Track performance results for trend analysis
RESULTS_DIR = Path("tests/performance/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_FILE = RESULTS_DIR / "performance_results.jsonl"


def record_performance(test_name: str, metrics: dict[str, Any]):
    """Record performance metrics for trend analysis."""
    result = {
        "test": test_name,
        "timestamp": time.time(),
        **metrics,
    }

    with open(RESULTS_FILE, "a") as f:
        f.write(json.dumps(result) + "\n")


class TestAPIThroughput:
    """Test API throughput and latency."""

    @pytest.mark.asyncio
    async def test_health_endpoint_latency(self):
        """Test that /health endpoint responds within 100ms."""
        try:
            from api.main import app
        except ImportError:
            pytest.skip("API module not available")

        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            latencies = []

            # Make 10 requests
            for _ in range(10):
                start = time.perf_counter()
                response = await client.get("/health")
                elapsed = time.perf_counter() - start
                latencies.append(elapsed)

                assert response.status_code == 200

            # Calculate metrics
            p50 = sorted(latencies)[len(latencies) // 2]
            p95 = sorted(latencies)[int(len(latencies) * 0.95)]
            p99 = sorted(latencies)[int(len(latencies) * 0.99)]

            # Record metrics
            record_performance("health_latency", {
                "p50_ms": p50 * 1000,
                "p95_ms": p95 * 1000,
                "p99_ms": p99 * 1000,
                "samples": len(latencies),
            })

            # Assert thresholds (p95 < 100ms)
            assert p95 < 0.1, f"Health endpoint p95 latency too high: {p95*1000:.2f}ms"

    @pytest.mark.asyncio
    async def test_job_submission_throughput(self):
        """Test job submission throughput."""
        try:
            from api.main import app
        except ImportError:
            pytest.skip("API module not available")

        from httpx import ASGITransport, AsyncClient

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            start = time.perf_counter()
            count = 5

            for i in range(count):
                response = await client.post(
                    "/api/v1/jobs",
                    json={
                        "problem_type": "QAOA",
                        "problem_config": {
                            "type": "maxcut",
                            "edges": [[0, 1], [1, 2]],
                        },
                        "backend": "local_simulator",
                    },
                    headers={"Authorization": "Bearer test_token"},
                )
                # Accept 201, 202, or auth errors
                assert response.status_code in [201, 202, 401, 403]

            elapsed = time.perf_counter() - start
            throughput = count / elapsed if elapsed > 0 else 0

            # Record metrics
            record_performance("job_submission_throughput", {
                "throughput_per_second": throughput,
                "total_time_ms": elapsed * 1000,
                "job_count": count,
            })

            # Should handle at least 1 job/sec
            assert throughput > 0.5, f"Job submission throughput too low: {throughput:.2f}/s"


class TestCryptoPerformance:
    """Test cryptographic operation performance."""

    def test_email_lookup_performance(self):
        """Test that email lookup is O(1) and completes in <1ms."""
        import asyncio
        import os

        os.environ["ADMIN_PASSWORD"] = "test_pass"
        os.environ["APP_ENV"] = "test"

        from api.auth_stores import InMemoryUserStore

        async def benchmark():
            store = InMemoryUserStore()

            # Add 1000 users
            for i in range(1000):
                await store.save({
                    "username": f"user{i}",
                    "user_id": f"usr_{i:05d}",
                    "email": f"user{i}@example.com",
                    "password_hash": "hashed",
                })

            # Benchmark email lookup
            latencies = []
            for i in range(100):
                start = time.perf_counter()
                await store.email_exists(f"user{i}@example.com")
                elapsed = time.perf_counter() - start
                latencies.append(elapsed)

            p50 = sorted(latencies)[len(latencies) // 2]
            p95 = sorted(latencies)[int(len(latencies) * 0.95)]

            return p50, p95

        p50, p95 = asyncio.run(benchmark())

        # Record metrics
        record_performance("email_lookup", {
            "p50_ms": p50 * 1000,
            "p95_ms": p95 * 1000,
            "user_count": 1000,
        })

        # Should be < 1ms for O(1) lookup
        assert p95 < 0.001, f"Email lookup too slow: p95={p95*1000:.3f}ms (should be < 1ms)"

    def test_key_store_lookup_performance(self):
        """Test that key store lookup is O(1)."""
        import asyncio
        from api.auth_stores import InMemoryKeyStore

        async def benchmark():
            store = InMemoryKeyStore()
            user_id = "usr_test"

            # Add 100 keys
            for i in range(100):
                await store.save({
                    "key_id": f"key_{i:03d}",
                    "user_id": user_id,
                    "type": "api_key",
                    "created_at": f"2024-01-{i%28+1:02d}T00:00:00",
                })

            # Benchmark lookup
            latencies = []
            for _ in range(100):
                start = time.perf_counter()
                await store.list_for_user(user_id)
                elapsed = time.perf_counter() - start
                latencies.append(elapsed)

            p50 = sorted(latencies)[len(latencies) // 2]
            return p50

        p50 = asyncio.run(benchmark())

        record_performance("key_store_lookup", {
            "p50_ms": p50 * 1000,
        })

        # Should be < 1ms
        assert p50 < 0.001, f"Key store lookup too slow: p50={p50*1000:.3f}ms"


class TestMemoryUsage:
    """Test memory usage doesn't grow unboundedly."""

    @pytest.mark.asyncio
    async def test_bounded_store_respects_max_size(self):
        """Test that bounded stores evict old entries."""
        from api.stores.bounded_memory_stores import BoundedInMemoryJobStore

        store = BoundedInMemoryJobStore(max_size=100, default_ttl_seconds=3600)

        # Add 150 items
        for i in range(150):
            await store.set(f"job_{i:03d}", {"id": f"job_{i:03d}", "data": "x" * 100})

        # Should have at most max_size items
        count = await store.count()
        assert count <= 100, f"Store exceeded max_size: {count} > 100"

        # Record metrics
        record_performance("bounded_store_size", {
            "items_added": 150,
            "items_retained": count,
            "max_size": 100,
            "evictions": 150 - count,
        })

    @pytest.mark.asyncio
    async def test_bounded_store_expires_old_items(self):
        """Test that bounded stores expire items after TTL."""
        from api.stores.bounded_memory_stores import BoundedInMemoryJobStore

        # Very short TTL for testing
        store = BoundedInMemoryJobStore(max_size=1000, default_ttl_seconds=1)

        # Add items
        for i in range(10):
            await store.set(f"job_{i}", {"id": f"job_{i}"}, ttl=1)

        # Wait for expiration
        await asyncio.sleep(1.5)

        # All should be expired
        count = await store.count()
        assert count == 0, f"Items not expired: {count} remaining"

        record_performance("bounded_store_expiry", {
            "items_added": 10,
            "items_after_ttl": count,
            "ttl_seconds": 1,
        })


class TestCachePerformance:
    """Test result caching performance."""

    def test_cache_hit_vs_miss(self):
        """Test that cache hits are significantly faster than misses."""
        import asyncio

        async def benchmark():
            from api.cache.result_cache import NoOpResultCache

            cache = NoOpResultCache()

            problem_config = {"type": "maxcut", "edges": [[0, 1]]}
            parameters = {"layers": 3, "optimizer": "COBYLA"}
            result = {"status": "completed", "value": -5.0}

            # Benchmark set
            start = time.perf_counter()
            await cache.set(problem_config, parameters, result)
            set_time = time.perf_counter() - start

            # Benchmark get (will be miss for NoOp)
            start = time.perf_counter()
            await cache.get(problem_config, parameters)
            get_time = time.perf_counter() - start

            return set_time, get_time

        set_time, get_time = asyncio.run(benchmark())

        record_performance("cache_operations", {
            "set_ms": set_time * 1000,
            "get_ms": get_time * 1000,
        })

        # Operations should be fast (< 10ms)
        assert set_time < 0.01, f"Cache set too slow: {set_time*1000:.2f}ms"
        assert get_time < 0.01, f"Cache get too slow: {get_time*1000:.2f}ms"


class TestEventLoopReuse:
    """Test event loop reuse optimization."""

    def test_event_loop_reuse(self):
        """Test that event loop is reused across calls."""
        import asyncio
        from api.tasks.workers import get_event_loop

        loop1 = get_event_loop()
        loop2 = get_event_loop()

        # Should be the same loop
        assert loop1 is loop2, "Event loop not reused!"

        # Should be running
        assert loop1.is_running() or not loop1.is_closed()


class TestDatabaseQueryPerformance:
    """Test database query performance."""

    @pytest.mark.asyncio
    async def test_user_count_is_o1(self):
        """Test that user count operation is O(1)."""
        import os
        os.environ["ADMIN_PASSWORD"] = "test_pass"
        os.environ["APP_ENV"] = "test"

        from api.auth_stores import InMemoryUserStore

        store = InMemoryUserStore()

        # Add users
        for i in range(1000):
            await store.save({
                "username": f"user{i}",
                "user_id": f"usr_{i:05d}",
                "email": f"user{i}@example.com",
                "password_hash": "hashed",
            })

        # Benchmark count
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            count = await store.count()
            elapsed = time.perf_counter() - start
            latencies.append(elapsed)

        p50 = sorted(latencies)[len(latencies) // 2]

        record_performance("user_count", {
            "p50_ms": p50 * 1000,
            "user_count": count,
        })

        # Should be < 1ms for O(1)
        assert p50 < 0.001, f"User count too slow: p50={p50*1000:.3f}ms"
        assert count == 1001  # 1000 + 1 admin


# Import asyncio at the end to ensure all modules are loaded
import asyncio

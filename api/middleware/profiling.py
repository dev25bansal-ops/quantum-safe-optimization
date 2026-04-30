"""
Performance Profiling Middleware.

Provides:
- Request latency tracking
- Memory usage profiling
- CPU time tracking
- Slow request detection
- Profiling data collection
"""

import gc
import logging
import os
import time
import traceback
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


@dataclass
class RequestProfile:
    method: str
    path: str
    latency_ms: float
    cpu_time_ms: float
    memory_before_mb: float
    memory_after_mb: float
    memory_delta_mb: float
    status_code: int
    timestamp: str
    request_id: str | None = None
    user_id: str | None = None
    slow_request: bool = False
    exception: str | None = None
    traceback: str | None = None


@dataclass
class ProfilingStats:
    total_requests: int
    slow_requests: int
    error_requests: int
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    avg_memory_delta_mb: float
    total_cpu_time_ms: float
    requests_per_minute: float
    profiles: list[dict[str, Any]] = field(default_factory=list)


try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class PerformanceProfilingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for profiling request performance.

    Tracks:
    - Request latency
    - CPU time
    - Memory usage before/after
    - Slow request detection
    - Exception tracking
    """

    SLOW_REQUEST_THRESHOLD_MS = float(os.getenv("SLOW_REQUEST_THRESHOLD_MS", "1000"))
    PROFILE_SAMPLE_RATE = float(os.getenv("PROFILE_SAMPLE_RATE", "0.1"))
    MAX_PROFILES = int(os.getenv("MAX_PROFILES", "1000"))

    def __init__(
        self,
        app: ASGIApp,
        slow_threshold_ms: float | None = None,
        sample_rate: float | None = None,
        max_profiles: int | None = None,
        enabled: bool = True,
    ):
        super().__init__(app)
        self.enabled = enabled
        self.slow_threshold_ms = slow_threshold_ms or self.SLOW_REQUEST_THRESHOLD_MS
        self.sample_rate = sample_rate or self.PROFILE_SAMPLE_RATE
        self.max_profiles = max_profiles or self.MAX_PROFILES

        self._profiles: deque = deque(maxlen=self.max_profiles)
        self._total_requests = 0
        self._slow_requests = 0
        self._error_requests = 0
        self._total_latency = 0.0
        self._total_cpu_time = 0.0
        self._total_memory_delta = 0.0
        self._start_time = datetime.now(UTC)
        self._minute_requests: deque = deque(maxlen=10000)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self.enabled:
            return await call_next(request)

        import random

        should_profile = random.random() < self.sample_rate

        profile_data: dict[str, Any] = {}
        start_time = time.perf_counter()
        start_cpu = time.process_time()

        if PSUTIL_AVAILABLE:
            import os

            process = psutil.Process(os.getpid())
            memory_before = process.memory_info().rss / 1024 / 1024
        else:
            memory_before = 0.0

        request_id = getattr(request.state, "request_id", None)
        user_id = getattr(request.state, "user_id", None)

        exception_info = None
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as e:
            exception_info = str(e)
            if should_profile:
                profile_data["exception"] = exception_info
                profile_data["traceback"] = traceback.format_exc()
            raise
        finally:
            end_time = time.perf_counter()
            end_cpu = time.process_time()

            if PSUTIL_AVAILABLE:
                memory_after = process.memory_info().rss / 1024 / 1024
            else:
                memory_after = 0.0

            latency_ms = (end_time - start_time) * 1000
            cpu_time_ms = (end_cpu - start_cpu) * 1000
            memory_delta = memory_after - memory_before

            self._total_requests += 1
            self._total_latency += latency_ms
            self._total_cpu_time += cpu_time_ms
            self._total_memory_delta += memory_delta

            self._minute_requests.append(datetime.now(UTC))

            is_slow = latency_ms > self.slow_threshold_ms
            is_error = status_code >= 400

            if is_slow:
                self._slow_requests += 1
                logger.warning(
                    "slow_request",
                    method=request.method,
                    path=request.url.path,
                    latency_ms=round(latency_ms, 2),
                    threshold_ms=self.slow_threshold_ms,
                    request_id=request_id,
                )

            if is_error:
                self._error_requests += 1

            if should_profile or is_slow or is_error:
                profile = RequestProfile(
                    method=request.method,
                    path=request.url.path,
                    latency_ms=round(latency_ms, 4),
                    cpu_time_ms=round(cpu_time_ms, 4),
                    memory_before_mb=round(memory_before, 2),
                    memory_after_mb=round(memory_after, 2),
                    memory_delta_mb=round(memory_delta, 4),
                    status_code=status_code,
                    timestamp=datetime.now(UTC).isoformat(),
                    request_id=request_id,
                    user_id=user_id,
                    slow_request=is_slow,
                    exception=exception_info,
                    traceback=profile_data.get("traceback") if exception_info else None,
                )
                self._profiles.append(asdict(profile))

    def get_stats(self) -> ProfilingStats:
        """Get profiling statistics."""
        profiles = list(self._profiles)

        if profiles:
            latencies = sorted([p["latency_ms"] for p in profiles])
            p95_idx = int(len(latencies) * 0.95)
            p99_idx = int(len(latencies) * 0.99)
            p95_latency = latencies[p95_idx] if p95_idx < len(latencies) else latencies[-1]
            p99_latency = latencies[p99_idx] if p99_idx < len(latencies) else latencies[-1]
        else:
            p95_latency = 0.0
            p99_latency = 0.0

        now = datetime.now(UTC)
        recent_requests = [t for t in self._minute_requests if (now - t).total_seconds() < 60]
        rpm = len(recent_requests)

        return ProfilingStats(
            total_requests=self._total_requests,
            slow_requests=self._slow_requests,
            error_requests=self._error_requests,
            avg_latency_ms=round(self._total_latency / self._total_requests, 2)
            if self._total_requests > 0
            else 0.0,
            p95_latency_ms=round(p95_latency, 2),
            p99_latency_ms=round(p99_latency, 2),
            avg_memory_delta_mb=round(self._total_memory_delta / self._total_requests, 4)
            if self._total_requests > 0
            else 0.0,
            total_cpu_time_ms=round(self._total_cpu_time, 2),
            requests_per_minute=rpm,
            profiles=profiles[-100:],
        )

    def get_slow_requests(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get slow request profiles."""
        slow = [p for p in self._profiles if p.get("slow_request")]
        return sorted(slow, key=lambda x: x["latency_ms"], reverse=True)[:limit]

    def get_error_requests(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get error request profiles."""
        errors = [p for p in self._profiles if p.get("status_code", 200) >= 400]
        return sorted(errors, key=lambda x: x["timestamp"], reverse=True)[:limit]

    def reset(self) -> None:
        """Reset profiling data."""
        self._profiles.clear()
        self._total_requests = 0
        self._slow_requests = 0
        self._error_requests = 0
        self._total_latency = 0.0
        self._total_cpu_time = 0.0
        self._total_memory_delta = 0.0
        self._start_time = datetime.now(UTC)
        self._minute_requests.clear()


_profiling_middleware: PerformanceProfilingMiddleware | None = None


def get_profiling_middleware() -> PerformanceProfilingMiddleware | None:
    """Get the profiling middleware instance."""
    return _profiling_middleware


def set_profiling_middleware(middleware: PerformanceProfilingMiddleware) -> None:
    """Set the profiling middleware instance."""
    global _profiling_middleware
    _profiling_middleware = middleware

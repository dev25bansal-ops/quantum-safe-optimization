"""Rate limiting middleware with per-tenant limits."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

RATE_LIMIT_HEADER_LIMIT = "X-RateLimit-Limit"
RATE_LIMIT_HEADER_REMAINING = "X-RateLimit-Remaining"
RATE_LIMIT_HEADER_RESET = "X-RateLimit-Reset"
RATE_LIMIT_HEADER_RETRY = "Retry-After"


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting."""

    tokens: float
    last_update: float
    max_tokens: int
    refill_rate: float  # tokens per second

    def consume(self, now: float, tokens: int = 1) -> tuple[bool, int, int]:
        """
        Try to consume tokens from the bucket.

        Returns:
            tuple of (allowed, remaining, reset_seconds)
        """
        elapsed = now - self.last_update
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_update = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            remaining = int(self.tokens)
            reset_seconds = int((self.max_tokens - self.tokens) / self.refill_rate)
            return True, remaining, reset_seconds
        else:
            remaining = 0
            reset_seconds = int((tokens - self.tokens) / self.refill_rate)
            return False, remaining, reset_seconds


@dataclass
class RateLimitStore:
    """In-memory rate limit store (use Redis in production)."""

    buckets: dict[str, RateLimitBucket] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """
        Check and update rate limit for a key.

        Returns:
            tuple of (allowed, remaining, reset_seconds)
        """
        async with self._lock:
            now = time.time()
            refill_rate = max_requests / window_seconds

            if key not in self.buckets:
                self.buckets[key] = RateLimitBucket(
                    tokens=float(max_requests),
                    last_update=now,
                    max_tokens=max_requests,
                    refill_rate=refill_rate,
                )

            bucket = self.buckets[key]
            return bucket.consume(now)

    async def cleanup_expired(self, max_age_seconds: int = 3600) -> int:
        """Remove expired buckets to prevent memory growth."""
        async with self._lock:
            now = time.time()
            expired_keys = [
                key
                for key, bucket in self.buckets.items()
                if now - bucket.last_update > max_age_seconds
            ]
            for key in expired_keys:
                del self.buckets[key]
            return len(expired_keys)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that implements per-tenant rate limiting."""

    def __init__(
        self,
        app,
        max_requests: int = 100,
        window_seconds: int = 60,
        key_func: Callable[[Request], str] | None = None,
        store: RateLimitStore | None = None,
    ) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_func = key_func or self._default_key_func
        self.store = store or RateLimitStore()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        key = self.key_func(request)

        allowed, remaining, reset_seconds = await self.store.check_rate_limit(
            key=key,
            max_requests=self.max_requests,
            window_seconds=self.window_seconds,
        )

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": f"Rate limit exceeded. Retry after {reset_seconds} seconds.",
                },
                headers={
                    RATE_LIMIT_HEADER_LIMIT: str(self.max_requests),
                    RATE_LIMIT_HEADER_REMAINING: str(remaining),
                    RATE_LIMIT_HEADER_RESET: str(reset_seconds),
                    RATE_LIMIT_HEADER_RETRY: str(reset_seconds),
                },
            )

        response = await call_next(request)

        response.headers[RATE_LIMIT_HEADER_LIMIT] = str(self.max_requests)
        response.headers[RATE_LIMIT_HEADER_REMAINING] = str(remaining)
        response.headers[RATE_LIMIT_HEADER_RESET] = str(reset_seconds)

        return response

    def _default_key_func(self, request: Request) -> str:
        """Default key function using tenant ID or IP address."""
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id:
            return f"tenant:{tenant_id}"

        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"

        return f"ip:{ip}"

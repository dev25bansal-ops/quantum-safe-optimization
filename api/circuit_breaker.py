"""
Circuit breaker pattern for external service calls.

Prevents cascading failures by failing fast when a service is down.
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitStats:
    """Circuit breaker statistics."""

    failures: int = 0
    successes: int = 0
    last_failure_time: float = 0
    last_success_time: float = 0
    state: CircuitState = CircuitState.CLOSED
    state_changed_at: float = field(default_factory=time.time)


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.

    Usage:
        breaker = CircuitBreaker(
            name="quantum_backend",
            failure_threshold=5,
            recovery_timeout=30
        )

        async with breaker:
            result = await call_external_service()
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        success_threshold: int = 3,
        timeout: float = 10.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.timeout = timeout
        self._stats = CircuitStats()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._stats.state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (allowing requests)."""
        return self._stats.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        if self._stats.state == CircuitState.OPEN:
            if time.time() - self._stats.state_changed_at > self.recovery_timeout:
                return False
            return True
        return False

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute a function through the circuit breaker."""
        async with self._lock:
            if self.is_open:
                raise CircuitOpenError(
                    f"Circuit '{self.name}' is open",
                    retry_after=self.recovery_timeout
                    - (time.time() - self._stats.state_changed_at),
                )

        try:
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.timeout,
            )
            await self._record_success()
            return result
        except asyncio.TimeoutError as e:
            await self._record_failure()
            raise CircuitTimeoutError(f"Circuit '{self.name}' timed out") from e
        except Exception as e:
            await self._record_failure()
            raise

    async def _record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            self._stats.successes += 1
            self._stats.last_success_time = time.time()

            if self._stats.state == CircuitState.HALF_OPEN:
                if self._stats.successes >= self.success_threshold:
                    self._stats.failures = 0
                    self._stats.state = CircuitState.CLOSED
                    self._stats.state_changed_at = time.time()

    async def _record_failure(self) -> None:
        """Record a failed call."""
        async with self._lock:
            self._stats.failures += 1
            self._stats.last_failure_time = time.time()

            if self._stats.state == CircuitState.HALF_OPEN:
                self._stats.state = CircuitState.OPEN
                self._stats.state_changed_at = time.time()
            elif self._stats.failures >= self.failure_threshold:
                self._stats.state = CircuitState.OPEN
                self._stats.state_changed_at = time.time()

    async def __aenter__(self) -> "CircuitBreaker":
        if self.is_open:
            raise CircuitOpenError(
                f"Circuit '{self.name}' is open",
                retry_after=self.recovery_timeout - (time.time() - self._stats.state_changed_at),
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            await self._record_failure()
        else:
            await self._record_success()

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self._stats.state.value,
            "failures": self._stats.failures,
            "successes": self._stats.successes,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }


class CircuitOpenError(Exception):
    """Circuit is open, requests are blocked."""

    def __init__(self, message: str, retry_after: float = 0):
        super().__init__(message)
        self.retry_after = retry_after


class CircuitTimeoutError(Exception):
    """Circuit call timed out."""

    pass


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}

    def get(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> CircuitBreaker:
        """Get or create a circuit breaker."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
            )
        return self._breakers[name]

    def get_all_stats(self) -> list[dict[str, Any]]:
        """Get stats for all circuit breakers."""
        return [breaker.get_stats() for breaker in self._breakers.values()]

    def reset(self, name: str) -> bool:
        """Reset a circuit breaker."""
        if name in self._breakers:
            self._breakers[name]._stats = CircuitStats()
            return True
        return False


circuit_registry = CircuitBreakerRegistry()

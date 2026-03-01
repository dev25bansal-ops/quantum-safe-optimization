"""
Quantum Backend Connection Manager

Provides unified management for quantum computing backend connections with:
- Connection pooling and reuse
- Health monitoring and circuit breaker pattern
- Automatic failover and retry logic
- Credential management
- Usage tracking and metrics
"""

import asyncio
import logging
import os
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type

from .base import BackendConfig, BackendType, QuantumBackend

logger = logging.getLogger(__name__)


class ConnectionState(str, Enum):
    """State of a backend connection."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    UNHEALTHY = "unhealthy"
    CIRCUIT_OPEN = "circuit_open"


class ProviderStatus(str, Enum):
    """Overall provider health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker pattern."""

    failure_threshold: int = 5  # Failures before opening circuit
    success_threshold: int = 3  # Successes before closing circuit
    timeout_seconds: int = 60  # Time before half-open state
    half_open_max_calls: int = 3  # Calls allowed in half-open state


@dataclass
class RetryConfig:
    """Configuration for retry logic."""

    max_retries: int = 3
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True


@dataclass
class ConnectionPoolConfig:
    """Configuration for connection pooling."""

    max_connections_per_backend: int = 5
    connection_timeout_seconds: int = 30
    idle_timeout_seconds: int = 300
    health_check_interval_seconds: int = 60


@dataclass
class BackendCredentials:
    """Credentials for a quantum backend."""

    api_token: Optional[str] = None
    api_key: Optional[str] = None
    region: Optional[str] = None
    instance: Optional[str] = None
    resource_id: Optional[str] = None
    s3_bucket: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_environment(cls, backend_type: BackendType) -> "BackendCredentials":
        """Load credentials from environment variables."""
        if backend_type == BackendType.IBM_QUANTUM:
            return cls(
                api_token=os.getenv("IBM_QUANTUM_TOKEN"),
                instance=os.getenv("IBM_QUANTUM_INSTANCE"),
                extra={
                    "channel": os.getenv("IBM_QUANTUM_CHANNEL", "ibm_quantum"),
                    "hub": os.getenv("IBM_QUANTUM_HUB"),
                    "group": os.getenv("IBM_QUANTUM_GROUP"),
                    "project": os.getenv("IBM_QUANTUM_PROJECT"),
                },
            )
        elif backend_type == BackendType.AWS_BRAKET:
            return cls(
                region=os.getenv("AWS_REGION", "us-east-1"),
                s3_bucket=os.getenv("BRAKET_S3_BUCKET"),
                extra={
                    "access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
                    "secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
                    "session_token": os.getenv("AWS_SESSION_TOKEN"),
                },
            )
        elif backend_type == BackendType.AZURE_QUANTUM:
            return cls(
                resource_id=os.getenv("AZURE_QUANTUM_RESOURCE_ID"),
                region=os.getenv("AZURE_QUANTUM_LOCATION", "eastus"),
                extra={
                    "subscription_id": os.getenv("AZURE_SUBSCRIPTION_ID"),
                    "resource_group": os.getenv("AZURE_RESOURCE_GROUP"),
                    "workspace_name": os.getenv("AZURE_QUANTUM_WORKSPACE"),
                },
            )
        elif backend_type == BackendType.DWAVE:
            return cls(
                api_token=os.getenv("DWAVE_API_TOKEN"),
                region=os.getenv("DWAVE_REGION", "na-west-1"),
                extra={
                    "solver": os.getenv("DWAVE_SOLVER"),
                    "endpoint": os.getenv("DWAVE_ENDPOINT"),
                },
            )
        else:
            return cls()


@dataclass
class CircuitBreakerState:
    """State tracking for circuit breaker."""

    failures: int = 0
    successes: int = 0
    state: ConnectionState = ConnectionState.DISCONNECTED
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    half_open_calls: int = 0


@dataclass
class ConnectionMetrics:
    """Metrics for a backend connection."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    last_request_time: Optional[datetime] = None
    last_error: Optional[str] = None

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    @property
    def average_latency_ms(self) -> float:
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency_ms / self.successful_requests


@dataclass
class ManagedConnection:
    """A managed backend connection with metadata."""

    backend: QuantumBackend
    created_at: datetime
    last_used_at: datetime
    state: ConnectionState
    circuit_breaker: CircuitBreakerState
    metrics: ConnectionMetrics
    in_use: bool = False


class BackendConnectionManager:
    """
    Manages connections to quantum computing backends.

    Features:
    - Connection pooling with configurable limits
    - Circuit breaker pattern for fault tolerance
    - Health monitoring with automatic recovery
    - Credential management from environment
    - Metrics collection and reporting
    """

    _instance: Optional["BackendConnectionManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "BackendConnectionManager":
        """Singleton pattern for connection manager."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        pool_config: Optional[ConnectionPoolConfig] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
        retry_config: Optional[RetryConfig] = None,
    ):
        if self._initialized:
            return

        self._pool_config = pool_config or ConnectionPoolConfig()
        self._circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig()
        self._retry_config = retry_config or RetryConfig()

        # Connection pools per backend type
        self._pools: Dict[BackendType, List[ManagedConnection]] = defaultdict(list)
        self._pool_locks: Dict[BackendType, asyncio.Lock] = {}

        # Credentials cache
        self._credentials: Dict[BackendType, BackendCredentials] = {}

        # Backend class registry
        self._backend_classes: Dict[BackendType, Type[QuantumBackend]] = {}

        # Health check task
        self._health_check_task: Optional[asyncio.Task] = None

        # Global metrics
        self._global_metrics: Dict[BackendType, ConnectionMetrics] = defaultdict(ConnectionMetrics)

        self._initialized = True
        self._running = False

        # Register default backend classes
        self._register_default_backends()

    def _register_default_backends(self) -> None:
        """Register default backend implementations."""
        from .aws import AWSBraketBackend
        from .azure import AzureQuantumBackend
        from .dwave import DWaveBackend
        from .ibm import IBMQuantumBackend
        from .simulator import LocalSimulatorBackend

        self._backend_classes[BackendType.IBM_QUANTUM] = IBMQuantumBackend
        self._backend_classes[BackendType.AWS_BRAKET] = AWSBraketBackend
        self._backend_classes[BackendType.AZURE_QUANTUM] = AzureQuantumBackend
        self._backend_classes[BackendType.DWAVE] = DWaveBackend
        self._backend_classes[BackendType.LOCAL_SIMULATOR] = LocalSimulatorBackend

    def register_backend_class(
        self, backend_type: BackendType, backend_class: Type[QuantumBackend]
    ) -> None:
        """Register a custom backend class."""
        self._backend_classes[backend_type] = backend_class

    async def start(self) -> None:
        """Start the connection manager and health monitoring."""
        if self._running:
            return

        self._running = True

        # Initialize pool locks
        for backend_type in BackendType:
            self._pool_locks[backend_type] = asyncio.Lock()

        # Load credentials from environment
        for backend_type in BackendType:
            if backend_type != BackendType.LOCAL_SIMULATOR:
                self._credentials[backend_type] = BackendCredentials.from_environment(backend_type)

        # Start health check task
        self._health_check_task = asyncio.create_task(self._health_check_loop())

        logger.info("Backend connection manager started")

    async def stop(self) -> None:
        """Stop the connection manager and close all connections."""
        self._running = False

        # Cancel health check task
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        for backend_type, pool in self._pools.items():
            for conn in pool:
                try:
                    await conn.backend.disconnect()
                except Exception as e:
                    logger.warning(f"Error closing connection to {backend_type}: {e}")

        self._pools.clear()
        logger.info("Backend connection manager stopped")

    async def get_connection(
        self,
        backend_type: BackendType,
        device_name: Optional[str] = None,
        credentials: Optional[BackendCredentials] = None,
    ) -> QuantumBackend:
        """
        Get a connection to a quantum backend.

        Args:
            backend_type: Type of backend to connect to
            device_name: Specific device to target
            credentials: Override credentials (uses env vars if not provided)

        Returns:
            Connected QuantumBackend instance

        Raises:
            ConnectionError: If unable to establish connection
        """
        if backend_type not in self._backend_classes:
            raise ValueError(f"Unknown backend type: {backend_type}")

        # Get or create pool lock
        if backend_type not in self._pool_locks:
            self._pool_locks[backend_type] = asyncio.Lock()

        async with self._pool_locks[backend_type]:
            # Try to reuse existing connection
            pool = self._pools[backend_type]
            for conn in pool:
                if not conn.in_use and conn.state == ConnectionState.CONNECTED:
                    # Check if circuit breaker allows
                    if self._can_use_connection(conn):
                        conn.in_use = True
                        conn.last_used_at = datetime.utcnow()
                        return conn.backend

            # Need to create new connection
            if len(pool) >= self._pool_config.max_connections_per_backend:
                # Wait for an available connection or timeout
                raise ConnectionError(
                    f"Connection pool exhausted for {backend_type}. "
                    f"Max connections: {self._pool_config.max_connections_per_backend}"
                )

            # Create new connection
            conn = await self._create_connection(backend_type, device_name, credentials)
            pool.append(conn)
            conn.in_use = True
            return conn.backend

    async def release_connection(
        self,
        backend: QuantumBackend,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """
        Release a connection back to the pool.

        Args:
            backend: The backend to release
            success: Whether the last operation was successful
            error: Error message if operation failed
        """
        backend_type = backend.backend_type

        async with self._pool_locks.get(backend_type, asyncio.Lock()):
            for conn in self._pools.get(backend_type, []):
                if conn.backend is backend:
                    conn.in_use = False
                    conn.last_used_at = datetime.utcnow()

                    # Update metrics
                    conn.metrics.total_requests += 1
                    if success:
                        conn.metrics.successful_requests += 1
                        self._record_circuit_breaker_success(conn)
                    else:
                        conn.metrics.failed_requests += 1
                        conn.metrics.last_error = error
                        self._record_circuit_breaker_failure(conn)

                    # Update global metrics
                    global_metrics = self._global_metrics[backend_type]
                    global_metrics.total_requests += 1
                    if success:
                        global_metrics.successful_requests += 1
                    else:
                        global_metrics.failed_requests += 1
                        global_metrics.last_error = error
                    global_metrics.last_request_time = datetime.utcnow()

                    return

    async def _create_connection(
        self,
        backend_type: BackendType,
        device_name: Optional[str] = None,
        credentials: Optional[BackendCredentials] = None,
    ) -> ManagedConnection:
        """Create a new backend connection with retry logic."""
        creds = credentials or self._credentials.get(backend_type, BackendCredentials())

        config = BackendConfig(
            backend_type=backend_type,
            api_token=creds.api_token,
            region=creds.region,
            device_name=device_name,
            extra_config=creds.extra,
        )

        backend_class = self._backend_classes[backend_type]
        backend = backend_class(config)

        # Connect with retry logic
        last_error = None
        for attempt in range(self._retry_config.max_retries + 1):
            try:
                await asyncio.wait_for(
                    backend.connect(), timeout=self._pool_config.connection_timeout_seconds
                )

                return ManagedConnection(
                    backend=backend,
                    created_at=datetime.utcnow(),
                    last_used_at=datetime.utcnow(),
                    state=ConnectionState.CONNECTED,
                    circuit_breaker=CircuitBreakerState(state=ConnectionState.CONNECTED),
                    metrics=ConnectionMetrics(),
                )
            except asyncio.TimeoutError:
                last_error = "Connection timeout"
            except Exception as e:
                last_error = str(e)

            if attempt < self._retry_config.max_retries:
                delay = self._calculate_retry_delay(attempt)
                logger.warning(
                    f"Connection attempt {attempt + 1} to {backend_type} failed: {last_error}. "
                    f"Retrying in {delay:.1f}s"
                )
                await asyncio.sleep(delay)

        raise ConnectionError(
            f"Failed to connect to {backend_type} after "
            f"{self._retry_config.max_retries + 1} attempts: {last_error}"
        )

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff and optional jitter."""
        import random

        delay = min(
            self._retry_config.initial_delay_seconds
            * (self._retry_config.exponential_base**attempt),
            self._retry_config.max_delay_seconds,
        )

        if self._retry_config.jitter:
            delay *= 0.5 + random.random()

        return delay

    def _can_use_connection(self, conn: ManagedConnection) -> bool:
        """Check if circuit breaker allows using this connection."""
        cb = conn.circuit_breaker

        if cb.state == ConnectionState.CIRCUIT_OPEN:
            # Check if timeout has passed
            if cb.last_failure_time:
                elapsed = (datetime.utcnow() - cb.last_failure_time).total_seconds()
                if elapsed >= self._circuit_breaker_config.timeout_seconds:
                    # Move to half-open state
                    cb.state = ConnectionState.CONNECTED
                    cb.half_open_calls = 0
                    return True
            return False

        return True

    def _record_circuit_breaker_success(self, conn: ManagedConnection) -> None:
        """Record a successful operation for circuit breaker."""
        cb = conn.circuit_breaker
        cb.successes += 1
        cb.last_success_time = datetime.utcnow()

        if cb.state == ConnectionState.UNHEALTHY:
            if cb.successes >= self._circuit_breaker_config.success_threshold:
                cb.state = ConnectionState.CONNECTED
                cb.failures = 0
                logger.info(f"Circuit breaker closed for {conn.backend.backend_type}")

    def _record_circuit_breaker_failure(self, conn: ManagedConnection) -> None:
        """Record a failed operation for circuit breaker."""
        cb = conn.circuit_breaker
        cb.failures += 1
        cb.successes = 0
        cb.last_failure_time = datetime.utcnow()

        if cb.failures >= self._circuit_breaker_config.failure_threshold:
            cb.state = ConnectionState.CIRCUIT_OPEN
            logger.warning(
                f"Circuit breaker opened for {conn.backend.backend_type} "
                f"after {cb.failures} failures"
            )

    async def _health_check_loop(self) -> None:
        """Periodic health check for all connections."""
        while self._running:
            try:
                await asyncio.sleep(self._pool_config.health_check_interval_seconds)
                await self._perform_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")

    async def _perform_health_checks(self) -> None:
        """Perform health checks on all connections."""
        for backend_type, pool in list(self._pools.items()):
            for conn in pool:
                if conn.in_use:
                    continue

                # Check idle timeout
                idle_time = (datetime.utcnow() - conn.last_used_at).total_seconds()
                if idle_time > self._pool_config.idle_timeout_seconds:
                    await self._close_connection(backend_type, conn)
                    continue

                # Perform health check
                try:
                    if hasattr(conn.backend, "health_check"):
                        await asyncio.wait_for(conn.backend.health_check(), timeout=10)
                    conn.state = ConnectionState.CONNECTED
                except Exception as e:
                    logger.warning(f"Health check failed for {backend_type}: {e}")
                    conn.state = ConnectionState.UNHEALTHY

    async def _close_connection(self, backend_type: BackendType, conn: ManagedConnection) -> None:
        """Close and remove a connection from the pool."""
        try:
            await conn.backend.disconnect()
        except Exception as e:
            logger.warning(f"Error closing connection: {e}")

        async with self._pool_locks.get(backend_type, asyncio.Lock()):
            if conn in self._pools[backend_type]:
                self._pools[backend_type].remove(conn)

    def get_provider_status(self, backend_type: BackendType) -> ProviderStatus:
        """Get overall health status for a provider."""
        pool = self._pools.get(backend_type, [])

        if not pool:
            return ProviderStatus.UNKNOWN

        connected = sum(1 for c in pool if c.state == ConnectionState.CONNECTED)
        unhealthy = sum(
            1 for c in pool if c.state in (ConnectionState.UNHEALTHY, ConnectionState.CIRCUIT_OPEN)
        )

        if unhealthy == len(pool):
            return ProviderStatus.UNHEALTHY
        elif unhealthy > 0:
            return ProviderStatus.DEGRADED
        elif connected > 0:
            return ProviderStatus.HEALTHY
        else:
            return ProviderStatus.UNKNOWN

    def get_metrics(self, backend_type: Optional[BackendType] = None) -> Dict[str, Any]:
        """Get connection metrics."""
        if backend_type:
            metrics = self._global_metrics.get(backend_type, ConnectionMetrics())
            pool = self._pools.get(backend_type, [])
            return {
                "backend_type": backend_type.value,
                "status": self.get_provider_status(backend_type).value,
                "pool_size": len(pool),
                "active_connections": sum(1 for c in pool if c.in_use),
                "total_requests": metrics.total_requests,
                "successful_requests": metrics.successful_requests,
                "failed_requests": metrics.failed_requests,
                "success_rate": metrics.success_rate,
                "average_latency_ms": metrics.average_latency_ms,
                "last_error": metrics.last_error,
            }
        else:
            return {
                backend_type.value: self.get_metrics(backend_type) for backend_type in BackendType
            }

    def get_available_backends(self) -> List[Dict[str, Any]]:
        """Get list of available backends with their status."""
        return [
            {
                "type": backend_type.value,
                "status": self.get_provider_status(backend_type).value,
                "configured": backend_type in self._credentials
                and bool(
                    self._credentials[backend_type].api_token
                    or backend_type == BackendType.LOCAL_SIMULATOR
                ),
            }
            for backend_type in BackendType
        ]


# Singleton instance
_connection_manager: Optional[BackendConnectionManager] = None


def get_connection_manager() -> BackendConnectionManager:
    """Get the singleton connection manager instance."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = BackendConnectionManager()
    return _connection_manager


async def get_backend(
    backend_type: BackendType,
    device_name: Optional[str] = None,
) -> QuantumBackend:
    """
    Convenience function to get a backend connection.

    Args:
        backend_type: Type of backend
        device_name: Target device name

    Returns:
        Connected QuantumBackend
    """
    manager = get_connection_manager()
    if not manager._running:
        await manager.start()
    return await manager.get_connection(backend_type, device_name)


async def release_backend(
    backend: QuantumBackend,
    success: bool = True,
    error: Optional[str] = None,
) -> None:
    """
    Convenience function to release a backend connection.

    Args:
        backend: Backend to release
        success: Whether operation was successful
        error: Error message if failed
    """
    manager = get_connection_manager()
    await manager.release_connection(backend, success, error)


class BackendContext:
    """
    Context manager for backend connections.

    Example:
        async with BackendContext(BackendType.IBM_QUANTUM) as backend:
            result = await backend.execute_circuit(circuit)
    """

    def __init__(
        self,
        backend_type: BackendType,
        device_name: Optional[str] = None,
    ):
        self.backend_type = backend_type
        self.device_name = device_name
        self.backend: Optional[QuantumBackend] = None
        self._success = True
        self._error: Optional[str] = None

    async def __aenter__(self) -> QuantumBackend:
        self.backend = await get_backend(self.backend_type, self.device_name)
        return self.backend

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self._success = False
            self._error = str(exc_val)

        if self.backend:
            await release_backend(self.backend, self._success, self._error)

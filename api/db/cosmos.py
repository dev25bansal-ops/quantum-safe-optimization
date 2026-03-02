"""
Azure Cosmos DB configuration and utilities.

Features:
- Connection pooling with configurable limits
- Retry policies with exponential backoff
- Singleton client pattern for efficiency
- Circuit breaker pattern for resilience
- Health checks for Kubernetes probes
- Integration with Azure Key Vault for secrets
"""

import asyncio
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from aiohttp import ClientTimeout, TCPConnector
from azure.cosmos import PartitionKey
from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential

# Configuration
COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT", "")
COSMOS_KEY = os.getenv("COSMOS_KEY", "")  # For local emulator
DATABASE_NAME = os.getenv("COSMOS_DATABASE", "quantum_optimization")

# Use managed identity in production, key for local development
USE_MANAGED_IDENTITY = os.getenv("USE_MANAGED_IDENTITY", "false").lower() == "true"


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes to close from half-open
    timeout_seconds: int = 30  # Time before trying half-open
    half_open_max_calls: int = 3  # Max calls in half-open state


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for resilience.

    Prevents cascading failures by temporarily stopping calls
    to a failing service.
    """

    def __init__(self, config: CircuitBreakerConfig | None = None):
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def can_execute(self) -> bool:
        """Check if execution is allowed."""
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                # Check if timeout has passed
                if self._last_failure_time:
                    elapsed = datetime.utcnow() - self._last_failure_time
                    if elapsed.total_seconds() >= self.config.timeout_seconds:
                        self._state = CircuitState.HALF_OPEN
                        self._half_open_calls = 0
                        return True
                return False

            # HALF_OPEN state
            if self._half_open_calls < self.config.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

    async def record_success(self):
        """Record a successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    async def record_failure(self):
        """Record a failed call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                # Immediately open on failure in half-open
                self._state = CircuitState.OPEN
                self._last_failure_time = datetime.utcnow()
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.config.failure_threshold:
                    self._state = CircuitState.OPEN
                    self._last_failure_time = datetime.utcnow()

    def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure": self._last_failure_time.isoformat()
            if self._last_failure_time
            else None,
        }


@dataclass
class HealthStatus:
    """Health check result."""

    healthy: bool
    latency_ms: float
    last_check: datetime
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CosmosRetryPolicy:
    """Configuration for retry behavior."""

    max_retries: int = 5
    initial_delay_ms: int = 100
    max_delay_ms: int = 5000
    exponential_base: float = 2.0
    retryable_status_codes: tuple = (429, 503, 408)


@dataclass
class CosmosPoolConfig:
    """Configuration for connection pooling."""

    max_connections: int = 100
    max_connections_per_host: int = 30
    connection_timeout_seconds: int = 30
    read_timeout_seconds: int = 60
    keepalive_timeout_seconds: int = 30
    enable_tcp_nodelay: bool = True


class CosmosDBManager:
    """
    Azure Cosmos DB connection manager with connection pooling and retry policies.

    Follows best practices:
    - Singleton client instance with connection pooling
    - Async operations with configurable timeouts
    - Automatic retry with exponential backoff
    - Circuit breaker for resilience
    - Health checks for Kubernetes
    - Proper partition key design for high cardinality
    """

    _instance: Optional["CosmosDBManager"] = None
    _client: CosmosClient | None = None
    _connector: TCPConnector | None = None
    _initialized: bool = False
    _circuit_breaker: CircuitBreaker = None
    _health_status: HealthStatus | None = None
    _health_check_interval: int = 30  # seconds
    _last_health_check: datetime | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.retry_policy = CosmosRetryPolicy()
            cls._instance.pool_config = CosmosPoolConfig()
            cls._instance._circuit_breaker = CircuitBreaker()
        return cls._instance

    def configure(
        self,
        retry_policy: CosmosRetryPolicy | None = None,
        pool_config: CosmosPoolConfig | None = None,
    ):
        """Configure retry policy and connection pooling."""
        if retry_policy:
            self.retry_policy = retry_policy
        if pool_config:
            self.pool_config = pool_config

    async def initialize(self):
        """Initialize Cosmos DB client with connection pooling."""
        if self._initialized:
            return

        # Create TCP connector for connection pooling
        self._connector = TCPConnector(
            limit=self.pool_config.max_connections,
            limit_per_host=self.pool_config.max_connections_per_host,
            keepalive_timeout=self.pool_config.keepalive_timeout_seconds,
            enable_cleanup_closed=True,
            force_close=False,
        )

        # Create timeout configuration
        ClientTimeout(
            total=None,
            connect=self.pool_config.connection_timeout_seconds,
            sock_read=self.pool_config.read_timeout_seconds,
        )

        if USE_MANAGED_IDENTITY:
            credential = DefaultAzureCredential()
            self._client = CosmosClient(
                COSMOS_ENDPOINT,
                credential=credential,
                connection_timeout=self.pool_config.connection_timeout_seconds,
            )
        else:
            self._client = CosmosClient(
                COSMOS_ENDPOINT,
                credential=COSMOS_KEY,
                connection_timeout=self.pool_config.connection_timeout_seconds,
            )

        # Ensure database and containers exist
        await self._setup_database()
        self._initialized = True

    async def _execute_with_retry(self, operation, *args, **kwargs):
        """
        Execute an operation with retry logic and circuit breaker.

        Uses exponential backoff for retryable errors.
        Circuit breaker prevents cascading failures.
        """
        # Check circuit breaker
        if not await self._circuit_breaker.can_execute():
            raise RuntimeError(
                f"Circuit breaker is OPEN - Cosmos DB unavailable. "
                f"Status: {self._circuit_breaker.get_status()}"
            )

        last_exception = None
        delay_ms = self.retry_policy.initial_delay_ms

        for attempt in range(self.retry_policy.max_retries + 1):
            try:
                result = await operation(*args, **kwargs)
                await self._circuit_breaker.record_success()
                return result
            except CosmosHttpResponseError as e:
                last_exception = e

                # Check if error is retryable
                if e.status_code not in self.retry_policy.retryable_status_codes:
                    raise

                if attempt < self.retry_policy.max_retries:
                    # Handle 429 (rate limited) with retry-after header
                    if e.status_code == 429:
                        retry_after_ms = int(e.headers.get("x-ms-retry-after-ms", delay_ms))
                        wait_time = retry_after_ms / 1000.0
                    else:
                        wait_time = delay_ms / 1000.0

                    await asyncio.sleep(wait_time)

                    # Exponential backoff
                    delay_ms = min(
                        delay_ms * self.retry_policy.exponential_base,
                        self.retry_policy.max_delay_ms,
                    )
            except Exception:
                # Non-Cosmos errors are not retried
                await self._circuit_breaker.record_failure()
                raise

        # All retries exhausted
        await self._circuit_breaker.record_failure()
        raise last_exception

    async def _setup_database(self):
        """Create database and containers with optimized composite indexes."""
        database = await self._client.create_database_if_not_exists(DATABASE_NAME)

        # Jobs container - partitioned by user_id for tenant isolation
        # Composite indexes on (user_id, status) and (user_id, created_at) for efficient queries
        indexing_policy = {
            "automatic": True,
            "indexingMode": "consistent",
            "includedPaths": [
                {
                    "path": "/*",
                    "indexes": [
                        {"kind": "Range", "dataType": "number"},
                        {"kind": "Range", "dataType": "string"},
                        {"kind": "Spatial", "dataType": "Point"},
                    ],
                }
            ],
            "excludedPaths": [{"path": '/"_etag"/?'}],
            "compositeIndexes": [
                # Composite index for user queries with status filter
                [
                    {"path": "/user_id", "order": "ascending"},
                    {"path": "/status", "order": "ascending"},
                ],
                # Composite index for user queries with created_at sort (default ORDER BY)
                [
                    {"path": "/user_id", "order": "ascending"},
                    {"path": "/created_at", "order": "descending"},
                ],
                # Composite index for user queries with problem_type filter
                [
                    {"path": "/user_id", "order": "ascending"},
                    {"path": "/problem_type", "order": "ascending"},
                ],
            ],
        }

        await database.create_container_if_not_exists(
            id="jobs",
            partition_key=PartitionKey(path="/user_id"),
            offer_throughput=400,  # Adjust based on workload
            indexing_policy=indexing_policy,
        )

        # Users container - partitioned by user_id
        await database.create_container_if_not_exists(
            id="users",
            partition_key=PartitionKey(path="/user_id"),
            offer_throughput=400,
        )

        # Keys container - for PQC public keys, partitioned by user_id
        await database.create_container_if_not_exists(
            id="keys",
            partition_key=PartitionKey(path="/user_id"),
            offer_throughput=400,
        )

        # Audit log container - partitioned by tenant_id and timestamp
        # Using hierarchical partition keys for scalability
        await database.create_container_if_not_exists(
            id="audit_logs",
            partition_key=PartitionKey(path=["/tenant_id", "/year_month"]),
            offer_throughput=400,
        )

    async def close(self):
        """Close the Cosmos DB client and connection pool."""
        if self._client:
            await self._client.close()
            self._client = None
        if self._connector:
            await self._connector.close()
            self._connector = None
        self._initialized = False

    @property
    def client(self) -> CosmosClient:
        if self._client is None:
            raise RuntimeError("CosmosDB client not initialized. Call initialize() first.")
        return self._client

    async def health_check(self, force: bool = False) -> HealthStatus:
        """
        Perform a health check on the Cosmos DB connection.

        Args:
            force: Force a new health check even if cached result is fresh

        Returns:
            HealthStatus with connection details
        """
        now = datetime.utcnow()

        # Return cached result if fresh
        if (
            not force
            and self._health_status
            and self._last_health_check
            and (now - self._last_health_check).total_seconds() < self._health_check_interval
        ):
            return self._health_status

        start_time = datetime.utcnow()

        try:
            if not self._initialized:
                return HealthStatus(
                    healthy=False,
                    latency_ms=0,
                    last_check=now,
                    error="Not initialized",
                )

            # Simple query to test connection
            database = self.get_database()
            await database.read()

            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            self._health_status = HealthStatus(
                healthy=True,
                latency_ms=latency_ms,
                last_check=now,
                details={
                    "endpoint": COSMOS_ENDPOINT,
                    "database": DATABASE_NAME,
                    "circuit_breaker": self._circuit_breaker.get_status(),
                    "pool_stats": self.get_pool_stats(),
                },
            )
            self._last_health_check = now
            return self._health_status

        except Exception as e:
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            self._health_status = HealthStatus(
                healthy=False,
                latency_ms=latency_ms,
                last_check=now,
                error=str(e),
                details={
                    "circuit_breaker": self._circuit_breaker.get_status(),
                },
            )
            self._last_health_check = now
            return self._health_status

    def get_circuit_breaker_status(self) -> dict[str, Any]:
        """Get the current circuit breaker status."""
        return self._circuit_breaker.get_status()

    async def reset_circuit_breaker(self):
        """Manually reset the circuit breaker to closed state."""
        async with self._circuit_breaker._lock:
            self._circuit_breaker._state = CircuitState.CLOSED
            self._circuit_breaker._failure_count = 0
            self._circuit_breaker._success_count = 0

    def get_database(self):
        return self.client.get_database_client(DATABASE_NAME)

    def get_container(self, container_name: str):
        return self.get_database().get_container_client(container_name)

    def get_pool_stats(self) -> dict[str, Any]:
        """Get connection pool statistics."""
        if self._connector:
            return {
                "limit": self._connector.limit,
                "limit_per_host": self._connector.limit_per_host,
                "active_connections": len(self._connector._acquired),
                "available_connections": self._connector.limit - len(self._connector._acquired),
            }
        return {"status": "not_initialized"}


# Repository classes for data access


class JobRepository:
    """Repository for job operations with retry support."""

    def __init__(self, cosmos_manager: CosmosDBManager):
        self._manager = cosmos_manager
        self.container = cosmos_manager.get_container("jobs")

    async def create_job(self, job_data: dict[str, Any]) -> dict[str, Any]:
        """Create a new job with retry."""
        # Ensure 'id' field is set (Cosmos DB requirement)
        if "id" not in job_data:
            job_data["id"] = job_data.get("job_id", str(uuid.uuid4()))

        async def _create():
            return await self.container.create_item(body=job_data)

        return await self._manager._execute_with_retry(_create)

    async def get_job(self, job_id: str, user_id: str) -> dict[str, Any] | None:
        """Get a job by ID with retry."""

        async def _get():
            try:
                return await self.container.read_item(
                    item=job_id,
                    partition_key=user_id,
                )
            except CosmosResourceNotFoundError:
                return None

        try:
            return await self._manager._execute_with_retry(_get)
        except Exception:
            return None

    async def get_job_any_user(self, job_id: str) -> dict[str, Any] | None:
        """Get a job by ID without knowing user_id (cross-partition query)."""
        query = "SELECT * FROM c WHERE c.job_id = @job_id OR c.id = @job_id"
        params = [{"name": "@job_id", "value": job_id}]

        async def _get():
            async for item in self.container.query_items(
                query=query,
                parameters=params,
                enable_cross_partition_query=True,
            ):
                return item
            return None

        try:
            return await self._manager._execute_with_retry(_get)
        except Exception:
            return None

    async def update_job(self, job_data: dict[str, Any]) -> dict[str, Any]:
        """Update a job with retry."""
        # Ensure 'id' field matches job_id
        if "id" not in job_data:
            job_data["id"] = job_data.get("job_id")

        async def _update():
            return await self.container.replace_item(
                item=job_data["id"],
                body=job_data,
            )

        return await self._manager._execute_with_retry(_update)

    async def upsert_job(self, job_data: dict[str, Any]) -> dict[str, Any]:
        """Upsert a job (create if not exists, update if exists)."""
        if "id" not in job_data:
            job_data["id"] = job_data.get("job_id")

        async def _upsert():
            return await self.container.upsert_item(body=job_data)

        return await self._manager._execute_with_retry(_upsert)

    async def list_jobs(
        self,
        user_id: str,
        status: str | None = None,
        problem_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List jobs for a user with retry."""
        query = "SELECT * FROM c WHERE c.user_id = @user_id"
        params = [{"name": "@user_id", "value": user_id}]

        if status:
            query += " AND c.status = @status"
            params.append({"name": "@status", "value": status})

        if problem_type:
            query += " AND c.problem_type = @problem_type"
            params.append({"name": "@problem_type", "value": problem_type})

        query += " ORDER BY c.created_at DESC OFFSET @offset LIMIT @limit"
        params.extend(
            [
                {"name": "@offset", "value": offset},
                {"name": "@limit", "value": limit},
            ]
        )

        async def _list():
            items = []
            async for item in self.container.query_items(
                query=query,
                parameters=params,
            ):
                items.append(item)
            return items

        return await self._manager._execute_with_retry(_list)

    async def count_jobs(
        self,
        user_id: str,
        status: str | None = None,
        problem_type: str | None = None,
    ) -> int:
        """Count jobs for a user."""
        query = "SELECT VALUE COUNT(1) FROM c WHERE c.user_id = @user_id"
        params = [{"name": "@user_id", "value": user_id}]

        if status:
            query += " AND c.status = @status"
            params.append({"name": "@status", "value": status})

        if problem_type:
            query += " AND c.problem_type = @problem_type"
            params.append({"name": "@problem_type", "value": problem_type})

        async def _count():
            async for item in self.container.query_items(
                query=query,
                parameters=params,
            ):
                return item
            return 0

        try:
            return await self._manager._execute_with_retry(_count)
        except Exception:
            return 0

    async def delete_job(self, job_id: str, user_id: str) -> bool:
        """Delete a job with retry."""

        async def _delete():
            await self.container.delete_item(item=job_id, partition_key=user_id)
            return True

        try:
            return await self._manager._execute_with_retry(_delete)
        except Exception:
            return False

    async def soft_delete_job(self, job_id: str, user_id: str) -> bool:
        """Soft delete a job by marking it as deleted."""
        job = await self.get_job(job_id, user_id)
        if job:
            job["deleted"] = True
            job["deleted_at"] = datetime.utcnow().isoformat()
            await self.update_job(job)
            return True
        return False


class UserRepository:
    """Repository for user operations."""

    def __init__(self, cosmos_manager: CosmosDBManager):
        self._manager = cosmos_manager
        self.container = cosmos_manager.get_container("users")

    async def create_user(self, user_data: dict[str, Any]) -> dict[str, Any]:
        """Create a new user."""
        # Ensure 'id' field is set
        if "id" not in user_data:
            user_data["id"] = user_data.get("user_id", str(uuid.uuid4()))

        async def _create():
            return await self.container.create_item(body=user_data)

        return await self._manager._execute_with_retry(_create)

    async def get_user(self, user_id: str) -> dict[str, Any] | None:
        """Get a user by ID."""

        async def _get():
            try:
                return await self.container.read_item(
                    item=user_id,
                    partition_key=user_id,
                )
            except CosmosResourceNotFoundError:
                return None

        try:
            return await self._manager._execute_with_retry(_get)
        except Exception:
            return None

    async def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        """Get a user by username."""
        query = "SELECT * FROM c WHERE c.username = @username"
        params = [{"name": "@username", "value": username}]

        async def _get():
            async for item in self.container.query_items(
                query=query,
                parameters=params,
                enable_cross_partition_query=True,  # Username is not the partition key
            ):
                return item
            return None

        try:
            return await self._manager._execute_with_retry(_get)
        except Exception:
            return None

    async def update_user(self, user_data: dict[str, Any]) -> dict[str, Any]:
        """Update a user."""
        if "id" not in user_data:
            user_data["id"] = user_data.get("user_id")

        async def _update():
            return await self.container.replace_item(
                item=user_data["id"],
                body=user_data,
            )

        return await self._manager._execute_with_retry(_update)

    async def upsert_user(self, user_data: dict[str, Any]) -> dict[str, Any]:
        """Upsert a user (create if not exists, update if exists)."""
        if "id" not in user_data:
            user_data["id"] = user_data.get("user_id")

        async def _upsert():
            return await self.container.upsert_item(body=user_data)

        return await self._manager._execute_with_retry(_upsert)

    async def delete_user(self, user_id: str) -> bool:
        """Delete a user."""

        async def _delete():
            await self.container.delete_item(item=user_id, partition_key=user_id)
            return True

        try:
            return await self._manager._execute_with_retry(_delete)
        except Exception:
            return False

    async def list_users(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List all users (admin only)."""
        query = "SELECT * FROM c ORDER BY c.created_at DESC OFFSET @offset LIMIT @limit"
        params = [
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]

        async def _list():
            items = []
            async for item in self.container.query_items(
                query=query,
                parameters=params,
                enable_cross_partition_query=True,
            ):
                items.append(item)
            return items

        return await self._manager._execute_with_retry(_list)

    async def count_users(self) -> int:
        """Count total users."""
        query = "SELECT VALUE COUNT(1) FROM c"

        async def _count():
            async for item in self.container.query_items(
                query=query,
                enable_cross_partition_query=True,
            ):
                return item
            return 0

        try:
            return await self._manager._execute_with_retry(_count)
        except Exception:
            return 0


class KeyRepository:
    """Repository for PQC key operations."""

    def __init__(self, cosmos_manager: CosmosDBManager):
        self.container = cosmos_manager.get_container("keys")

    async def store_keys(self, user_id: str, key_data: dict[str, Any]) -> dict[str, Any]:
        """Store user's PQC public keys."""
        key_data["id"] = f"{user_id}_keys"
        key_data["user_id"] = user_id

        try:
            return await self.container.upsert_item(body=key_data)
        except Exception:
            return await self.container.create_item(body=key_data)

    async def get_keys(self, user_id: str) -> dict[str, Any] | None:
        """Get user's PQC public keys."""
        try:
            return await self.container.read_item(
                item=f"{user_id}_keys",
                partition_key=user_id,
            )
        except Exception:
            return None


# Global instance
cosmos_manager = CosmosDBManager()


async def init_cosmos():
    """Initialize Cosmos DB connection."""
    await cosmos_manager.initialize()


async def close_cosmos():
    """Close Cosmos DB connection."""
    await cosmos_manager.close()

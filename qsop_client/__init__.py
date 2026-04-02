"""
QSOP Python SDK Client.

A fully-typed async client library for interacting with the QSOP API.

Features:
    - Automatic authentication with token management
    - Token refresh handling
    - Retry logic with exponential backoff
    - WebSocket support for real-time updates
    - Full type hints for IDE autocomplete
    - Comprehensive error handling

Installation:
    pip install qsop-client

Quick Start:
    ```python
    import asyncio
    from qsop_client import QSOPClient

    async def main():
        async with QSOPClient(base_url="http://localhost:8000") as client:
            # Login
            await client.login("admin", "password")

            # Submit a QAOA MaxCut job
            job = await client.submit_job(
                problem_type="QAOA",
                problem_config={
                    "type": "maxcut",
                    "graph": {"edges": [[0, 1], [1, 2], [2, 0]]}
                },
                parameters={"layers": 2, "shots": 1024}
            )

            # Wait for completion
            job = await client.wait_for_job(job.id)
            print(f"Result: {job.result}")

    asyncio.run(main())
    ```

Synchronous Usage:
    ```python
    from qsop_client import SyncQSOPClient

    with SyncQSOPClient() as client:
        client.login("admin", "password")
        job = client.submit_job(problem_type="QAOA", ...)
        result = client.wait_for_job(job.id)
    ```
"""

from __future__ import annotations

__version__ = "0.3.0"
__author__ = "QSOP Team"
__all__ = [
    "QSOPClient",
    "SyncQSOPClient",
    "QSOPClientError",
    "Job",
    "KeyPair",
    "User",
    "JobStatus",
    "AlgorithmType",
    "BackendType",
    "Tenant",
    "BillingUsage",
    "Invoice",
    "Algorithm",
    "QKDSimulationResult",
    "BenchmarkResult",
]

import asyncio
import base64
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Literal, TypedDict, cast

import httpx

logger = logging.getLogger(__name__)


JobStatus = Literal["pending", "running", "completed", "failed", "cancelled"]
AlgorithmType = Literal["QAOA", "VQE", "ANNEALING", "GROVER"]
BackendType = Literal["qiskit_aer", "ibm_quantum", "aws_braket", "azure_quantum", "dwave_leap"]


class ProblemConfigDict(TypedDict, total=False):
    type: str
    graph: dict[str, Any]
    edges: list[tuple[int, int]]
    weights: list[float]


class JobParametersDict(TypedDict, total=False):
    layers: int
    optimizer: str
    max_iterations: int
    shots: int
    backend: BackendType
    random_seed: int


@dataclass
class Job:
    """
    Represents an optimization job.

    Attributes:
        id: Unique job identifier
        problem_type: Algorithm type (QAOA, VQE, ANNEALING, GROVER)
        status: Current job status
        created_at: ISO timestamp of job creation
        user_id: ID of the user who submitted the job
        progress: Progress percentage (0.0 to 1.0)
        result: Job result when completed
        error: Error message if job failed
    """

    id: str
    problem_type: AlgorithmType
    status: JobStatus
    created_at: str
    user_id: str | None = None
    progress: float = 0.0
    result: dict[str, Any] | None = None
    error: str | None = None
    parameters: JobParametersDict = field(default_factory=lambda: cast(JobParametersDict, {}))
    updated_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Job":
        """Create Job from API response dictionary."""
        return cls(
            id=data["id"],
            problem_type=data.get("problem_type", "QAOA"),
            status=data.get("status", "pending"),
            created_at=data.get("created_at", ""),
            user_id=data.get("user_id"),
            progress=data.get("progress", 0.0),
            result=data.get("result"),
            error=data.get("error"),
            parameters=data.get("parameters", {}),
            updated_at=data.get("updated_at"),
        )


@dataclass
class KeyPair:
    """
    Represents a PQC key pair.

    Attributes:
        key_id: Unique key identifier
        public_key: Base64-encoded public key
        key_type: Key type (kem or signing)
        algorithm: Algorithm name (e.g., ML-KEM-768)
        created_at: ISO timestamp of key creation
        expires_at: ISO timestamp of key expiration
    """

    key_id: str
    public_key: str
    key_type: Literal["kem", "signing"]
    algorithm: str
    created_at: str
    expires_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KeyPair":
        """Create KeyPair from API response dictionary."""
        return cls(
            key_id=data["key_id"],
            public_key=data["public_key"],
            key_type=data.get("key_type", "kem"),
            algorithm=data.get("algorithm", "ML-KEM-768"),
            created_at=data.get("created_at", ""),
            expires_at=data.get("expires_at", ""),
        )


@dataclass
class User:
    """
    Represents an authenticated user.

    Attributes:
        user_id: Unique user identifier
        username: Username
        email: User email address
        roles: List of user roles
        created_at: ISO timestamp of account creation
    """

    user_id: str
    username: str
    email: str | None
    roles: list[str]
    created_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "User":
        """Create User from API response dictionary."""
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            email=data.get("email"),
            roles=data.get("roles", []),
            created_at=data.get("created_at", ""),
        )


@dataclass
class Tenant:
    """Represents a tenant in multi-tenant system."""

    tenant_id: str
    name: str
    tier: str
    is_active: bool
    created_at: str
    quotas: dict[str, int] = field(default_factory=dict)
    usage: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Tenant":
        return cls(
            tenant_id=data["tenant_id"],
            name=data["name"],
            tier=data.get("tier", "free"),
            is_active=data.get("is_active", True),
            created_at=data.get("created_at", ""),
            quotas=data.get("quotas", {}),
            usage=data.get("usage", {}),
        )


@dataclass
class BillingUsage:
    """Represents billing usage event."""

    event_id: str
    resource_type: str
    quantity: int
    unit_price: float
    total_price: float
    timestamp: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BillingUsage":
        return cls(
            event_id=data["event_id"],
            resource_type=data["resource_type"],
            quantity=data["quantity"],
            unit_price=data.get("unit_price", 0.0),
            total_price=data.get("total_price", 0.0),
            timestamp=data.get("timestamp", ""),
        )


@dataclass
class Invoice:
    """Represents a billing invoice."""

    invoice_id: str
    status: str
    subtotal: float
    tax: float
    total: float
    created_at: str
    paid_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Invoice":
        return cls(
            invoice_id=data["invoice_id"],
            status=data.get("status", "pending"),
            subtotal=data.get("subtotal", 0.0),
            tax=data.get("tax", 0.0),
            total=data.get("total", 0.0),
            created_at=data.get("created_at", ""),
            paid_at=data.get("paid_at"),
        )


@dataclass
class Algorithm:
    """Represents an algorithm in the marketplace."""

    algorithm_id: str
    name: str
    description: str
    category: str
    author_name: str
    version: str
    pricing_model: str
    price: float
    downloads: int
    rating_avg: float
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Algorithm":
        return cls(
            algorithm_id=data["algorithm_id"],
            name=data["name"],
            description=data.get("description", ""),
            category=data.get("category", ""),
            author_name=data.get("author_name", ""),
            version=data.get("version", "1.0.0"),
            pricing_model=data.get("pricing_model", "free"),
            price=data.get("price", 0.0),
            downloads=data.get("downloads", 0),
            rating_avg=data.get("rating_avg", 0.0),
            tags=data.get("tags", []),
        )


@dataclass
class QKDSimulationResult:
    """Represents a QKD simulation result."""

    simulation_id: str
    protocol: str
    sifted_key_length: int
    error_rate: float
    secure_key_length: int
    eavesdropper_detected: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QKDSimulationResult":
        return cls(
            simulation_id=data["simulation_id"],
            protocol=data.get("protocol", "bb84"),
            sifted_key_length=data.get("sifted_key_length", 0),
            error_rate=data.get("error_rate", 0.0),
            secure_key_length=data.get("secure_key_length", 0),
            eavesdropper_detected=data.get("eavesdropper_detected", False),
        )


@dataclass
class BenchmarkResult:
    """Represents a benchmark result."""

    benchmark_id: str
    name: str
    category: str
    status: str
    duration_ms: float
    metrics: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BenchmarkResult":
        return cls(
            benchmark_id=data["benchmark_id"],
            name=data.get("name", ""),
            category=data.get("category", ""),
            status=data.get("status", ""),
            duration_ms=data.get("duration_ms", 0.0),
            metrics=data.get("metrics", {}),
        )


class QSOPClientError(Exception):
    """
    Exception raised for API errors.

    Attributes:
        message: Error message
        status_code: HTTP status code (if applicable)
        details: Additional error details from API
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}

    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class QSOPClient:
    """
    Async client for the QSOP API.

    This client handles authentication, token management, retry logic,
    and provides a type-safe interface to the API.

    Args:
        base_url: Base URL of the QSOP API
        username: Default username for login
        password: Default password for login
        token: Pre-existing authentication token
        timeout: Request timeout in seconds
        max_retries: Maximum number of retries for failed requests

    Example:
        ```python
        async with QSOPClient("http://localhost:8000") as client:
            await client.login("admin", "password")
            jobs = await client.get_jobs()
        ```
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        username: str | None = None,
        password: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

        self._username = username
        self._password = password
        self._token: str | None = token
        self._refresh_token_value: str | None = None
        self._token_expires: float = 0

        self._client: httpx.AsyncClient | None = None
        self._on_token_refresh: Callable[[str], None] | None = None

    async def __aenter__(self) -> "QSOPClient":
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Make an API request with retry logic.

        Args:
            method: HTTP method
            path: API endpoint path
            **kwargs: Additional arguments for httpx.request

        Returns:
            Response JSON data

        Raises:
            QSOPClientError: If request fails after retries
        """
        client = await self._ensure_client()

        for attempt in range(self.max_retries):
            try:
                response = await client.request(
                    method,
                    path,
                    headers=self._get_headers(),
                    **kwargs,
                )

                if response.status_code == 401 and self._refresh_token_value:
                    await self._refresh_access_token()
                    continue

                if response.status_code >= 400:
                    try:
                        error = response.json()
                        raise QSOPClientError(
                            message=error.get("detail", error.get("message", "Unknown error"))
                            or "Unknown error",
                            status_code=response.status_code,
                            details=error,
                        )
                    except json.JSONDecodeError:
                        raise QSOPClientError(
                            message=response.text or "Unknown error",
                            status_code=response.status_code,
                        )

                if response.status_code == 204:
                    return {}

                return response.json()

            except httpx.TimeoutException:
                if attempt == self.max_retries - 1:
                    raise QSOPClientError("Request timed out")
                await asyncio.sleep(2**attempt)

            except httpx.RequestError as e:
                if attempt == self.max_retries - 1:
                    raise QSOPClientError(f"Request failed: {e}")
                await asyncio.sleep(2**attempt)

        raise QSOPClientError("Max retries exceeded")

    # Authentication Methods

    async def login(self, username: str, password: str) -> dict[str, Any]:
        """
        Login and obtain access token.

        Args:
            username: Username
            password: Password

        Returns:
            Token response with access_token, refresh_token, expires_in
        """
        response = await self._request(
            "POST",
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )

        self._token = response.get("access_token")
        self._refresh_token_value = response.get("refresh_token")
        self._token_expires = time.time() + response.get("expires_in", 3600)

        return response

    async def logout(self) -> None:
        """Logout and revoke the current token."""
        await self._request("POST", "/api/v1/auth/logout")
        self._token = None
        self._refresh_token_value = None

    async def _refresh_access_token(self) -> None:
        """Refresh the access token using refresh token."""
        if not self._refresh_token_value:
            raise QSOPClientError("No refresh token available")

        response = await self._request(
            "POST",
            "/api/v1/auth/refresh",
            json={"refresh_token": self._refresh_token_value},
        )

        self._token = response.get("access_token")
        self._refresh_token_value = response.get("refresh_token")
        self._token_expires = time.time() + response.get("expires_in", 3600)

        if self._on_token_refresh and self._token:
            self._on_token_refresh(self._token)

    async def get_current_user(self) -> User:
        """Get the currently authenticated user."""
        response = await self._request("GET", "/api/v1/auth/me")
        return User.from_dict(response)

    # Job Methods

    async def submit_job(
        self,
        problem_type: AlgorithmType,
        problem_config: ProblemConfigDict,
        parameters: JobParametersDict | None = None,
        webhook_url: str | None = None,
    ) -> Job:
        """
        Submit a new optimization job.

        Args:
            problem_type: Algorithm type (QAOA, VQE, ANNEALING, GROVER)
            problem_config: Problem configuration dictionary
            parameters: Optional job parameters
            webhook_url: Optional webhook URL for notifications

        Returns:
            Created Job object
        """
        payload: dict[str, Any] = {
            "problem_type": problem_type,
            "problem_config": problem_config,
        }
        if parameters:
            payload["parameters"] = parameters
        if webhook_url:
            payload["webhook_url"] = webhook_url

        response = await self._request("POST", "/api/v1/jobs", json=payload)
        return Job.from_dict(response)

    async def get_job(self, job_id: str) -> Job:
        """
        Get job status by ID.

        Args:
            job_id: Job identifier
        """
        response = await self._request("GET", f"/api/v1/jobs/{job_id}")
        return Job.from_dict(response)

    async def get_jobs(
        self,
        status: JobStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Job]:
        """
        List jobs with optional filtering.

        Args:
            status: Filter by job status
            limit: Maximum number of results
            offset: Result offset for pagination

        Returns:
            List of Job objects
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        response = await self._request("GET", "/api/v1/jobs", params=params)
        items = response.get("items", response)
        return [Job.from_dict(job) for job in items]

    async def cancel_job(self, job_id: str) -> Job:
        """
        Cancel a running job.

        Args:
            job_id: Job identifier
        """
        response = await self._request("POST", f"/api/v1/jobs/{job_id}/cancel")
        return Job.from_dict(response)

    async def get_job_result(self, job_id: str) -> dict[str, Any]:
        """
        Get job result data.

        Args:
            job_id: Job identifier
        """
        return await self._request("GET", f"/api/v1/jobs/{job_id}/result")

    async def wait_for_job(
        self,
        job_id: str,
        timeout: float = 300,
        poll_interval: float = 2.0,
    ) -> Job:
        """
        Wait for job completion.

        Args:
            job_id: Job identifier
            timeout: Maximum wait time in seconds
            poll_interval: Polling interval in seconds

        Returns:
            Completed Job object

        Raises:
            QSOPClientError: If timeout is exceeded
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            job = await self.get_job(job_id)

            if job.status in ("completed", "failed", "cancelled"):
                return job

            await asyncio.sleep(poll_interval)

        raise QSOPClientError(f"Job {job_id} did not complete within {timeout}s")

    # Key Methods

    async def generate_key(
        self,
        key_type: Literal["kem", "signing"] = "kem",
        security_level: int = 3,
    ) -> KeyPair:
        """
        Generate a new PQC key pair.

        Args:
            key_type: Key type (kem for encryption, signing for signatures)
            security_level: NIST security level (1, 3, or 5)
        """
        response = await self._request(
            "POST",
            "/api/v1/auth/keys/generate",
            json={"key_type": key_type, "security_level": security_level},
        )
        return KeyPair.from_dict(response)

    async def get_keys(self) -> list[KeyPair]:
        """List user's keys."""
        response = await self._request("GET", "/api/v1/auth/keys")
        return [KeyPair.from_dict(cast(dict[str, Any], key)) for key in response]

    # Health Methods

    async def health_check(self) -> dict[str, Any]:
        """Check API health status."""
        return await self._request("GET", "/health")

    async def crypto_status(self) -> dict[str, Any]:
        """Check crypto provider status."""
        return await self._request("GET", "/health/crypto")

    # Billing Methods

    async def record_usage(
        self,
        resource_type: str,
        quantity: int,
        metadata: dict[str, Any] | None = None,
    ) -> BillingUsage:
        """Record a usage event for billing."""
        payload: dict[str, Any] = {"resource_type": resource_type, "quantity": quantity}
        if metadata:
            payload["metadata"] = metadata
        response = await self._request("POST", "/api/v1/billing/usage", json=payload)
        return BillingUsage.from_dict(response)

    async def get_usage_summary(self, period: str = "month") -> dict[str, Any]:
        """Get usage summary for billing period."""
        return await self._request(
            "GET", "/api/v1/billing/usage/summary", params={"period": period}
        )

    async def get_pricing(self) -> list[dict[str, Any]]:
        """Get current pricing for all resources."""
        return await self._request("GET", "/api/v1/billing/pricing")

    async def estimate_cost(
        self,
        shots: int = 0,
        jobs: int = 0,
        compute_seconds: int = 0,
    ) -> dict[str, Any]:
        """Estimate cost for a job configuration."""
        return await self._request(
            "POST",
            "/api/v1/billing/estimate",
            json={"shots": shots, "jobs": jobs, "compute_seconds": compute_seconds},
        )

    async def generate_invoice(self, period: str = "month") -> Invoice:
        """Generate an invoice for the billing period."""
        response = await self._request(
            "POST", "/api/v1/billing/invoices/generate", params={"period": period}
        )
        return Invoice.from_dict(response)

    async def get_invoices(self, limit: int = 10) -> list[Invoice]:
        """List invoices."""
        response = await self._request("GET", "/api/v1/billing/invoices", params={"limit": limit})
        return [Invoice.from_dict(inv) for inv in response]

    # Tenant Methods

    async def create_tenant(
        self,
        name: str,
        tier: str = "free",
        admin_email: str = "",
    ) -> Tenant:
        """Create a new tenant."""
        response = await self._request(
            "POST",
            "/api/v1/tenants",
            json={"name": name, "tier": tier, "admin_email": admin_email},
        )
        return Tenant.from_dict(response)

    async def get_tenant(self, tenant_id: str) -> Tenant:
        """Get tenant details."""
        response = await self._request("GET", f"/api/v1/tenants/{tenant_id}")
        return Tenant.from_dict(response)

    async def list_tenants(self, limit: int = 20) -> list[Tenant]:
        """List tenants for current user."""
        response = await self._request("GET", "/api/v1/tenants", params={"limit": limit})
        return [Tenant.from_dict(t) for t in response]

    async def get_tenant_quotas(self, tenant_id: str) -> list[dict[str, Any]]:
        """Get tenant quota usage."""
        return await self._request("GET", f"/api/v1/tenants/{tenant_id}/quota")

    async def get_tenant_usage(self, tenant_id: str, period: str = "month") -> dict[str, Any]:
        """Get tenant usage statistics."""
        return await self._request(
            "GET", f"/api/v1/tenants/{tenant_id}/usage", params={"period": period}
        )

    # Marketplace Methods

    async def search_algorithms(
        self,
        query: str | None = None,
        category: str | None = None,
        min_rating: float | None = None,
        limit: int = 20,
    ) -> list[Algorithm]:
        """Search algorithms in marketplace."""
        params: dict[str, Any] = {"limit": limit}
        if query:
            params["q"] = query
        if category:
            params["category"] = category
        if min_rating:
            params["min_rating"] = min_rating
        response = await self._request("GET", "/api/v1/marketplace/search", params=params)
        return [Algorithm.from_dict(a) for a in response]

    async def get_algorithm(self, algorithm_id: str) -> Algorithm:
        """Get algorithm details."""
        response = await self._request("GET", f"/api/v1/marketplace/{algorithm_id}")
        return Algorithm.from_dict(response)

    async def purchase_algorithm(self, algorithm_id: str) -> dict[str, Any]:
        """Purchase an algorithm."""
        return await self._request("POST", f"/api/v1/marketplace/{algorithm_id}/purchase")

    async def get_user_purchases(self) -> list[dict[str, Any]]:
        """Get user's purchased algorithms."""
        return await self._request("GET", "/api/v1/marketplace/user/purchases")

    # Federation Methods

    async def get_federation_status(self) -> dict[str, Any]:
        """Get overall federation status."""
        return await self._request("GET", "/api/v1/federation/status")

    async def list_regions(self, provider: str | None = None) -> list[dict[str, Any]]:
        """List all federation regions."""
        params = {}
        if provider:
            params["provider"] = provider
        return await self._request("GET", "/api/v1/federation/regions", params=params)

    async def route_job(
        self,
        shots: int,
        preferred_provider: str | None = None,
        max_cost: float | None = None,
    ) -> dict[str, Any]:
        """Get routing decision for a job."""
        payload: dict[str, Any] = {
            "shots": shots,
            "job_type": "optimization",
            "algorithm": "QAOA",
            "num_qubits": 4,
        }
        if preferred_provider:
            payload["preferred_provider"] = preferred_provider
        if max_cost:
            payload["max_cost"] = max_cost
        return await self._request("POST", "/api/v1/federation/route", json=payload)

    # Circuit Visualization Methods

    async def generate_circuit(
        self,
        num_qubits: int = 4,
        depth: int = 3,
    ) -> dict[str, Any]:
        """Generate a sample quantum circuit."""
        return await self._request(
            "POST",
            "/api/v1/circuits/circuits/generate",
            params={"num_qubits": num_qubits, "depth": depth},
        )

    async def execute_circuit(self, circuit_id: str, shots: int = 1024) -> dict[str, Any]:
        """Execute a circuit."""
        return await self._request(
            "POST",
            f"/api/v1/circuits/circuits/{circuit_id}/execute",
            params={"shots": shots},
        )

    async def get_circuit_execution(self, execution_id: str) -> dict[str, Any]:
        """Get execution status."""
        return await self._request("GET", f"/api/v1/circuits/executions/{execution_id}")

    # Security Methods

    async def get_quantum_encryption_status(self) -> dict[str, Any]:
        """Get quantum-safe encryption status."""
        return await self._request("GET", "/api/v1/security/quantum-encryption/status")

    async def encrypt_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Encrypt data with ML-KEM wrapped AES."""
        return await self._request("POST", "/api/v1/security/quantum-encryption/encrypt", json=data)

    async def decrypt_data(self, ciphertext: str) -> dict[str, Any]:
        """Decrypt data encrypted with ML-KEM wrapped AES."""
        return await self._request(
            "POST",
            "/api/v1/security/quantum-encryption/decrypt",
            params={"ciphertext": ciphertext},
        )

    async def get_audit_logs(self, limit: int = 100) -> dict[str, Any]:
        """Get audit logs."""
        return await self._request("GET", "/api/v1/security/audit/logs", params={"limit": limit})

    # Performance Methods

    async def get_performance_metrics(self) -> dict[str, Any]:
        """Get performance metrics."""
        return await self._request("GET", "/api/v1/performance/metrics")

    async def get_query_stats(self) -> dict[str, Any]:
        """Get query performance statistics."""
        return await self._request("GET", "/api/v1/performance/queries")


class SyncQSOPClient:
    """
    Synchronous wrapper for QSOPClient.

    Provides a synchronous interface for applications that don't use async.

    Example:
        ```python
        with SyncQSOPClient("http://localhost:8000") as client:
            client.login("admin", "password")
            job = client.submit_job(...)
        ```
    """

    def __init__(self, **kwargs: Any):
        self._async_client = QSOPClient(**kwargs)

    def __enter__(self) -> "SyncQSOPClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        asyncio.run(self._async_client.close())

    def _run(self, coro: Any) -> Any:
        return asyncio.run(coro)

    def login(self, username: str, password: str) -> dict[str, Any]:
        return self._run(self._async_client.login(username, password))

    def logout(self) -> None:
        return self._run(self._async_client.logout())

    def get_current_user(self) -> User:
        return self._run(self._async_client.get_current_user())

    def submit_job(
        self,
        problem_type: AlgorithmType,
        problem_config: ProblemConfigDict,
        parameters: JobParametersDict | None = None,
        webhook_url: str | None = None,
    ) -> Job:
        return self._run(
            self._async_client.submit_job(problem_type, problem_config, parameters, webhook_url)
        )

    def get_job(self, job_id: str) -> Job:
        return self._run(self._async_client.get_job(job_id))

    def get_jobs(
        self,
        status: JobStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Job]:
        return self._run(self._async_client.get_jobs(status, limit, offset))

    def cancel_job(self, job_id: str) -> Job:
        return self._run(self._async_client.cancel_job(job_id))

    def get_job_result(self, job_id: str) -> dict[str, Any]:
        return self._run(self._async_client.get_job_result(job_id))

    def wait_for_job(self, job_id: str, timeout: float = 300, poll_interval: float = 2.0) -> Job:
        return self._run(self._async_client.wait_for_job(job_id, timeout, poll_interval))

    def generate_key(
        self, key_type: Literal["kem", "signing"] = "kem", security_level: int = 3
    ) -> KeyPair:
        return self._run(self._async_client.generate_key(key_type, security_level))

    def get_keys(self) -> list[KeyPair]:
        return self._run(self._async_client.get_keys())

    def health_check(self) -> dict[str, Any]:
        return self._run(self._async_client.health_check())

    def crypto_status(self) -> dict[str, Any]:
        return self._run(self._async_client.crypto_status())

    # Billing Methods

    def record_usage(
        self, resource_type: str, quantity: int, metadata: dict[str, Any] | None = None
    ) -> BillingUsage:
        return self._run(self._async_client.record_usage(resource_type, quantity, metadata))

    def get_usage_summary(self, period: str = "month") -> dict[str, Any]:
        return self._run(self._async_client.get_usage_summary(period))

    def get_pricing(self) -> list[dict[str, Any]]:
        return self._run(self._async_client.get_pricing())

    def estimate_cost(
        self, shots: int = 0, jobs: int = 0, compute_seconds: int = 0
    ) -> dict[str, Any]:
        return self._run(self._async_client.estimate_cost(shots, jobs, compute_seconds))

    def generate_invoice(self, period: str = "month") -> Invoice:
        return self._run(self._async_client.generate_invoice(period))

    def get_invoices(self, limit: int = 10) -> list[Invoice]:
        return self._run(self._async_client.get_invoices(limit))

    # Tenant Methods

    def create_tenant(self, name: str, tier: str = "free", admin_email: str = "") -> Tenant:
        return self._run(self._async_client.create_tenant(name, tier, admin_email))

    def get_tenant(self, tenant_id: str) -> Tenant:
        return self._run(self._async_client.get_tenant(tenant_id))

    def list_tenants(self, limit: int = 20) -> list[Tenant]:
        return self._run(self._async_client.list_tenants(limit))

    def get_tenant_quotas(self, tenant_id: str) -> list[dict[str, Any]]:
        return self._run(self._async_client.get_tenant_quotas(tenant_id))

    def get_tenant_usage(self, tenant_id: str, period: str = "month") -> dict[str, Any]:
        return self._run(self._async_client.get_tenant_usage(tenant_id, period))

    # Marketplace Methods

    def search_algorithms(
        self,
        query: str | None = None,
        category: str | None = None,
        min_rating: float | None = None,
        limit: int = 20,
    ) -> list[Algorithm]:
        return self._run(self._async_client.search_algorithms(query, category, min_rating, limit))

    def get_algorithm(self, algorithm_id: str) -> Algorithm:
        return self._run(self._async_client.get_algorithm(algorithm_id))

    def purchase_algorithm(self, algorithm_id: str) -> dict[str, Any]:
        return self._run(self._async_client.purchase_algorithm(algorithm_id))

    def get_user_purchases(self) -> list[dict[str, Any]]:
        return self._run(self._async_client.get_user_purchases())

    # Federation Methods

    def get_federation_status(self) -> dict[str, Any]:
        return self._run(self._async_client.get_federation_status())

    def list_regions(self, provider: str | None = None) -> list[dict[str, Any]]:
        return self._run(self._async_client.list_regions(provider))

    def route_job(
        self, shots: int, preferred_provider: str | None = None, max_cost: float | None = None
    ) -> dict[str, Any]:
        return self._run(self._async_client.route_job(shots, preferred_provider, max_cost))

    # Circuit Methods

    def generate_circuit(self, num_qubits: int = 4, depth: int = 3) -> dict[str, Any]:
        return self._run(self._async_client.generate_circuit(num_qubits, depth))

    def execute_circuit(self, circuit_id: str, shots: int = 1024) -> dict[str, Any]:
        return self._run(self._async_client.execute_circuit(circuit_id, shots))

    def get_circuit_execution(self, execution_id: str) -> dict[str, Any]:
        return self._run(self._async_client.get_circuit_execution(execution_id))

    # Security Methods

    def get_quantum_encryption_status(self) -> dict[str, Any]:
        return self._run(self._async_client.get_quantum_encryption_status())

    def encrypt_data(self, data: dict[str, Any]) -> dict[str, Any]:
        return self._run(self._async_client.encrypt_data(data))

    def decrypt_data(self, ciphertext: str) -> dict[str, Any]:
        return self._run(self._async_client.decrypt_data(ciphertext))

    def get_audit_logs(self, limit: int = 100) -> dict[str, Any]:
        return self._run(self._async_client.get_audit_logs(limit))

    # Performance Methods

    def get_performance_metrics(self) -> dict[str, Any]:
        return self._run(self._async_client.get_performance_metrics())

    def get_query_stats(self) -> dict[str, Any]:
        return self._run(self._async_client.get_query_stats())

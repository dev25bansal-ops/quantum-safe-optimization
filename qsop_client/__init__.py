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

__version__ = "0.2.0"
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

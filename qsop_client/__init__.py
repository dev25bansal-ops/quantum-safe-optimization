"""
QSOP Python SDK Client.

A client library for interacting with the QSOP API.

Usage:
    from qsop_client import QSOPClient

    async with QSOPClient(base_url="http://localhost:8000") as client:
        # Login
        await client.login("admin", "password")

        # Submit a job
        job = await client.submit_job(
            problem_type="QAOA",
            problem_config={"edges": [[0, 1], [1, 2]]}
        )

        # Get job status
        status = await client.get_job(job.id)

        # Get job results
        if status.status == "completed":
            result = await client.get_job_result(job.id)
"""

import asyncio
import base64
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

import httpx


@dataclass
class Job:
    """Job representation."""

    id: str
    problem_type: str
    status: str
    created_at: str
    user_id: str | None = None
    progress: float = 0.0
    result: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class KeyPair:
    """PQC Key pair representation."""

    key_id: str
    public_key: str
    key_type: str
    algorithm: str
    expires_at: str


@dataclass
class User:
    """User representation."""

    user_id: str
    username: str
    email: str | None
    roles: list[str]
    created_at: str


class QSOPClientError(Exception):
    """Client error."""

    def __init__(self, message: str, status_code: int | None = None, details: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class QSOPClient:
    """
    Async client for QSOP API.

    Features:
    - Automatic authentication
    - Token refresh
    - Retry logic
    - WebSocket support
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
        self._token = token
        self._refresh_token: str | None = None
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
        **kwargs,
    ) -> dict[str, Any]:
        """Make an API request with retry logic."""
        client = await self._ensure_client()

        for attempt in range(self.max_retries):
            try:
                response = await client.request(
                    method,
                    path,
                    headers=self._get_headers(),
                    **kwargs,
                )

                if response.status_code == 401 and self._refresh_token:
                    await self._refresh_access_token()
                    continue

                if response.status_code >= 400:
                    try:
                        error = response.json()
                        raise QSOPClientError(
                            message=error.get("message", error.get("detail", "Unknown error")),
                            status_code=response.status_code,
                            details=error,
                        )
                    except json.JSONDecodeError:
                        raise QSOPClientError(
                            message=response.text,
                            status_code=response.status_code,
                        )

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

    # Authentication

    async def login(self, username: str, password: str) -> dict[str, Any]:
        """Login and obtain access token."""
        response = await self._request(
            "POST",
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )

        self._token = response.get("access_token")
        self._refresh_token = response.get("refresh_token")
        self._token_expires = time.time() + response.get("expires_in", 3600)

        return response

    async def logout(self) -> None:
        """Logout and revoke token."""
        await self._request("POST", "/api/v1/auth/logout")
        self._token = None
        self._refresh_token = None

    async def _refresh_access_token(self) -> None:
        """Refresh the access token."""
        if not self._refresh_token:
            raise QSOPClientError("No refresh token available")

        response = await self._request(
            "POST",
            "/api/v1/auth/refresh",
            json={"refresh_token": self._refresh_token},
        )

        self._token = response.get("access_token")
        self._refresh_token = response.get("refresh_token")
        self._token_expires = time.time() + response.get("expires_in", 3600)

        if self._on_token_refresh:
            self._on_token_refresh(self._token)

    async def get_current_user(self) -> User:
        """Get current authenticated user."""
        response = await self._request("GET", "/api/v1/auth/me")
        return User(**response)

    # Jobs

    async def submit_job(
        self,
        problem_type: str,
        problem_config: dict[str, Any],
        parameters: dict[str, Any] | None = None,
        webhook_url: str | None = None,
    ) -> Job:
        """Submit a new optimization job."""
        payload = {
            "problem_type": problem_type,
            "problem_config": problem_config,
        }
        if parameters:
            payload["parameters"] = parameters
        if webhook_url:
            payload["webhook_url"] = webhook_url

        response = await self._request("POST", "/api/v1/jobs", json=payload)
        return Job(**response)

    async def get_job(self, job_id: str) -> Job:
        """Get job status."""
        response = await self._request("GET", f"/api/v1/jobs/{job_id}")
        return Job(**response)

    async def get_jobs(
        self,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Job]:
        """List jobs."""
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        response = await self._request("GET", "/api/v1/jobs", params=params)
        return [Job(**job) for job in response.get("items", response)]

    async def cancel_job(self, job_id: str) -> Job:
        """Cancel a job."""
        response = await self._request("POST", f"/api/v1/jobs/{job_id}/cancel")
        return Job(**response)

    async def get_job_result(self, job_id: str) -> dict[str, Any]:
        """Get job result."""
        return await self._request("GET", f"/api/v1/jobs/{job_id}/result")

    async def wait_for_job(
        self,
        job_id: str,
        timeout: float = 300,
        poll_interval: float = 2.0,
    ) -> Job:
        """Wait for job completion."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            job = await self.get_job(job_id)

            if job.status in ("completed", "failed", "cancelled"):
                return job

            await asyncio.sleep(poll_interval)

        raise QSOPClientError(f"Job {job_id} did not complete within {timeout}s")

    # Keys

    async def generate_key(
        self,
        key_type: str = "kem",
        security_level: int = 3,
    ) -> KeyPair:
        """Generate a new PQC key pair."""
        response = await self._request(
            "POST",
            "/api/v1/auth/keys/generate",
            json={"key_type": key_type, "security_level": security_level},
        )
        return KeyPair(**response)

    async def get_keys(self) -> list[KeyPair]:
        """List user's keys."""
        response = await self._request("GET", "/api/v1/auth/keys")
        return [KeyPair(**key) for key in response]

    # Health

    async def health_check(self) -> dict[str, Any]:
        """Check API health."""
        return await self._request("GET", "/health")

    async def crypto_status(self) -> dict[str, Any]:
        """Check crypto provider status."""
        return await self._request("GET", "/health/crypto")


class SyncQSOPClient:
    """Synchronous wrapper for QSOPClient."""

    def __init__(self, **kwargs):
        self._async_client = QSOPClient(**kwargs)

    def __enter__(self) -> "SyncQSOPClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        asyncio.run(self._async_client.close())

    def _run(self, coro):
        return asyncio.run(coro)

    def login(self, username: str, password: str) -> dict[str, Any]:
        return self._run(self._async_client.login(username, password))

    def submit_job(self, **kwargs) -> Job:
        return self._run(self._async_client.submit_job(**kwargs))

    def get_job(self, job_id: str) -> Job:
        return self._run(self._async_client.get_job(job_id))

    def wait_for_job(self, job_id: str, **kwargs) -> Job:
        return self._run(self._async_client.wait_for_job(job_id, **kwargs))

    def get_job_result(self, job_id: str) -> dict[str, Any]:
        return self._run(self._async_client.get_job_result(job_id))

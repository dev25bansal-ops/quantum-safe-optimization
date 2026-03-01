"""
QuantumSafe Client - Main client implementations.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx

from quantum_safe_client.exceptions import (
    APIError,
    AuthenticationError,
    JobNotFoundError,
    RateLimitError,
    ValidationError,
)
from quantum_safe_client.models import (
    CostEstimate,
    Job,
    JobStatus,
    QuantumBackend,
)


class AsyncQuantumSafeClient:
    """
    Async client for the QuantumSafe Optimization Platform.

    Example:
        ```python
        async with AsyncQuantumSafeClient(
            base_url="https://api.quantumsafe.io",
            api_key="your-api-key"
        ) as client:
            job = await client.submit_qaoa_job(
                problem={"Q": [[1, -1], [-1, 1]]},
                backend="ibm_quantum"
            )
            result = await client.wait_for_job(job.id)
        ```
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
        verify_ssl: bool = True,
    ):
        """
        Initialize the async client.

        Args:
            base_url: Base URL of the QuantumSafe API
            api_key: API key for authentication (alternative to token)
            token: JWT token for authentication
            timeout: Request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.token = token
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> AsyncQuantumSafeClient:
        """Enter async context."""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        await self.close()

    async def _ensure_client(self):
        """Ensure HTTP client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with authentication."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        elif self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request."""
        await self._ensure_client()

        try:
            response = await self._client.request(
                method=method,
                url=endpoint,
                json=data,
                params=params,
                headers=self._get_headers(),
            )
        except httpx.ConnectError as e:
            raise APIError(f"Connection failed: {e}") from e
        except httpx.TimeoutException as e:
            raise APIError(f"Request timed out: {e}") from e

        return self._handle_response(response)

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle API response and raise appropriate exceptions."""
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 201:
            return response.json()
        elif response.status_code == 401:
            raise AuthenticationError("Invalid or expired authentication")
        elif response.status_code == 404:
            raise JobNotFoundError("Resource not found")
        elif response.status_code == 422:
            detail = response.json().get("detail", "Validation error")
            raise ValidationError(f"Validation error: {detail}")
        elif response.status_code == 429:
            raise RateLimitError("Rate limit exceeded")
        else:
            raise APIError(f"API error: {response.status_code} - {response.text}")

    # ==================== Authentication ====================

    async def login(self, username: str, password: str) -> str:
        """
        Authenticate and get a JWT token.

        Args:
            username: User's username
            password: User's password

        Returns:
            JWT token string
        """
        response = await self._request(
            "POST",
            "/auth/login",
            data={"username": username, "password": password},
        )
        self.token = response.get("access_token")
        return self.token

    async def refresh_token(self) -> str:
        """
        Refresh the JWT token.

        Returns:
            New JWT token string
        """
        response = await self._request("POST", "/auth/refresh")
        self.token = response.get("access_token")
        return self.token

    # ==================== Job Submission ====================

    async def submit_qaoa_job(
        self,
        problem: dict[str, Any],
        backend: str = "simulator",
        p: int = 1,
        shots: int = 1000,
        optimizer: str = "COBYLA",
        webhook_url: str | None = None,
        **kwargs,
    ) -> Job:
        """
        Submit a QAOA optimization job.

        Args:
            problem: QUBO problem definition (Q matrix)
            backend: Quantum backend to use
            p: Number of QAOA layers
            shots: Number of measurement shots
            optimizer: Classical optimizer
            webhook_url: URL for completion webhook

        Returns:
            Job object with ID and initial status
        """
        data = {
            "job_type": "qaoa",
            "problem": problem,
            "backend": backend,
            "config": {
                "p": p,
                "shots": shots,
                "optimizer": optimizer,
                **kwargs,
            },
        }
        if webhook_url:
            data["webhook_url"] = webhook_url

        response = await self._request("POST", "/jobs/submit", data=data)
        return Job.from_dict(response)

    async def submit_vqe_job(
        self,
        hamiltonian: dict[str, Any],
        ansatz: str = "uccsd",
        backend: str = "simulator",
        shots: int = 1000,
        optimizer: str = "COBYLA",
        webhook_url: str | None = None,
        **kwargs,
    ) -> Job:
        """
        Submit a VQE optimization job.

        Args:
            hamiltonian: Hamiltonian definition
            ansatz: Variational ansatz type
            backend: Quantum backend to use
            shots: Number of measurement shots
            optimizer: Classical optimizer
            webhook_url: URL for completion webhook

        Returns:
            Job object with ID and initial status
        """
        data = {
            "job_type": "vqe",
            "hamiltonian": hamiltonian,
            "backend": backend,
            "config": {
                "ansatz": ansatz,
                "shots": shots,
                "optimizer": optimizer,
                **kwargs,
            },
        }
        if webhook_url:
            data["webhook_url"] = webhook_url

        response = await self._request("POST", "/jobs/submit", data=data)
        return Job.from_dict(response)

    async def submit_annealing_job(
        self,
        problem: dict[str, Any],
        backend: str = "dwave",
        num_reads: int = 1000,
        annealing_time: int = 20,
        webhook_url: str | None = None,
        **kwargs,
    ) -> Job:
        """
        Submit a quantum annealing job.

        Args:
            problem: QUBO/Ising problem definition
            backend: Annealing backend (dwave, simulator)
            num_reads: Number of annealing reads
            annealing_time: Annealing time in microseconds
            webhook_url: URL for completion webhook

        Returns:
            Job object with ID and initial status
        """
        data = {
            "job_type": "annealing",
            "problem": problem,
            "backend": backend,
            "config": {
                "num_reads": num_reads,
                "annealing_time": annealing_time,
                **kwargs,
            },
        }
        if webhook_url:
            data["webhook_url"] = webhook_url

        response = await self._request("POST", "/jobs/submit", data=data)
        return Job.from_dict(response)

    # ==================== Job Management ====================

    async def get_job(self, job_id: str) -> Job:
        """
        Get job details by ID.

        Args:
            job_id: The job ID

        Returns:
            Job object with current status and results
        """
        response = await self._request("GET", f"/jobs/{job_id}")
        return Job.from_dict(response)

    async def list_jobs(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Job]:
        """
        List jobs with optional filtering.

        Args:
            status: Filter by job status
            limit: Maximum number of jobs to return
            offset: Pagination offset

        Returns:
            List of Job objects
        """
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status

        response = await self._request("GET", "/jobs", params=params)
        jobs = response.get("jobs", [])
        return [Job.from_dict(j) for j in jobs]

    async def cancel_job(self, job_id: str, reason: str | None = None) -> Job:
        """
        Cancel a running job.

        Args:
            job_id: The job ID to cancel
            reason: Optional cancellation reason

        Returns:
            Updated Job object
        """
        data = {}
        if reason:
            data["reason"] = reason

        response = await self._request("POST", f"/jobs/{job_id}/cancel", data=data)
        return Job.from_dict(response)

    async def delete_job(self, job_id: str) -> bool:
        """
        Delete a job.

        Args:
            job_id: The job ID to delete

        Returns:
            True if deleted successfully
        """
        await self._request("DELETE", f"/jobs/{job_id}")
        return True

    async def wait_for_job(
        self,
        job_id: str,
        poll_interval: float = 2.0,
        timeout: float | None = None,
    ) -> Job:
        """
        Wait for a job to complete.

        Args:
            job_id: The job ID to wait for
            poll_interval: Seconds between status checks
            timeout: Maximum time to wait (None for no timeout)

        Returns:
            Completed Job object

        Raises:
            TimeoutError: If timeout is reached
        """
        start_time = datetime.now()

        while True:
            job = await self.get_job(job_id)

            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                return job

            if timeout:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed >= timeout:
                    raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")

            await asyncio.sleep(poll_interval)

    # ==================== Cost Estimation ====================

    async def estimate_cost(
        self,
        job_type: str,
        backend: str,
        shots: int = 1000,
        circuit_depth: int | None = None,
        num_qubits: int | None = None,
        problem_size: int | None = None,
    ) -> CostEstimate:
        """
        Estimate the cost of a quantum job.

        Args:
            job_type: Type of job (qaoa, vqe, annealing)
            backend: Target quantum backend
            shots: Number of shots/reads
            circuit_depth: Estimated circuit depth
            num_qubits: Number of qubits needed
            problem_size: Size of the optimization problem

        Returns:
            CostEstimate object with pricing details
        """
        data = {
            "job_type": job_type,
            "backend": backend,
            "shots": shots,
        }
        if circuit_depth:
            data["circuit_depth"] = circuit_depth
        if num_qubits:
            data["num_qubits"] = num_qubits
        if problem_size:
            data["problem_size"] = problem_size

        response = await self._request("POST", "/costs/estimate", data=data)
        return CostEstimate.from_dict(response)

    # ==================== Backends ====================

    async def list_backends(self) -> list[QuantumBackend]:
        """
        List available quantum backends.

        Returns:
            List of QuantumBackend objects
        """
        response = await self._request("GET", "/backends")
        backends = response.get("backends", [])
        return [QuantumBackend.from_dict(b) for b in backends]

    async def get_backend_status(self, backend_name: str) -> dict[str, Any]:
        """
        Get status of a specific backend.

        Args:
            backend_name: Name of the backend

        Returns:
            Backend status information
        """
        return await self._request("GET", f"/backends/{backend_name}/status")


class QuantumSafeClient:
    """
    Synchronous client for the QuantumSafe Optimization Platform.

    Wraps AsyncQuantumSafeClient for synchronous usage.

    Example:
        ```python
        with QuantumSafeClient(
            base_url="https://api.quantumsafe.io",
            api_key="your-api-key"
        ) as client:
            job = client.submit_qaoa_job(
                problem={"Q": [[1, -1], [-1, 1]]},
                backend="ibm_quantum"
            )
            result = client.wait_for_job(job.id, timeout=300)
        ```
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
        verify_ssl: bool = True,
    ):
        """
        Initialize the sync client.

        Args:
            base_url: Base URL of the QuantumSafe API
            api_key: API key for authentication
            token: JWT token for authentication
            timeout: Request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
        """
        self._async_client = AsyncQuantumSafeClient(
            base_url=base_url,
            api_key=api_key,
            token=token,
            timeout=timeout,
            verify_ssl=verify_ssl,
        )
        self._loop: asyncio.AbstractEventLoop | None = None

    def __enter__(self) -> QuantumSafeClient:
        """Enter sync context."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit sync context."""
        self.close()

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create event loop."""
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            if self._loop is None or self._loop.is_closed():
                self._loop = asyncio.new_event_loop()
            return self._loop

    def _run(self, coro):
        """Run coroutine synchronously."""
        loop = self._get_loop()
        try:
            return loop.run_until_complete(coro)
        except RuntimeError:
            # If we're in an async context, create a new loop
            new_loop = asyncio.new_event_loop()
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()

    def close(self):
        """Close the client."""
        self._run(self._async_client.close())
        if self._loop and not self._loop.is_closed():
            self._loop.close()

    # ==================== Authentication ====================

    def login(self, username: str, password: str) -> str:
        """Authenticate and get a JWT token."""
        return self._run(self._async_client.login(username, password))

    def refresh_token(self) -> str:
        """Refresh the JWT token."""
        return self._run(self._async_client.refresh_token())

    # ==================== Job Submission ====================

    def submit_qaoa_job(
        self,
        problem: dict[str, Any],
        backend: str = "simulator",
        p: int = 1,
        shots: int = 1000,
        optimizer: str = "COBYLA",
        webhook_url: str | None = None,
        **kwargs,
    ) -> Job:
        """Submit a QAOA optimization job."""
        return self._run(
            self._async_client.submit_qaoa_job(
                problem=problem,
                backend=backend,
                p=p,
                shots=shots,
                optimizer=optimizer,
                webhook_url=webhook_url,
                **kwargs,
            )
        )

    def submit_vqe_job(
        self,
        hamiltonian: dict[str, Any],
        ansatz: str = "uccsd",
        backend: str = "simulator",
        shots: int = 1000,
        optimizer: str = "COBYLA",
        webhook_url: str | None = None,
        **kwargs,
    ) -> Job:
        """Submit a VQE optimization job."""
        return self._run(
            self._async_client.submit_vqe_job(
                hamiltonian=hamiltonian,
                ansatz=ansatz,
                backend=backend,
                shots=shots,
                optimizer=optimizer,
                webhook_url=webhook_url,
                **kwargs,
            )
        )

    def submit_annealing_job(
        self,
        problem: dict[str, Any],
        backend: str = "dwave",
        num_reads: int = 1000,
        annealing_time: int = 20,
        webhook_url: str | None = None,
        **kwargs,
    ) -> Job:
        """Submit a quantum annealing job."""
        return self._run(
            self._async_client.submit_annealing_job(
                problem=problem,
                backend=backend,
                num_reads=num_reads,
                annealing_time=annealing_time,
                webhook_url=webhook_url,
                **kwargs,
            )
        )

    # ==================== Job Management ====================

    def get_job(self, job_id: str) -> Job:
        """Get job details by ID."""
        return self._run(self._async_client.get_job(job_id))

    def list_jobs(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Job]:
        """List jobs with optional filtering."""
        return self._run(self._async_client.list_jobs(status=status, limit=limit, offset=offset))

    def cancel_job(self, job_id: str, reason: str | None = None) -> Job:
        """Cancel a running job."""
        return self._run(self._async_client.cancel_job(job_id, reason))

    def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        return self._run(self._async_client.delete_job(job_id))

    def wait_for_job(
        self,
        job_id: str,
        poll_interval: float = 2.0,
        timeout: float | None = None,
    ) -> Job:
        """Wait for a job to complete."""
        return self._run(self._async_client.wait_for_job(job_id, poll_interval, timeout))

    # ==================== Cost Estimation ====================

    def estimate_cost(
        self,
        job_type: str,
        backend: str,
        shots: int = 1000,
        circuit_depth: int | None = None,
        num_qubits: int | None = None,
        problem_size: int | None = None,
    ) -> CostEstimate:
        """Estimate the cost of a quantum job."""
        return self._run(
            self._async_client.estimate_cost(
                job_type=job_type,
                backend=backend,
                shots=shots,
                circuit_depth=circuit_depth,
                num_qubits=num_qubits,
                problem_size=problem_size,
            )
        )

    # ==================== Backends ====================

    def list_backends(self) -> list[QuantumBackend]:
        """List available quantum backends."""
        return self._run(self._async_client.list_backends())

    def get_backend_status(self, backend_name: str) -> dict[str, Any]:
        """Get status of a specific backend."""
        return self._run(self._async_client.get_backend_status(backend_name))

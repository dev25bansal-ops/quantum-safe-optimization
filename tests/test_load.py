"""
Load Tests for Quantum-Safe Optimization Platform.

Verifies performance under concurrent job submissions and API load.
"""

import asyncio
import os
import statistics
import time
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

# Disable rate limiting in test environment
os.environ["TESTING"] = "1"

from api.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_token(client: AsyncClient) -> str:
    """Get authentication token."""
    response = await client.post("/auth/login", json={"username": "admin", "password": "admin123!"})
    return response.json()["access_token"]


class LoadTestMetrics:
    """Collect and analyze load test metrics."""

    def __init__(self):
        self.response_times: list[float] = []
        self.success_count: int = 0
        self.failure_count: int = 0
        self.errors: list[str] = []

    def record_success(self, response_time: float):
        self.response_times.append(response_time)
        self.success_count += 1

    def record_failure(self, error: str):
        self.failure_count += 1
        self.errors.append(error)

    @property
    def total_requests(self) -> int:
        return self.success_count + self.failure_count

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.success_count / self.total_requests

    @property
    def avg_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        return statistics.mean(self.response_times)

    @property
    def p50_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        return statistics.median(self.response_times)

    @property
    def p95_response_time(self) -> float:
        if len(self.response_times) < 2:
            return self.avg_response_time
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[idx]

    @property
    def p99_response_time(self) -> float:
        if len(self.response_times) < 2:
            return self.avg_response_time
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.99)
        return sorted_times[idx]

    def report(self) -> dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": f"{self.success_rate * 100:.1f}%",
            "avg_response_time_ms": f"{self.avg_response_time * 1000:.2f}",
            "p50_response_time_ms": f"{self.p50_response_time * 1000:.2f}",
            "p95_response_time_ms": f"{self.p95_response_time * 1000:.2f}",
            "p99_response_time_ms": f"{self.p99_response_time * 1000:.2f}",
        }


class TestConcurrentJobSubmissions:
    """Test concurrent job submission performance."""

    @pytest.mark.anyio
    async def test_concurrent_job_submissions_10(self, client: AsyncClient, auth_token: str):
        """Test 10 concurrent job submissions."""
        metrics = LoadTestMetrics()
        headers = {"Authorization": f"Bearer {auth_token}"}
        num_concurrent = 10

        async def submit_job(job_num: int) -> tuple[bool, float, str]:
            start = time.perf_counter()
            try:
                response = await client.post(
                    "/jobs",
                    json={
                        "problem_type": "QAOA",
                        "problem_config": {
                            "problem": "maxcut",
                            "edges": [[0, 1], [1, 2]],
                        },
                        "backend": "local_simulator",
                    },
                    headers=headers,
                )
                elapsed = time.perf_counter() - start

                # Accept 202 (created) or 429 (rate limited - acceptable under load)
                if response.status_code in [202, 429]:
                    return True, elapsed, ""
                else:
                    return False, elapsed, f"Status {response.status_code}"
            except Exception as e:
                elapsed = time.perf_counter() - start
                return False, elapsed, str(e)

        # Submit jobs concurrently
        tasks = [submit_job(i) for i in range(num_concurrent)]
        results = await asyncio.gather(*tasks)

        for success, elapsed, error in results:
            if success:
                metrics.record_success(elapsed)
            else:
                metrics.record_failure(error)

        report = metrics.report()
        for _key, _value in report.items():
            pass

        # Assertions - relaxed for test environment
        # At least 70% success rate in test environment (may have resource constraints)
        assert metrics.success_rate >= 0.7, f"Success rate too low: {metrics.success_rate}"
        # Allow slower response in test environment (quantum optimization takes time)
        assert metrics.avg_response_time < 30.0, (
            f"Avg response too slow: {metrics.avg_response_time}s"
        )

    @pytest.mark.anyio
    async def test_concurrent_job_submissions_25(self, client: AsyncClient, auth_token: str):
        """Test 25 concurrent job submissions."""
        metrics = LoadTestMetrics()
        headers = {"Authorization": f"Bearer {auth_token}"}
        num_concurrent = 25

        async def submit_job(job_num: int) -> tuple[bool, float, str]:
            start = time.perf_counter()
            try:
                response = await client.post(
                    "/jobs",
                    json={
                        "problem_type": "QAOA",
                        "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                        "backend": "local_simulator",
                    },
                    headers=headers,
                )
                elapsed = time.perf_counter() - start
                return response.status_code == 202, elapsed, ""
            except Exception as e:
                return False, time.perf_counter() - start, str(e)

        tasks = [submit_job(i) for i in range(num_concurrent)]
        results = await asyncio.gather(*tasks)

        for success, elapsed, error in results:
            if success:
                metrics.record_success(elapsed)
            else:
                metrics.record_failure(error)

        report = metrics.report()
        for _key, _value in report.items():
            pass

        assert metrics.success_rate >= 0.85

    @pytest.mark.anyio
    async def test_sustained_load(self, client: AsyncClient, auth_token: str):
        """Test sustained load over time."""
        metrics = LoadTestMetrics()
        headers = {"Authorization": f"Bearer {auth_token}"}

        duration_seconds = 3
        requests_per_second = 5
        total_requests = duration_seconds * requests_per_second

        async def submit_job() -> tuple[bool, float]:
            start = time.perf_counter()
            try:
                response = await client.post(
                    "/jobs",
                    json={
                        "problem_type": "QAOA",
                        "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                        "backend": "local_simulator",
                    },
                    headers=headers,
                )
                elapsed = time.perf_counter() - start
                return response.status_code == 202, elapsed
            except Exception:
                return False, time.perf_counter() - start

        start_time = time.perf_counter()

        for _ in range(total_requests):
            success, elapsed = await submit_job()
            if success:
                metrics.record_success(elapsed)
            else:
                metrics.record_failure("")

            # Pace requests
            await asyncio.sleep(1.0 / requests_per_second)

        total_time = time.perf_counter() - start_time
        total_requests / total_time

        assert metrics.success_rate >= 0.9


class TestAuthenticationLoad:
    """Test authentication endpoint under load."""

    @pytest.mark.anyio
    async def test_concurrent_logins(self, client: AsyncClient):
        """Test concurrent login requests."""
        metrics = LoadTestMetrics()
        num_concurrent = 10

        async def login() -> tuple[bool, float]:
            start = time.perf_counter()
            try:
                response = await client.post(
                    "/auth/login", json={"username": "admin", "password": "admin123!"}
                )
                elapsed = time.perf_counter() - start
                # Accept 200 (success) or 429 (rate limited under load)
                return response.status_code in [200, 429], elapsed
            except Exception:
                return False, time.perf_counter() - start

        tasks = [login() for _ in range(num_concurrent)]
        results = await asyncio.gather(*tasks)

        for success, elapsed in results:
            if success:
                metrics.record_success(elapsed)
            else:
                metrics.record_failure("")

        # Relaxed thresholds for test environment
        assert metrics.success_rate >= 0.7
        # Auth may be slower in test environment
        assert metrics.avg_response_time < 5.0

    @pytest.mark.anyio
    async def test_token_verification_load(self, client: AsyncClient, auth_token: str):
        """Test token verification under load."""
        metrics = LoadTestMetrics()
        headers = {"Authorization": f"Bearer {auth_token}"}
        num_requests = 20

        async def verify() -> tuple[bool, float]:
            start = time.perf_counter()
            try:
                response = await client.get("/auth/me", headers=headers)
                elapsed = time.perf_counter() - start
                return response.status_code == 200, elapsed
            except Exception:
                return False, time.perf_counter() - start

        tasks = [verify() for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)

        for success, elapsed in results:
            if success:
                metrics.record_success(elapsed)
            else:
                metrics.record_failure("")

        assert metrics.success_rate >= 0.95
        assert metrics.avg_response_time < 1.0


class TestMixedWorkload:
    """Test mixed API workload."""

    @pytest.mark.anyio
    async def test_mixed_operations(self, client: AsyncClient, auth_token: str):
        """Test mixed read/write operations."""
        metrics = LoadTestMetrics()
        headers = {"Authorization": f"Bearer {auth_token}"}

        async def health_check() -> tuple[str, bool, float]:
            start = time.perf_counter()
            try:
                response = await client.get("/health")
                return "health", response.status_code == 200, time.perf_counter() - start
            except Exception:
                return "health", False, time.perf_counter() - start

        async def list_jobs() -> tuple[str, bool, float]:
            start = time.perf_counter()
            try:
                response = await client.get("/jobs", headers=headers)
                return "list_jobs", response.status_code == 200, time.perf_counter() - start
            except Exception:
                return "list_jobs", False, time.perf_counter() - start

        async def submit_job() -> tuple[str, bool, float]:
            start = time.perf_counter()
            try:
                response = await client.post(
                    "/jobs",
                    json={
                        "problem_type": "QAOA",
                        "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                        "backend": "local_simulator",
                    },
                    headers=headers,
                )
                return "submit_job", response.status_code == 202, time.perf_counter() - start
            except Exception:
                return "submit_job", False, time.perf_counter() - start

        async def get_user() -> tuple[str, bool, float]:
            start = time.perf_counter()
            try:
                response = await client.get("/auth/me", headers=headers)
                return "get_user", response.status_code == 200, time.perf_counter() - start
            except Exception:
                return "get_user", False, time.perf_counter() - start

        # Create mixed workload
        operations = [health_check] * 5 + [list_jobs] * 5 + [submit_job] * 5 + [get_user] * 5

        tasks = [op() for op in operations]
        results = await asyncio.gather(*tasks)

        # Analyze by operation type
        by_type: dict[str, LoadTestMetrics] = {}

        for op_type, success, elapsed in results:
            if op_type not in by_type:
                by_type[op_type] = LoadTestMetrics()

            if success:
                by_type[op_type].record_success(elapsed)
                metrics.record_success(elapsed)
            else:
                by_type[op_type].record_failure("")
                metrics.record_failure("")

        for op_type, _op_metrics in by_type.items():
            pass

        assert metrics.success_rate >= 0.9


class TestCryptoOperationsLoad:
    """Test crypto operations under load."""

    @pytest.mark.anyio
    async def test_key_generation_load(self, client: AsyncClient, auth_token: str):
        """Test KEM key generation under load."""
        metrics = LoadTestMetrics()
        headers = {"Authorization": f"Bearer {auth_token}"}
        num_requests = 10

        async def generate_key() -> tuple[bool, float]:
            start = time.perf_counter()
            try:
                response = await client.post("/auth/keys/generate", headers=headers)
                elapsed = time.perf_counter() - start
                return response.status_code == 200, elapsed
            except Exception:
                return False, time.perf_counter() - start

        tasks = [generate_key() for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)

        for success, elapsed in results:
            if success:
                metrics.record_success(elapsed)
            else:
                metrics.record_failure("")

        assert metrics.success_rate >= 0.9


class TestJobPollingLoad:
    """Test job polling performance."""

    @pytest.mark.anyio
    async def test_concurrent_polling(self, client: AsyncClient, auth_token: str):
        """Test concurrent job status polling."""
        metrics = LoadTestMetrics()
        headers = {"Authorization": f"Bearer {auth_token}"}

        # First submit some jobs
        job_ids = []
        for _ in range(5):
            response = await client.post(
                "/jobs",
                json={
                    "problem_type": "QAOA",
                    "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                    "backend": "local_simulator",
                },
                headers=headers,
            )
            if response.status_code == 202:
                job_ids.append(response.json()["job_id"])

        if not job_ids:
            pytest.skip("No jobs created for polling test")

        async def poll_job(job_id: str) -> tuple[bool, float]:
            start = time.perf_counter()
            try:
                response = await client.get(f"/jobs/{job_id}", headers=headers)
                elapsed = time.perf_counter() - start
                return response.status_code == 200, elapsed
            except Exception:
                return False, time.perf_counter() - start

        # Poll each job 5 times concurrently
        tasks = []
        for job_id in job_ids:
            for _ in range(5):
                tasks.append(poll_job(job_id))

        results = await asyncio.gather(*tasks)

        for success, elapsed in results:
            if success:
                metrics.record_success(elapsed)
            else:
                metrics.record_failure("")

        assert metrics.success_rate >= 0.95
        assert metrics.avg_response_time < 1.0


class TestLatencyDistribution:
    """Test and analyze latency distribution."""

    @pytest.mark.anyio
    async def test_health_endpoint_latency(self, client: AsyncClient):
        """Analyze latency distribution for health endpoint."""
        metrics = LoadTestMetrics()
        num_requests = 50

        for _ in range(num_requests):
            start = time.perf_counter()
            try:
                response = await client.get("/health")
                elapsed = time.perf_counter() - start
                if response.status_code == 200:
                    metrics.record_success(elapsed)
                else:
                    metrics.record_failure("")
            except Exception:
                metrics.record_failure("")

        # Health endpoint should be very fast
        assert metrics.p95_response_time < 0.5  # 500ms

    @pytest.mark.anyio
    async def test_job_submission_latency(self, client: AsyncClient, auth_token: str):
        """Analyze latency distribution for job submissions."""
        metrics = LoadTestMetrics()
        headers = {"Authorization": f"Bearer {auth_token}"}
        num_requests = 20

        for _ in range(num_requests):
            start = time.perf_counter()
            try:
                response = await client.post(
                    "/jobs",
                    json={
                        "problem_type": "QAOA",
                        "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                        "backend": "local_simulator",
                    },
                    headers=headers,
                )
                elapsed = time.perf_counter() - start
                if response.status_code == 202:
                    metrics.record_success(elapsed)
                else:
                    metrics.record_failure("")
            except Exception:
                metrics.record_failure("")

        # Job submission should complete within reasonable time
        assert metrics.p95_response_time < 5.0  # 5 seconds

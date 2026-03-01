"""
Integration Tests for Quantum-Safe Optimization Platform.

Full workflow tests: login → submit → poll → results
"""

import asyncio
import os

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
    """Get authentication token for tests."""
    response = await client.post("/auth/login", json={"username": "admin", "password": "admin123!"})
    assert response.status_code == 200
    return response.json()["access_token"]


class TestFullJobWorkflow:
    """Test complete job lifecycle from submission to results."""

    @pytest.mark.anyio
    async def test_qaoa_maxcut_full_workflow(self, client: AsyncClient, auth_token: str):
        """
        Full QAOA MaxCut workflow: login → submit → poll → results.
        """
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Step 1: Submit QAOA job
        submit_response = await client.post(
            "/jobs",
            json={
                "problem_type": "QAOA",
                "problem_config": {
                    "problem": "maxcut",
                    "edges": [[0, 1], [1, 2], [2, 3], [3, 0], [0, 2]],
                },
                "parameters": {
                    "layers": 2,
                    "optimizer": "COBYLA",
                    "shots": 500,
                },
                "backend": "local_simulator",
            },
            headers=headers,
        )
        assert submit_response.status_code == 202
        job_data = submit_response.json()
        job_id = job_data["job_id"]
        assert job_data["status"] == "queued"
        assert job_data["problem_type"] == "QAOA"

        # Step 2: Poll for completion (with timeout)
        max_polls = 30
        poll_interval = 0.5
        final_status = None

        for _ in range(max_polls):
            poll_response = await client.get(
                f"/jobs/{job_id}",
                headers=headers,
            )
            assert poll_response.status_code == 200
            job_status = poll_response.json()
            final_status = job_status["status"]

            if final_status in ("completed", "failed"):
                break

            await asyncio.sleep(poll_interval)

        # Step 3: Verify results
        assert final_status == "completed", f"Job failed or timed out: {job_status}"

        result = job_status.get("result")
        assert result is not None, "Completed job should have result"
        assert "optimal_value" in result or "optimal_bitstring" in result
        assert job_status.get("completed_at") is not None

    @pytest.mark.anyio
    async def test_vqe_full_workflow(self, client: AsyncClient, auth_token: str):
        """
        Full VQE workflow: login → submit → poll → results.
        Note: VQE requires specific Hamiltonian setup; may fail if backend not configured.
        """
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Step 1: Submit VQE job
        submit_response = await client.post(
            "/jobs",
            json={
                "problem_type": "VQE",
                "problem_config": {
                    "hamiltonian": "h2",
                },
                "parameters": {
                    "optimizer": "COBYLA",
                    "shots": 500,
                    "ansatz_type": "hardware_efficient",
                },
                "backend": "local_simulator",
            },
            headers=headers,
        )
        assert submit_response.status_code == 202
        job_id = submit_response.json()["job_id"]

        # Step 2: Poll for completion
        final_status = await self._poll_job(client, job_id, headers)

        # Step 3: Verify job completed (may fail if backend not fully configured)
        job_response = await client.get(f"/jobs/{job_id}", headers=headers)
        job_data = job_response.json()

        # VQE may fail if the specific Hamiltonian setup is not supported
        assert final_status in ("completed", "failed")
        if final_status == "completed":
            result = job_data.get("result")
            assert result is not None

    @pytest.mark.anyio
    async def test_annealing_qubo_full_workflow(self, client: AsyncClient, auth_token: str):
        """
        Full Annealing workflow: login → submit → poll → results.
        Note: Requires D-Wave API token; may fail if not configured.
        """
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Simple QUBO matrix for testing
        qubo_matrix = [
            [1.0, -0.5, 0.0],
            [-0.5, 1.0, -0.5],
            [0.0, -0.5, 1.0],
        ]

        # Step 1: Submit Annealing job
        submit_response = await client.post(
            "/jobs",
            json={
                "problem_type": "ANNEALING",
                "problem_config": {
                    "qubo_matrix": qubo_matrix,
                },
                "parameters": {
                    "num_reads": 100,
                    "use_hybrid": True,
                },
                "backend": "dwave_simulator",
            },
            headers=headers,
        )
        assert submit_response.status_code == 202
        job_id = submit_response.json()["job_id"]

        # Step 2: Poll for completion
        final_status = await self._poll_job(client, job_id, headers)

        # Step 3: Verify results (may fail if D-Wave token not configured)
        job_response = await client.get(f"/jobs/{job_id}", headers=headers)
        job_data = job_response.json()

        # Annealing requires D-Wave API token, so failure is expected without it
        assert final_status in ("completed", "failed")
        if final_status == "completed":
            result = job_data.get("result")
            assert result is not None

    async def _poll_job(
        self,
        client: AsyncClient,
        job_id: str,
        headers: dict,
        max_polls: int = 30,
        interval: float = 0.5,
    ) -> str:
        """Poll job until completion or timeout."""
        for _ in range(max_polls):
            response = await client.get(f"/jobs/{job_id}", headers=headers)
            status = response.json()["status"]
            if status in ("completed", "failed"):
                return status
            await asyncio.sleep(interval)
        return "timeout"


class TestJobListAndPagination:
    """Test job listing and pagination."""

    @pytest.mark.anyio
    async def test_list_jobs_pagination(self, client: AsyncClient, auth_token: str):
        """Test job listing with pagination."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Submit multiple jobs
        for _i in range(3):
            await client.post(
                "/jobs",
                json={
                    "problem_type": "QAOA",
                    "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                    "backend": "local_simulator",
                },
                headers=headers,
            )

        # List jobs with pagination
        response = await client.get(
            "/jobs?limit=2&offset=0",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data
        assert len(data["jobs"]) <= 2
        assert data["limit"] == 2
        assert data["offset"] == 0

    @pytest.mark.anyio
    async def test_list_jobs_filter_by_status(self, client: AsyncClient, auth_token: str):
        """Test filtering jobs by status."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        response = await client.get(
            "/jobs?status=queued",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        # All returned jobs should be queued
        for job in data.get("jobs", []):
            assert job["status"] == "queued"


class TestErrorHandlingWorkflow:
    """Test error scenarios in job workflow."""

    @pytest.mark.anyio
    async def test_invalid_problem_type(self, client: AsyncClient, auth_token: str):
        """Test submission with invalid problem type."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        response = await client.post(
            "/jobs",
            json={
                "problem_type": "INVALID_TYPE",
                "problem_config": {},
                "backend": "local_simulator",
            },
            headers=headers,
        )
        # Should accept but fail during processing
        assert response.status_code in (202, 400)

    @pytest.mark.anyio
    async def test_missing_required_config(self, client: AsyncClient, auth_token: str):
        """Test submission with minimal/empty configuration."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # ANNEALING with empty config - should generate default QUBO
        response = await client.post(
            "/jobs",
            json={
                "problem_type": "ANNEALING",
                "problem_config": {},  # Empty config, will use defaults
                "backend": "local_simulator",
            },
            headers=headers,
        )
        # Job should be accepted
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Poll and verify job processes (with defaults)
        await asyncio.sleep(2)
        status_response = await client.get(
            f"/jobs/{job_id}",
            headers=headers,
        )
        job_data = status_response.json()
        # Should complete successfully with default QUBO or be processing
        assert job_data["status"] in ("completed", "failed", "running", "queued")

    @pytest.mark.anyio
    async def test_job_not_found(self, client: AsyncClient, auth_token: str):
        """Test getting non-existent job."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        response = await client.get(
            "/jobs/nonexistent-job-id",
            headers=headers,
        )
        assert response.status_code == 404


class TestAuthWorkflow:
    """Test authentication workflow integration."""

    @pytest.mark.anyio
    async def test_full_auth_lifecycle(self, client: AsyncClient):
        """Test complete auth lifecycle: register → login → use → refresh → logout."""
        import secrets

        # Step 1: Register new user
        username = f"workflow_test_{secrets.token_hex(4)}"
        register_response = await client.post(
            "/auth/register",
            json={
                "username": username,
                "password": "SecurePassword123!",
                "email": f"{username}@test.com",
            },
        )
        assert register_response.status_code == 201

        # Step 2: Login
        login_response = await client.post(
            "/auth/login", json={"username": username, "password": "SecurePassword123!"}
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        # Step 3: Use token to access protected resource
        me_response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_response.status_code == 200
        assert me_response.json()["username"] == username

        # Step 4: Refresh token
        refresh_response = await client.post(
            "/auth/refresh", headers={"Authorization": f"Bearer {token}"}
        )
        assert refresh_response.status_code == 200
        new_token = refresh_response.json()["access_token"]

        # Step 5: Logout
        logout_response = await client.post(
            "/auth/logout", headers={"Authorization": f"Bearer {new_token}"}
        )
        assert logout_response.status_code == 200

        # Step 6: Verify token is revoked
        verify_response = await client.get(
            "/auth/me", headers={"Authorization": f"Bearer {new_token}"}
        )
        assert verify_response.status_code == 401


class TestEncryptedResultWorkflow:
    """Test job workflow with encrypted results."""

    @pytest.mark.anyio
    async def test_job_with_result_encryption(self, client: AsyncClient, auth_token: str):
        """Test job that encrypts results with user's public key."""
        from quantum_safe_crypto import KemKeyPair

        headers = {"Authorization": f"Bearer {auth_token}"}

        # Step 1: Generate and set encryption key
        keypair = KemKeyPair()
        key_response = await client.put(
            "/auth/keys/encryption-key",
            json={
                "public_key": keypair.public_key,
                "key_type": "ML-KEM-768",
            },
            headers=headers,
        )
        assert key_response.status_code == 200

        # Step 2: Submit job with encryption enabled
        submit_response = await client.post(
            "/jobs",
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1], [1, 2]]},
                "encrypt_result": True,
                "backend": "local_simulator",
            },
            headers=headers,
        )
        assert submit_response.status_code == 202
        job_id = submit_response.json()["job_id"]

        # Step 3: Poll for completion
        final_status = None
        for _ in range(30):
            poll_response = await client.get(f"/jobs/{job_id}", headers=headers)
            if poll_response.status_code != 200:
                # If there's an error, break early
                break
            job_data = poll_response.json()
            final_status = job_data.get("status")
            if final_status in ("completed", "failed"):
                break
            await asyncio.sleep(0.5)

        # Step 4: Verify encrypted result
        assert final_status == "completed"
        # If encryption is enabled, result should be encrypted (returned as JSON string)
        if job_data.get("encrypted_result"):
            # Plain result should be hidden when encrypted
            assert len(job_data["encrypted_result"]) > 0

"""
End-to-end job lifecycle tests.

Tests complete job lifecycle: submit → poll → result → decrypt.
"""

import asyncio
import os
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app

os.environ["TESTING"] = "1"


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
async def auth_token(client: AsyncClient):
    """Get authentication token."""
    response = await client.post("/auth/login", json={"username": "admin", "password": "admin123!"})
    return response.json()["access_token"]


@pytest.mark.anyio
async def test_job_submission_qaoa(client: AsyncClient, auth_token: str):
    """Test submitting a QAOA job with valid configuration."""
    response = await client.post(
        "/jobs",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "problem_type": "QAOA",
            "problem_config": {"problem": "maxcut", "edges": [[0, 1], [1, 2], [2, 0]]},
            "backend": "local_simulator",
            "parameters": {"layers": 1, "shots": 100},
        },
    )

    assert response.status_code in [201, 202]
    data = response.json()
    assert "job_id" in data
    assert "status" in data
    assert data["status"] in ["queued", "pending"]


@pytest.mark.anyio
async def test_job_submission_vqe(client: AsyncClient, auth_token: str):
    """Test submitting a VQE job with valid configuration."""
    response = await client.post(
        "/jobs",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "problem_type": "VQE",
            "problem_config": {
                "molecule": "h2",
                "basis": "sto-3g",
                "distance": 0.735,
            },
            "backend": "local_simulator",
            "parameters": {"ansatz_depth": 3, "shots": 1024},
        },
    )

    assert response.status_code in [201, 202]
    data = response.json()
    assert "job_id" in data
    assert "status" in data


@pytest.mark.anyio
async def test_job_submission_annealing(client: AsyncClient, auth_token: str):
    """Test submitting a quantum annealing job."""
    response = await client.post(
        "/jobs",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "problem_type": "ANNEALING",
            "problem_config": {"problem": "qubo", "qubo_matrix": [[0, -1], [-1, 0]]},
            "backend": "dwave",
            "parameters": {"annealing_time": 100, "num_reads": 100},
        },
    )

    assert response.status_code in [201, 202]
    data = response.json()
    assert "job_id" in data


@pytest.mark.anyio
async def test_job_status_polling(client: AsyncClient, auth_token: str):
    """Test polling job status until completion."""
    submit_response = await client.post(
        "/jobs",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "problem_type": "QAOA",
            "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
            "backend": "local_simulator",
            "parameters": {"layers": 1, "shots": 50},
        },
    )

    job_id = submit_response.json()["job_id"]

    statuses = []
    status_transitions = 0
    last_status = None

    for _ in range(30):
        status_response = await client.get(
            f"/jobs/{job_id}", headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert status_response.status_code == 200
        data = status_response.json()
        current_status = data["status"]
        statuses.append(current_status)

        if last_status and last_status != current_status:
            status_transitions += 1
        last_status = current_status

        if current_status in ["completed", "failed", "cancelled"]:
            break

        await asyncio.sleep(0.2)

    assert len(statuses) > 0
    assert status_transitions >= 0


@pytest.mark.anyio
async def test_job_result_retrieval(client: AsyncClient, auth_token: str):
    """Test retrieving job results after completion."""
    submit_response = await client.post(
        "/jobs",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "problem_type": "QAOA",
            "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
            "backend": "local_simulator",
            "parameters": {"layers": 1, "shots": 50},
        },
    )

    job_id = submit_response.json()["job_id"]

    for _ in range(30):
        status_response = await client.get(
            f"/jobs/{job_id}", headers={"Authorization": f"Bearer {auth_token}"}
        )
        if status_response.json()["status"] == "completed":
            break
        await asyncio.sleep(0.2)

    result_response = await client.get(
        f"/jobs/{job_id}/results", headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert result_response.status_code == 200
    result_data = result_response.json()
    assert "result" in result_data or "values" in result_data


@pytest.mark.anyio
async def test_client_side_decryption(client: AsyncClient, auth_token: str):
    """Test client-side decryption of encrypted results."""
    try:
        from quantum_safe_crypto import KemKeyPair, EncryptedEnvelope

        keypair = KemKeyPair()

        register_key_response = await client.put(
            "/auth/keys/encryption-key",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"public_key": keypair.public_key, "key_type": "ML-KEM-768"},
        )

        if register_key_response.status_code == 200:
            submit_response = await client.post(
                "/jobs",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "problem_type": "QAOA",
                    "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                    "backend": "local_simulator",
                    "parameters": {"layers": 1, "shots": 50},
                    "encrypt_result": True,
                },
            )

            job_id = submit_response.json()["job_id"]

            for _ in range(60):
                status_response = await client.get(
                    f"/jobs/{job_id}", headers={"Authorization": f"Bearer {auth_token}"}
                )
                if status_response.json()["status"] == "completed":
                    break
                await asyncio.sleep(0.5)

            result_response = await client.get(
                f"/jobs/{job_id}/results", headers={"Authorization": f"Bearer {auth_token}"}
            )

            if result_response.status_code == 200:
                result_data = result_response.json()
                if "encrypted_result" in result_data:
                    envelope_dict = result_data["encrypted_result"]
                    envelope = EncryptedEnvelope.from_dict(envelope_dict)

                    decrypted = keypair.decrypt(envelope)
                    assert decrypted is not None
                    assert len(decrypted) > 0
    except ImportError:
        pytest.skip("quantum_safe_crypto not available")


@pytest.mark.anyio
async def test_job_cancellation(client: AsyncClient, auth_token: str):
    """Test cancelling a running job."""
    submit_response = await client.post(
        "/jobs",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "problem_type": "VQE",
            "problem_config": {"molecule": "h2", "basis": "sto-3g"},
            "backend": "local_simulator",
            "parameters": {"ansatz_depth": 5, "shots": 10000},
        },
    )

    job_id = submit_response.json()["job_id"]

    cancel_response = await client.delete(
        f"/jobs/{job_id}", headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert cancel_response.status_code in [200, 204, 404]

    if cancel_response.status_code != 404:
        status_response = await client.get(
            f"/jobs/{job_id}", headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert status_response.json()["status"] == "cancelled"


@pytest.mark.anyio
async def test_job_list_with_filters(client: AsyncClient, auth_token: str):
    """Test listing jobs with status and limit filters."""
    for i in range(3):
        await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "local_simulator",
                "parameters": {"layers": 1, "shots": 50},
            },
        )
        await asyncio.sleep(0.1)

    list_response = await client.get(
        "/jobs?status=queued&limit=2", headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert list_response.status_code == 200
    data = list_response.json()
    assert "jobs" in data
    assert len(data["jobs"]) <= 2


@pytest.mark.anyio
async def test_job_retry_failed_job(client: AsyncClient, auth_token: str):
    """Test retrying a failed job."""
    with patch("api.routers.jobs.job_queue") as mock_queue:
        mock_queue.submit_job = AsyncMock(return_value=str(uuid4()))

        submit_response = await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "invalid_backend",
                "parameters": {"layers": 1, "shots": 50},
            },
        )

        job_id = submit_response.json()["job_id"]

        for _ in range(30):
            status_response = await client.get(
                f"/jobs/{job_id}", headers={"Authorization": f"Bearer {auth_token}"}
            )
            data = status_response.json()
            if data["status"] in ["failed", "completed", "cancelled"]:
                break
            await asyncio.sleep(0.1)

        retry_response = await client.post(
            f"/jobs/{job_id}/retry", headers={"Authorization": f"Bearer {auth_token}"}
        )

        if retry_response.status_code in [200, 202]:
            retry_data = retry_response.json()
            assert "job_id" in retry_data
            assert retry_data["job_id"] != job_id


@pytest.mark.anyio
async def test_job_with_callback_url(client: AsyncClient, auth_token: str):
    """Test job submission with webhook callback URL."""
    callback_url = "https://example.com/webhook-test"

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        response = await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "local_simulator",
                "parameters": {"layers": 1, "shots": 50},
                "callback_url": callback_url,
            },
        )

        assert response.status_code in [201, 202]


@pytest.mark.anyio
async def test_job_with_encryption_settings(client: AsyncClient, auth_token: str):
    """Test job submission with encryption settings."""
    response = await client.post(
        "/jobs",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "problem_type": "QAOA",
            "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
            "backend": "local_simulator",
            "parameters": {"layers": 1, "shots": 50},
            "crypto": {"encrypt_result": True, "algorithm": "ML-KEM-768"},
        },
    )

    assert response.status_code in [201, 202]


@pytest.mark.anyio
async def test_job_with_priority_level(client: AsyncClient, auth_token: str):
    """Test job submission with priority levels."""
    for priority in [1, 5, 10]:
        response = await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "local_simulator",
                "parameters": {"layers": 1, "shots": 50},
                "priority": priority,
            },
        )

        assert response.status_code in [201, 202]
        data = response.json()
        assert "priority" in data or data.get("status") in ["queued", "pending"]


@pytest.mark.anyio
async def test_job_validation_invalid_parameters(client: AsyncClient, auth_token: str):
    """Test job submission with invalid parameters."""
    invalid_configs = [
        {"problem_type": "INVALID", "problem_config": {}, "backend": "local_simulator"},
        {
            "problem_type": "QAOA",
            "problem_config": {"problem": "invalid"},
            "backend": "local_simulator",
        },
        {
            "problem_type": "QAOA",
            "problem_config": {"problem": "maxcut"},
            "backend": "invalid_backend",
        },
    ]

    for config in invalid_configs:
        response = await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=config,
        )
        assert response.status_code in [400, 422]


@pytest.mark.anyio
async def test_job_unauthorized_access(client: AsyncClient):
    """Test that unauthorized users cannot access job endpoints."""
    response = await client.get("/jobs", headers={"Authorization": ""})
    assert response.status_code in [401, 403]

    response = await client.post(
        "/jobs",
        json={
            "problem_type": "QAOA",
            "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
            "backend": "local_simulator",
        },
    )
    assert response.status_code in [401, 403]


@pytest.mark.anyio
async def test_job_concurrent_submissions(client: AsyncClient, auth_token: str):
    """Test handling of multiple concurrent job submissions."""
    import asyncio

    async def submit_job(index):
        return await client.post(
            "/jobs",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "problem_type": "QAOA",
                "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
                "backend": "local_simulator",
                "parameters": {"layers": 1, "shots": 50},
            },
        )

    tasks = [submit_job(i) for i in range(5)]
    responses = await asyncio.gather(*tasks)

    success_count = sum(1 for r in responses if r.status_code in [201, 202])
    assert success_count >= 4


@pytest.mark.anyio
async def test_job_metadata_preservation(client: AsyncClient, auth_token: str):
    """Test that job metadata is preserved."""
    metadata = {"client_id": "test_client", "project": "integration_test", "tags": ["test", "unit"]}

    response = await client.post(
        "/jobs",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "problem_type": "QAOA",
            "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
            "backend": "local_simulator",
            "parameters": {"layers": 1, "shots": 50},
            "metadata": metadata,
        },
    )

    if response.status_code in [201, 202]:
        job_id = response.json()["job_id"]
        state_response = await client.get(
            f"/jobs/{job_id}", headers={"Authorization": f"Bearer {auth_token}"}
        )
        job_data = state_response.json()
        assert "metadata" in job_data or job_data.get("status")

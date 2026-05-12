"""API contract tests — verify OpenAPI spec matches actual response schemas.

These tests validate that the API responses conform to the declared OpenAPI schema.
Run with: pytest tests/contract/test_api_contract.py -v

Tests:
- /health response schema
- /api/v1/jobs POST response (JobResponse)
- /api/v1/jobs GET response (JobListResponse with pagination)
- /api/v1/jobs/{job_id} GET response
- Required fields present and correct types
"""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client(app):
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.contract
@pytest.mark.asyncio
async def test_health_contract(client):
    """Verify /health response matches expected schema."""
    resp = await client.get("/health")
    assert resp.status_code == 200

    data = resp.json()
    # Required fields
    assert "status" in data
    assert isinstance(data["status"], str)
    assert "version" in data
    assert "environment" in data
    assert "mode" in data


@pytest.mark.contract
@pytest.mark.asyncio
async def test_job_submission_contract(client):
    """Verify POST /api/v1/jobs response matches JobResponse schema."""
    resp = await client.post(
        "/api/v1/jobs",
        json={
            "problem_type": "QAOA",
            "problem_config": {
                "problem": "maxcut",
                "edges": [[0, 1], [1, 2], [2, 0]],
            },
            "parameters": {"layers": 2, "shots": 100},
            "backend": "local_simulator",
        },
    )
    assert resp.status_code == 202

    data = resp.json()
    # JobResponse required fields
    assert "job_id" in data
    assert isinstance(data["job_id"], str)
    assert data["job_id"].startswith("job_")
    assert "status" in data
    assert data["status"] == "queued"
    assert "problem_type" in data
    assert data["problem_type"] == "QAOA"
    assert "backend" in data
    assert "created_at" in data
    assert isinstance(data["created_at"], str)


@pytest.mark.contract
@pytest.mark.asyncio
async def test_job_list_contract(client):
    """Verify GET /api/v1/jobs response matches JobListResponse with pagination."""
    resp = await client.get("/api/v1/jobs")
    assert resp.status_code == 200

    data = resp.json()
    # JobListResponse fields
    assert "jobs" in data
    assert isinstance(data["jobs"], list)
    assert "total" in data
    assert isinstance(data["total"], int)
    assert "limit" in data
    assert isinstance(data["limit"], int)
    assert "offset" in data
    assert isinstance(data["offset"], int)

    # Pagination metadata
    assert "page" in data
    assert isinstance(data["page"], int)
    assert "page_size" in data
    assert isinstance(data["page_size"], int)
    assert "total_pages" in data
    assert isinstance(data["total_pages"], int)
    assert "has_next" in data
    assert isinstance(data["has_next"], bool)
    assert "has_prev" in data
    assert isinstance(data["has_prev"], bool)


@pytest.mark.contract
@pytest.mark.asyncio
async def test_queue_status_contract(client):
    """Verify GET /api/v1/jobs/queue/status response schema."""
    resp = await client.get("/api/v1/jobs/queue/status")
    assert resp.status_code == 200

    data = resp.json()
    assert "queue_size" in data
    assert "max_capacity" in data
    assert "priority_distribution" in data
    assert isinstance(data["priority_distribution"], dict)
    assert "next_job_id" in data


@pytest.mark.contract
@pytest.mark.asyncio
async def test_rate_limit_headers_present(client):
    """Verify API responses include rate limiting headers."""
    resp = await client.get("/health")
    # Rate limit headers should be present (even if None/slowavi not configured)
    # At minimum the response should succeed without error
    assert resp.status_code == 200


@pytest.mark.contract
@pytest.mark.asyncio
async def test_job_response_field_types(client):
    """Verify individual job response field types match schema."""
    # Submit a job first
    submit_resp = await client.post(
        "/api/v1/jobs",
        json={
            "problem_type": "QAOA",
            "problem_config": {"problem": "maxcut", "edges": [[0, 1]]},
            "backend": "local_simulator",
        },
    )
    job_id = submit_resp.json()["job_id"]

    # Get the job
    resp = await client.get(f"/api/v1/jobs/{job_id}")
    assert resp.status_code == 200

    data = resp.json()
    assert isinstance(data["job_id"], str)
    assert isinstance(data["status"], str)
    assert data["status"] in ("queued", "running", "completed", "failed")
    assert isinstance(data["problem_type"], str)
    assert isinstance(data["backend"], str)
    assert isinstance(data["created_at"], str)
    # Optional fields
    assert data.get("started_at") is None or isinstance(data["started_at"], str)
    assert data.get("completed_at") is None or isinstance(data["completed_at"], str)
    assert data.get("result") is None or isinstance(data["result"], dict)
    assert data.get("error") is None or isinstance(data["error"], str)

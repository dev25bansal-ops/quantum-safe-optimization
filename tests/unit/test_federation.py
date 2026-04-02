"""
Tests for Federation API Endpoints.
"""

import os
import pytest
from httpx import ASGITransport, AsyncClient

os.environ["TESTING"] = "1"

from api.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_token(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": os.getenv("ADMIN_PASSWORD", "changeme")},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.mark.anyio
async def test_get_federation_status(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/federation/status",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_regions" in data
    assert "healthy_regions" in data
    assert "unhealthy_regions" in data
    assert "federation_enabled" in data


@pytest.mark.anyio
async def test_list_regions(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/federation/regions",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.anyio
async def test_list_regions_by_provider(client: AsyncClient, auth_token: str):
    for provider in ["ibm", "aws", "azure", "dwave"]:
        response = await client.get(
            f"/api/v1/federation/regions?provider={provider}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200


@pytest.mark.anyio
async def test_list_regions_by_status(client: AsyncClient, auth_token: str):
    for status in ["healthy", "degraded", "offline"]:
        response = await client.get(
            f"/api/v1/federation/regions?status={status}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200


@pytest.mark.anyio
async def test_list_regions_pagination(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/federation/regions?limit=5",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) <= 5


@pytest.mark.anyio
async def test_create_region(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/federation/regions",
        json={
            "name": "Test Region",
            "provider": "ibm",
            "endpoint": "https://test.quantum.ibm.com",
            "priority": 5,
            "weight": 100,
            "max_concurrent_jobs": 10,
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "region_id" in data
    assert data["name"] == "Test Region"
    assert data["provider"] == "ibm"
    assert data["status"] == "healthy"


@pytest.mark.anyio
async def test_create_region_aws(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/federation/regions",
        json={
            "name": "AWS Region",
            "provider": "aws",
            "endpoint": "https://braket.aws.amazon.com",
            "priority": 8,
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "aws"


@pytest.mark.anyio
async def test_create_region_azure(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/federation/regions",
        json={
            "name": "Azure Region",
            "provider": "azure",
            "endpoint": "https://quantum.azure.com",
            "priority": 7,
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "azure"


@pytest.mark.anyio
async def test_get_region(client: AsyncClient, auth_token: str):
    list_response = await client.get(
        "/api/v1/federation/regions",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    regions = list_response.json()

    if regions:
        region_id = regions[0]["region_id"]
        response = await client.get(
            f"/api/v1/federation/regions/{region_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["region_id"] == region_id


@pytest.mark.anyio
async def test_get_region_not_found(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/federation/regions/nonexistent_region",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_update_region_status(client: AsyncClient, auth_token: str):
    create_response = await client.post(
        "/api/v1/federation/regions",
        json={
            "name": "Status Test Region",
            "provider": "ibm",
            "endpoint": "https://status.test.com",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    region_id = create_response.json()["region_id"]

    response = await client.patch(
        f"/api/v1/federation/regions/{region_id}/status?status=degraded",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"


@pytest.mark.anyio
async def test_update_region_status_offline(client: AsyncClient, auth_token: str):
    create_response = await client.post(
        "/api/v1/federation/regions",
        json={
            "name": "Offline Test Region",
            "provider": "aws",
            "endpoint": "https://offline.test.com",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    region_id = create_response.json()["region_id"]

    response = await client.patch(
        f"/api/v1/federation/regions/{region_id}/status?status=offline",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "offline"


@pytest.mark.anyio
async def test_remove_region(client: AsyncClient, auth_token: str):
    create_response = await client.post(
        "/api/v1/federation/regions",
        json={
            "name": "Region to Remove",
            "provider": "ibm",
            "endpoint": "https://remove.test.com",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    region_id = create_response.json()["region_id"]

    response = await client.delete(
        f"/api/v1/federation/regions/{region_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "removed"


@pytest.mark.anyio
async def test_remove_region_not_found(client: AsyncClient, auth_token: str):
    response = await client.delete(
        "/api/v1/federation/regions/nonexistent_region",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_route_job(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/federation/route",
        json={
            "shots": 10000,
            "preferred_provider": "ibm",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "decision_id" in data
    assert "selected_region" in data
    assert "selected_provider" in data
    assert "endpoint" in data
    assert "estimated_cost" in data
    assert "estimated_latency_ms" in data
    assert "routing_reason" in data


@pytest.mark.anyio
async def test_route_job_with_constraints(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/federation/route",
        json={
            "shots": 5000,
            "max_cost": 10.0,
            "max_latency_ms": 500,
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "selected_region" in data


@pytest.mark.anyio
async def test_route_job_with_preferred_region(client: AsyncClient, auth_token: str):
    list_response = await client.get(
        "/api/v1/federation/regions",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    regions = list_response.json()

    if regions:
        preferred_region = regions[0]["region_id"]
        response = await client.post(
            "/api/v1/federation/route",
            json={
                "shots": 1000,
                "preferred_region": preferred_region,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200


@pytest.mark.anyio
async def test_list_providers(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/federation/providers",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    assert len(data["providers"]) > 0

    provider_ids = [p["id"] for p in data["providers"]]
    assert "ibm" in provider_ids
    assert "aws" in provider_ids
    assert "azure" in provider_ids
    assert "dwave" in provider_ids


@pytest.mark.anyio
async def test_federation_health(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/federation/health",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ["healthy", "degraded"]
    assert "healthy_regions" in data
    assert "total_regions" in data


@pytest.mark.anyio
async def test_failover_test(client: AsyncClient, auth_token: str):
    create_response1 = await client.post(
        "/api/v1/federation/regions",
        json={"name": "Source Region", "provider": "ibm", "endpoint": "https://source.test.com"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    create_response2 = await client.post(
        "/api/v1/federation/regions",
        json={"name": "Target Region", "provider": "aws", "endpoint": "https://target.test.com"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    from_region = create_response1.json()["region_id"]
    to_region = create_response2.json()["region_id"]

    response = await client.post(
        f"/api/v1/federation/failover/test?from_region={from_region}&to_region={to_region}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failover_test_passed"
    assert "estimated_downtime_ms" in data


@pytest.mark.anyio
async def test_failover_test_not_found(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/federation/failover/test?from_region=nonexistent&to_region=also_nonexistent",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_get_federation_metrics(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/federation/metrics",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_active_jobs" in data
    assert "total_queued_jobs" in data
    assert "average_latency_ms" in data
    assert "total_regions" in data
    assert "healthy_regions" in data
    assert "by_provider" in data


@pytest.mark.anyio
async def test_region_response_fields(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/federation/regions",
        json={
            "name": "Fields Test Region",
            "provider": "ibm",
            "endpoint": "https://fields.test.com",
            "priority": 10,
            "weight": 50,
            "max_concurrent_jobs": 20,
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    data = response.json()

    assert "region_id" in data
    assert "name" in data
    assert "provider" in data
    assert "endpoint" in data
    assert "status" in data
    assert "priority" in data
    assert "weight" in data
    assert "created_at" in data


@pytest.mark.anyio
async def test_routing_decision_fields(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/federation/route",
        json={"shots": 1000},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    data = response.json()

    assert "decision_id" in data
    assert "selected_region" in data
    assert "selected_provider" in data
    assert "endpoint" in data
    assert "estimated_cost" in data
    assert "estimated_latency_ms" in data
    assert "estimated_wait_time_s" in data
    assert "alternatives" in data
    assert "routing_reason" in data


@pytest.mark.anyio
async def test_invalid_provider_rejected(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/federation/regions",
        json={
            "name": "Invalid Provider",
            "provider": "invalid_provider",
            "endpoint": "https://invalid.com",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 422

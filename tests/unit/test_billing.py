"""
Tests for Billing API Endpoints.
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
async def test_record_usage_event(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/billing/usage",
        json={
            "resource_type": "job_submission",
            "quantity": 5,
            "metadata": {"job_id": "test_job"},
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "event_id" in data
    assert data["resource_type"] == "job_submission"
    assert data["quantity"] == 5
    assert "unit_price" in data
    assert "total_price" in data


@pytest.mark.anyio
async def test_record_usage_quantum_shots(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/billing/usage",
        json={
            "resource_type": "quantum_shot",
            "quantity": 10000,
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["resource_type"] == "quantum_shot"
    assert data["quantity"] == 10000
    assert data["total_price"] > 0


@pytest.mark.anyio
async def test_get_usage_summary(client: AsyncClient, auth_token: str):
    await client.post(
        "/api/v1/billing/usage",
        json={"resource_type": "api_call", "quantity": 100},
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    response = await client.get(
        "/api/v1/billing/usage/summary",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "period_start" in data
    assert "period_end" in data
    assert "total_cost" in data
    assert "total_events" in data


@pytest.mark.anyio
async def test_usage_summary_periods(client: AsyncClient, auth_token: str):
    for period in ["day", "week", "month", "year"]:
        response = await client.get(
            f"/api/v1/billing/usage/summary?period={period}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200


@pytest.mark.anyio
async def test_get_pricing(client: AsyncClient):
    response = await client.get("/api/v1/billing/pricing")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

    pricing_items = {item["resource_type"]: item for item in data}
    assert "api_call" in pricing_items
    assert "job_submission" in pricing_items
    assert "quantum_shot" in pricing_items

    for item in data:
        assert "resource_type" in item
        assert "unit" in item
        assert "price_usd" in item
        assert item["price_usd"] >= 0


@pytest.mark.anyio
async def test_estimate_cost(client: AsyncClient):
    response = await client.post(
        "/api/v1/billing/estimate",
        json={
            "shots": 10000,
            "jobs": 5,
            "compute_seconds": 120,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_cost" in data
    assert data["total_cost"] > 0

    assert "shots_cost" in data
    assert "jobs_cost" in data
    assert "compute_cost" in data


@pytest.mark.anyio
async def test_estimate_cost_zero(client: AsyncClient):
    response = await client.post(
        "/api/v1/billing/estimate",
        json={
            "shots": 0,
            "jobs": 0,
            "compute_seconds": 0,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_cost"] >= 0


@pytest.mark.anyio
async def test_generate_invoice(client: AsyncClient, auth_token: str):
    await client.post(
        "/api/v1/billing/usage",
        json={"resource_type": "job_submission", "quantity": 10},
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    response = await client.post(
        "/api/v1/billing/invoices/generate",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "invoice_id" in data
    assert "tenant_id" in data
    assert "period_start" in data
    assert "period_end" in data
    assert "status" in data
    assert "subtotal" in data
    assert "tax" in data
    assert "total" in data
    assert "line_items" in data


@pytest.mark.anyio
async def test_generate_weekly_invoice(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/billing/invoices/generate?period=week",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "invoice_id" in data


@pytest.mark.anyio
async def test_list_invoices(client: AsyncClient, auth_token: str):
    await client.post(
        "/api/v1/billing/invoices/generate",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    response = await client.get(
        "/api/v1/billing/invoices",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.anyio
async def test_invalid_resource_type(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/billing/usage",
        json={
            "resource_type": "invalid_type",
            "quantity": 1,
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_negative_quantity_rejected(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/billing/usage",
        json={
            "resource_type": "api_call",
            "quantity": -10,
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 422

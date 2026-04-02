"""
Integration Tests for Advanced Features.

Tests the interaction between multiple modules.
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


# ============================================================================
# Tenant + Billing Integration
# ============================================================================


@pytest.mark.anyio
async def test_tenant_billing_integration(client: AsyncClient, auth_token: str):
    tenant_response = await client.post(
        "/api/v1/tenants",
        json={
            "name": "Billing Test Tenant",
            "tier": "professional",
            "admin_email": "admin@billing.com",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert tenant_response.status_code == 200

    usage_response = await client.post(
        "/api/v1/billing/usage",
        json={"resource_type": "job_submission", "quantity": 10},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert usage_response.status_code == 200

    summary_response = await client.get(
        "/api/v1/billing/usage/summary",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert summary_response.status_code == 200


@pytest.mark.anyio
async def test_tenant_quota_billing(client: AsyncClient, auth_token: str):
    tenant_response = await client.post(
        "/api/v1/tenants",
        json={"name": "Quota Tenant", "tier": "enterprise", "admin_email": "admin@quota.com"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    tenant_id = tenant_response.json()["tenant_id"]

    quota_response = await client.get(
        f"/api/v1/tenants/{tenant_id}/quota",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert quota_response.status_code == 200

    estimate_response = await client.post(
        "/api/v1/billing/estimate",
        json={"shots": 100000, "jobs": 50},
    )
    assert estimate_response.status_code == 200


# ============================================================================
# Marketplace + Federation Integration
# ============================================================================


@pytest.mark.anyio
async def test_marketplace_federation_integration(client: AsyncClient, auth_token: str):
    marketplace_response = await client.get(
        "/api/v1/marketplace/search",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert marketplace_response.status_code == 200

    route_response = await client.post(
        "/api/v1/federation/route",
        json={"shots": 5000, "preferred_provider": "ibm"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert route_response.status_code == 200


@pytest.mark.anyio
async def test_purchase_with_federation(client: AsyncClient, auth_token: str):
    home_response = await client.get(
        "/api/v1/marketplace/",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    featured = home_response.json()["featured"]

    if featured:
        algorithm_id = featured[0]["algorithm_id"]
        purchase_response = await client.post(
            f"/api/v1/marketplace/{algorithm_id}/purchase",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert purchase_response.status_code == 200

        route_response = await client.post(
            "/api/v1/federation/route",
            json={"shots": 1000},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert route_response.status_code == 200


# ============================================================================
# Circuit + Security Integration
# ============================================================================


@pytest.mark.anyio
async def test_circuit_security_integration(client: AsyncClient, auth_token: str):
    gen_response = await client.post(
        "/api/v1/circuits/circuits/generate?num_qubits=4&depth=3",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert gen_response.status_code == 200
    circuit_id = gen_response.json()["circuit_id"]

    encrypt_response = await client.post(
        "/api/v1/security/quantum-encryption/encrypt",
        json={"circuit_id": circuit_id, "gates": 50},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert encrypt_response.status_code == 200


@pytest.mark.anyio
async def test_circuit_execution_with_audit(client: AsyncClient, auth_token: str):
    gen_response = await client.post(
        "/api/v1/circuits/circuits/generate?num_qubits=2&depth=1",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    circuit_id = gen_response.json()["circuit_id"]

    exec_response = await client.post(
        f"/api/v1/circuits/circuits/{circuit_id}/execute",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert exec_response.status_code == 200

    audit_response = await client.get(
        "/api/v1/security/audit/logs",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert audit_response.status_code == 200


# ============================================================================
# Multi-tenant Isolation Test
# ============================================================================


@pytest.mark.anyio
async def test_multi_tenant_isolation(client: AsyncClient, auth_token: str):
    tenant1_response = await client.post(
        "/api/v1/tenants",
        json={"name": "Tenant One", "tier": "professional", "admin_email": "admin@tenant1.com"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    tenant1_id = tenant1_response.json()["tenant_id"]

    tenant2_response = await client.post(
        "/api/v1/tenants",
        json={"name": "Tenant Two", "tier": "professional", "admin_email": "admin@tenant2.com"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    tenant2_id = tenant2_response.json()["tenant_id"]

    assert tenant1_id != tenant2_id

    quota1_response = await client.get(
        f"/api/v1/tenants/{tenant1_id}/quota",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    quota2_response = await client.get(
        f"/api/v1/tenants/{tenant2_id}/quota",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert quota1_response.status_code == 200
    assert quota2_response.status_code == 200


# ============================================================================
# Full Workflow Integration
# ============================================================================


@pytest.mark.anyio
async def test_full_quantum_workflow(client: AsyncClient, auth_token: str):
    tenant_response = await client.post(
        "/api/v1/tenants",
        json={"name": "Workflow Tenant", "tier": "enterprise", "admin_email": "admin@workflow.com"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert tenant_response.status_code == 200

    route_response = await client.post(
        "/api/v1/federation/route",
        json={"shots": 10000},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert route_response.status_code == 200
    endpoint = route_response.json()["endpoint"]

    circuit_response = await client.post(
        "/api/v1/circuits/circuits/generate?num_qubits=5&depth=4",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert circuit_response.status_code == 200
    circuit_id = circuit_response.json()["circuit_id"]

    exec_response = await client.post(
        f"/api/v1/circuits/circuits/{circuit_id}/execute?shots=10000",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert exec_response.status_code == 200

    usage_response = await client.post(
        "/api/v1/billing/usage",
        json={"resource_type": "quantum_shot", "quantity": 10000},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert usage_response.status_code == 200

    invoice_response = await client.post(
        "/api/v1/billing/invoices/generate",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert invoice_response.status_code == 200


# ============================================================================
# Security + Billing Integration
# ============================================================================


@pytest.mark.anyio
async def test_security_audit_billing(client: AsyncClient, auth_token: str):
    for _ in range(3):
        await client.post(
            "/api/v1/billing/usage",
            json={"resource_type": "api_call", "quantity": 100},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    audit_response = await client.get(
        "/api/v1/security/audit/summary",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert audit_response.status_code == 200

    verify_response = await client.post(
        "/api/v1/security/audit-integrity/verify",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert verify_response.status_code == 200


# ============================================================================
# Federation Health + Circuit Execution
# ============================================================================


@pytest.mark.anyio
async def test_federation_health_before_execution(client: AsyncClient, auth_token: str):
    health_response = await client.get(
        "/api/v1/federation/health",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert health_response.status_code == 200
    health_data = health_response.json()

    if health_data["healthy_regions"] > 0:
        circuit_response = await client.post(
            "/api/v1/circuits/circuits/generate?num_qubits=3&depth=2",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert circuit_response.status_code == 200


# ============================================================================
# Key Rotation Integration
# ============================================================================


@pytest.mark.anyio
async def test_key_rotation_workflow(client: AsyncClient, auth_token: str):
    encrypt_response1 = await client.post(
        "/api/v1/security/quantum-encryption/encrypt",
        json={"data": "before_rotation"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert encrypt_response1.status_code == 200
    ciphertext1 = encrypt_response1.json()["ciphertext"]

    rotate_response = await client.post(
        "/api/v1/security/quantum-encryption/rotate",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert rotate_response.status_code == 200

    encrypt_response2 = await client.post(
        "/api/v1/security/quantum-encryption/encrypt",
        json={"data": "after_rotation"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert encrypt_response2.status_code == 200

    status_response = await client.get(
        "/api/v1/security/quantum-encryption/status",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert status_response.status_code == 200


# ============================================================================
# Marketplace Search + Purchase Flow
# ============================================================================


@pytest.mark.anyio
async def test_marketplace_search_purchase_flow(client: AsyncClient, auth_token: str):
    search_response = await client.get(
        "/api/v1/marketplace/search?category=optimization&min_rating=3.0",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert search_response.status_code == 200
    results = search_response.json()

    if results:
        algorithm_id = results[0]["algorithm_id"]

        algo_response = await client.get(
            f"/api/v1/marketplace/{algorithm_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert algo_response.status_code == 200

        purchase_response = await client.post(
            f"/api/v1/marketplace/{algorithm_id}/purchase",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert purchase_response.status_code == 200

        review_response = await client.post(
            f"/api/v1/marketplace/{algorithm_id}/reviews",
            json={"rating": 5, "comment": "Great algorithm!"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert review_response.status_code == 200

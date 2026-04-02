"""
Tests for Multi-Tenant API Endpoints.
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
async def test_create_tenant(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/tenants",
        json={
            "name": "Test Company",
            "tier": "professional",
            "admin_email": "admin@testcompany.com",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "tenant_id" in data
    assert data["name"] == "Test Company"
    assert data["tier"] == "professional"
    assert data["is_active"] is True
    assert "quotas" in data
    assert "created_at" in data


@pytest.mark.anyio
async def test_create_tenant_enterprise(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/tenants",
        json={
            "name": "Enterprise Corp",
            "tier": "enterprise",
            "admin_email": "admin@enterprise.com",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "enterprise"
    quotas = data["quotas"]
    assert quotas.get("jobs_per_month", 0) == -1 or quotas.get("jobs_per_month", 0) >= 1000


@pytest.mark.anyio
async def test_create_tenant_free_tier(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/tenants",
        json={
            "name": "Free User",
            "tier": "free",
            "admin_email": "admin@freeuser.com",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "free"


@pytest.mark.anyio
async def test_list_tenants(client: AsyncClient, auth_token: str):
    await client.post(
        "/api/v1/tenants",
        json={"name": "List Test Tenant", "tier": "professional", "admin_email": "admin@list.com"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    response = await client.get(
        "/api/v1/tenants",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


@pytest.mark.anyio
async def test_get_tenant(client: AsyncClient, auth_token: str):
    create_response = await client.post(
        "/api/v1/tenants",
        json={"name": "Get Test Tenant", "tier": "professional", "admin_email": "admin@get.com"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    tenant_id = create_response.json()["tenant_id"]

    response = await client.get(
        f"/api/v1/tenants/{tenant_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == tenant_id
    assert data["name"] == "Get Test Tenant"


@pytest.mark.anyio
async def test_get_tenant_not_found(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/tenants/nonexistent_tenant",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_update_tenant(client: AsyncClient, auth_token: str):
    create_response = await client.post(
        "/api/v1/tenants",
        json={
            "name": "Update Test Tenant",
            "tier": "professional",
            "admin_email": "admin@update.com",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    tenant_id = create_response.json()["tenant_id"]

    response = await client.patch(
        f"/api/v1/tenants/{tenant_id}",
        json={"name": "Updated Tenant Name"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Tenant Name"


@pytest.mark.anyio
async def test_update_tenant_settings(client: AsyncClient, auth_token: str):
    create_response = await client.post(
        "/api/v1/tenants",
        json={
            "name": "Settings Test Tenant",
            "tier": "professional",
            "admin_email": "admin@settings.com",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    tenant_id = create_response.json()["tenant_id"]

    response = await client.patch(
        f"/api/v1/tenants/{tenant_id}",
        json={
            "settings": {
                "notifications_enabled": True,
                "custom_setting": "value",
            }
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_add_tenant_member(client: AsyncClient, auth_token: str):
    create_response = await client.post(
        "/api/v1/tenants",
        json={
            "name": "Member Test Tenant",
            "tier": "professional",
            "admin_email": "admin@member.com",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    tenant_id = create_response.json()["tenant_id"]

    response = await client.post(
        f"/api/v1/tenants/{tenant_id}/members",
        json={
            "user_email": "newuser@example.com",
            "role": "member",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "user_id" in data
    assert data["role"] == "member"


@pytest.mark.anyio
async def test_add_tenant_member_admin(client: AsyncClient, auth_token: str):
    create_response = await client.post(
        "/api/v1/tenants",
        json={
            "name": "Admin Member Tenant",
            "tier": "professional",
            "admin_email": "admin@adminmember.com",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    tenant_id = create_response.json()["tenant_id"]

    response = await client.post(
        f"/api/v1/tenants/{tenant_id}/members",
        json={
            "user_email": "admin@example.com",
            "role": "admin",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "admin"


@pytest.mark.anyio
async def test_list_tenant_members(client: AsyncClient, auth_token: str):
    create_response = await client.post(
        "/api/v1/tenants",
        json={
            "name": "Members List Tenant",
            "tier": "professional",
            "admin_email": "admin@memberslist.com",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    tenant_id = create_response.json()["tenant_id"]

    response = await client.get(
        f"/api/v1/tenants/{tenant_id}/members",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.anyio
async def test_update_member_role(client: AsyncClient, auth_token: str):
    create_response = await client.post(
        "/api/v1/tenants",
        json={
            "name": "Role Update Tenant",
            "tier": "professional",
            "admin_email": "admin@role.com",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    tenant_id = create_response.json()["tenant_id"]

    member_response = await client.post(
        f"/api/v1/tenants/{tenant_id}/members",
        json={"user_email": "roleuser@example.com", "role": "member"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    user_id = member_response.json()["user_id"]

    response = await client.patch(
        f"/api/v1/tenants/{tenant_id}/members/{user_id}",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "admin"


@pytest.mark.anyio
async def test_remove_tenant_member(client: AsyncClient, auth_token: str):
    create_response = await client.post(
        "/api/v1/tenants",
        json={
            "name": "Remove Member Tenant",
            "tier": "professional",
            "admin_email": "admin@remove.com",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    tenant_id = create_response.json()["tenant_id"]

    member_response = await client.post(
        f"/api/v1/tenants/{tenant_id}/members",
        json={"user_email": "removeuser@example.com", "role": "member"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    user_id = member_response.json()["user_id"]

    response = await client.delete(
        f"/api/v1/tenants/{tenant_id}/members/{user_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "removed"


@pytest.mark.anyio
async def test_check_quotas(client: AsyncClient, auth_token: str):
    create_response = await client.post(
        "/api/v1/tenants",
        json={
            "name": "Quota Test Tenant",
            "tier": "professional",
            "admin_email": "admin@quota.com",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    tenant_id = create_response.json()["tenant_id"]

    response = await client.get(
        f"/api/v1/tenants/{tenant_id}/quota",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

    for quota in data:
        assert "resource" in quota
        assert "used" in quota
        assert "limit" in quota
        assert "remaining" in quota
        assert "exceeded" in quota


@pytest.mark.anyio
async def test_get_tenant_usage(client: AsyncClient, auth_token: str):
    create_response = await client.post(
        "/api/v1/tenants",
        json={
            "name": "Usage Test Tenant",
            "tier": "professional",
            "admin_email": "admin@usage.com",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    tenant_id = create_response.json()["tenant_id"]

    response = await client.get(
        f"/api/v1/tenants/{tenant_id}/usage",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == tenant_id
    assert "jobs_count" in data
    assert "shots_used" in data
    assert "compute_seconds" in data


@pytest.mark.anyio
async def test_get_tenant_usage_periods(client: AsyncClient, auth_token: str):
    create_response = await client.post(
        "/api/v1/tenants",
        json={
            "name": "Usage Period Tenant",
            "tier": "professional",
            "admin_email": "admin@usageperiod.com",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    tenant_id = create_response.json()["tenant_id"]

    for period in ["day", "week", "month"]:
        response = await client.get(
            f"/api/v1/tenants/{tenant_id}/usage?period={period}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200


@pytest.mark.anyio
async def test_list_roles(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/roles",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "roles" in data
    assert "all_permissions" in data

    role_names = [r["name"] for r in data["roles"]]
    assert "admin" in role_names
    assert "member" in role_names
    assert "viewer" in role_names


@pytest.mark.anyio
async def test_tenant_slug_generation(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/tenants",
        json={"name": "Test Company Name", "tier": "professional", "admin_email": "admin@slug.com"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "slug" in data
    assert "-" in data["slug"] or data["slug"].islower()


@pytest.mark.anyio
async def test_invalid_tier_rejected(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/tenants",
        json={"name": "Invalid Tier", "tier": "invalid_tier", "admin_email": "admin@invalid.com"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_invalid_role_rejected(client: AsyncClient, auth_token: str):
    create_response = await client.post(
        "/api/v1/tenants",
        json={
            "name": "Invalid Role Tenant",
            "tier": "professional",
            "admin_email": "admin@invalidrole.com",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    tenant_id = create_response.json()["tenant_id"]

    response = await client.post(
        f"/api/v1/tenants/{tenant_id}/members",
        json={"user_email": "test@example.com", "role": "invalid_role"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 422

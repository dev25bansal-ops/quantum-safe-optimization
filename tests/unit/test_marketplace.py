"""
Tests for Algorithm Marketplace API Endpoints.
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
async def test_marketplace_home(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/marketplace/",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "featured" in data
    assert "categories" in data
    assert "total_algorithms" in data
    assert isinstance(data["featured"], list)


@pytest.mark.anyio
async def test_search_algorithms(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/marketplace/search",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.anyio
async def test_search_with_query(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/marketplace/search?q=qaoa",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.anyio
async def test_search_by_category(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/marketplace/search?category=optimization",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_search_with_filters(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/marketplace/search?min_rating=3.5&pricing=free&max_price=100",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_search_with_tags(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/marketplace/search?tags=quantum,optimization",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_search_pagination(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/marketplace/search?limit=5&offset=0",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) <= 5


@pytest.mark.anyio
async def test_list_categories(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/marketplace/categories",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

    for category in data:
        assert "id" in category
        assert "name" in category
        assert "count" in category


@pytest.mark.anyio
async def test_publish_algorithm(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/marketplace/",
        json={
            "name": "Test Algorithm",
            "description": "A test algorithm for unit testing",
            "category": "optimization",
            "pricing_model": "free",
            "price": 0,
            "tags": ["test", "quantum"],
            "min_qubits": 2,
            "max_qubits": 10,
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "algorithm_id" in data
    assert data["name"] == "Test Algorithm"
    assert data["pricing_model"] == "free"


@pytest.mark.anyio
async def test_publish_paid_algorithm(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/marketplace/",
        json={
            "name": "Premium Algorithm",
            "description": "A premium algorithm",
            "category": "machine_learning",
            "pricing_model": "paid",
            "price": 99.99,
            "license_type": "commercial",
            "tags": ["premium"],
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["pricing_model"] == "paid"
    assert data["price"] == 99.99


@pytest.mark.anyio
async def test_get_algorithm(client: AsyncClient, auth_token: str):
    home_response = await client.get(
        "/api/v1/marketplace/",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    featured = home_response.json()["featured"]

    if featured:
        algorithm_id = featured[0]["algorithm_id"]
        response = await client.get(
            f"/api/v1/marketplace/{algorithm_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["algorithm_id"] == algorithm_id


@pytest.mark.anyio
async def test_get_algorithm_not_found(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/marketplace/nonexistent_algorithm",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_purchase_algorithm(client: AsyncClient, auth_token: str):
    home_response = await client.get(
        "/api/v1/marketplace/",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    featured = home_response.json()["featured"]

    if featured:
        algorithm_id = featured[0]["algorithm_id"]
        response = await client.post(
            f"/api/v1/marketplace/{algorithm_id}/purchase",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "purchase_id" in data
        assert "algorithm_id" in data
        assert "license_key" in data


@pytest.mark.anyio
async def test_get_algorithm_reviews(client: AsyncClient, auth_token: str):
    home_response = await client.get(
        "/api/v1/marketplace/",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    featured = home_response.json()["featured"]

    if featured:
        algorithm_id = featured[0]["algorithm_id"]
        response = await client.get(
            f"/api/v1/marketplace/{algorithm_id}/reviews",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.anyio
async def test_submit_review(client: AsyncClient, auth_token: str):
    home_response = await client.get(
        "/api/v1/marketplace/",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    featured = home_response.json()["featured"]

    if featured:
        algorithm_id = featured[0]["algorithm_id"]
        response = await client.post(
            f"/api/v1/marketplace/{algorithm_id}/reviews",
            json={
                "rating": 5,
                "comment": "Excellent algorithm!",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 5
        assert "review_id" in data


@pytest.mark.anyio
async def test_submit_review_invalid_rating(client: AsyncClient, auth_token: str):
    home_response = await client.get(
        "/api/v1/marketplace/",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    featured = home_response.json()["featured"]

    if featured:
        algorithm_id = featured[0]["algorithm_id"]
        response = await client.post(
            f"/api/v1/marketplace/{algorithm_id}/reviews",
            json={"rating": 6, "comment": "Invalid rating"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 422


@pytest.mark.anyio
async def test_get_user_purchases(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/marketplace/user/purchases",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.anyio
async def test_delete_algorithm(client: AsyncClient, auth_token: str):
    publish_response = await client.post(
        "/api/v1/marketplace/",
        json={
            "name": "Algorithm to Delete",
            "description": "Will be deleted",
            "category": "optimization",
            "pricing_model": "free",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    algorithm_id = publish_response.json()["algorithm_id"]

    response = await client.delete(
        f"/api/v1/marketplace/{algorithm_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"


@pytest.mark.anyio
async def test_algorithm_fields(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/marketplace/",
        json={
            "name": "Full Fields Algorithm",
            "description": "Testing all fields",
            "long_description": "This is a longer description",
            "category": "optimization",
            "pricing_model": "paid",
            "price": 49.99,
            "license_type": "mit",
            "tags": ["quantum", "vqe"],
            "min_qubits": 4,
            "max_qubits": 20,
            "source_url": "https://github.com/example/algo",
            "documentation_url": "https://docs.example.com",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["min_qubits"] == 4
    assert data["max_qubits"] == 20
    assert data["license_type"] == "mit"


@pytest.mark.anyio
async def test_search_sorting(client: AsyncClient, auth_token: str):
    for sort_option in ["relevance", "downloads", "rating", "newest"]:
        response = await client.get(
            f"/api/v1/marketplace/search?sort={sort_option}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200

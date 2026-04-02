"""
Tests for Circuit Visualization API Endpoints.
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
async def test_list_circuits(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/circuits/circuits",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.anyio
async def test_generate_circuit(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/circuits/circuits/generate?num_qubits=4&depth=3",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "circuit_id" in data
    assert data["num_qubits"] == 4
    assert data["depth"] == 3
    assert "layers" in data
    assert "total_gates" in data


@pytest.mark.anyio
async def test_generate_circuit_custom_qubits(client: AsyncClient, auth_token: str):
    for qubits in [2, 3, 5, 8]:
        response = await client.post(
            f"/api/v1/circuits/circuits/generate?num_qubits={qubits}&depth=2",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["num_qubits"] == qubits


@pytest.mark.anyio
async def test_generate_circuit_custom_depth(client: AsyncClient, auth_token: str):
    for depth in [1, 2, 5, 10]:
        response = await client.post(
            f"/api/v1/circuits/circuits/generate?num_qubits=3&depth={depth}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["depth"] == depth


@pytest.mark.anyio
async def test_get_circuit(client: AsyncClient, auth_token: str):
    gen_response = await client.post(
        "/api/v1/circuits/circuits/generate?num_qubits=4&depth=2",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    circuit_id = gen_response.json()["circuit_id"]

    response = await client.get(
        f"/api/v1/circuits/circuits/{circuit_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["circuit_id"] == circuit_id


@pytest.mark.anyio
async def test_get_circuit_not_found(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/circuits/circuits/nonexistent_circuit",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_execute_circuit(client: AsyncClient, auth_token: str):
    gen_response = await client.post(
        "/api/v1/circuits/circuits/generate?num_qubits=2&depth=2",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    circuit_id = gen_response.json()["circuit_id"]

    response = await client.post(
        f"/api/v1/circuits/circuits/{circuit_id}/execute?shots=1024",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "execution_id" in data
    assert data["circuit_id"] == circuit_id
    assert data["status"] == "running"
    assert "started_at" in data


@pytest.mark.anyio
async def test_execute_circuit_not_found(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/circuits/circuits/nonexistent/execute",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_get_execution(client: AsyncClient, auth_token: str):
    gen_response = await client.post(
        "/api/v1/circuits/circuits/generate?num_qubits=2&depth=1",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    circuit_id = gen_response.json()["circuit_id"]

    exec_response = await client.post(
        f"/api/v1/circuits/circuits/{circuit_id}/execute",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    execution_id = exec_response.json()["execution_id"]

    response = await client.get(
        f"/api/v1/circuits/executions/{execution_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["execution_id"] == execution_id


@pytest.mark.anyio
async def test_get_execution_not_found(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/circuits/executions/nonexistent_execution",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_cancel_execution(client: AsyncClient, auth_token: str):
    gen_response = await client.post(
        "/api/v1/circuits/circuits/generate?num_qubits=4&depth=10",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    circuit_id = gen_response.json()["circuit_id"]

    exec_response = await client.post(
        f"/api/v1/circuits/circuits/{circuit_id}/execute",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    execution_id = exec_response.json()["execution_id"]

    response = await client.post(
        f"/api/v1/circuits/executions/{execution_id}/cancel",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"


@pytest.mark.anyio
async def test_cancel_completed_execution(client: AsyncClient, auth_token: str):
    gen_response = await client.post(
        "/api/v1/circuits/circuits/generate?num_qubits=2&depth=1",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    circuit_id = gen_response.json()["circuit_id"]

    exec_response = await client.post(
        f"/api/v1/circuits/circuits/{circuit_id}/execute",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    execution_id = exec_response.json()["execution_id"]

    import asyncio

    await asyncio.sleep(1)

    response = await client.post(
        f"/api/v1/circuits/executions/{execution_id}/cancel",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code in [200, 400]


@pytest.mark.anyio
async def test_cancel_execution_not_found(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/circuits/executions/nonexistent/cancel",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_get_visualization_styles(client: AsyncClient, auth_token: str):
    response = await client.get(
        "/api/v1/circuits/styles",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "styles" in data
    assert "themes" in data
    assert "gate_colors" in data

    style_ids = [s["id"] for s in data["styles"]]
    assert "circuit" in style_ids
    assert "timeline" in style_ids
    assert "bloch" in style_ids

    theme_ids = [t["id"] for t in data["themes"]]
    assert "dark" in theme_ids
    assert "light" in theme_ids


@pytest.mark.anyio
async def test_circuit_gate_structure(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/circuits/circuits/generate?num_qubits=3&depth=2",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    data = response.json()

    assert "layers" in data
    assert len(data["layers"]) > 0

    for layer in data["layers"]:
        assert "layer_id" in layer
        assert "gates" in layer
        assert "depth" in layer

        for gate in layer["gates"]:
            assert "name" in gate
            assert "qubits" in gate
            assert isinstance(gate["qubits"], list)


@pytest.mark.anyio
async def test_circuit_total_gates(client: AsyncClient, auth_token: str):
    response = await client.post(
        "/api/v1/circuits/circuits/generate?num_qubits=4&depth=3",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    data = response.json()

    total_gates_from_layers = sum(len(layer["gates"]) for layer in data["layers"])
    assert data["total_gates"] == total_gates_from_layers

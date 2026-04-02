"""
Live Circuit Visualization API.

Provides real-time quantum circuit visualization with WebSocket streaming.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


class CircuitGate(BaseModel):
    """A single quantum gate in the circuit."""

    name: str
    qubits: list[int]
    params: list[float] = Field(default_factory=list)
    controls: list[int] | None = None


class CircuitLayer(BaseModel):
    """A layer of gates in the circuit."""

    layer_id: int
    gates: list[CircuitGate]
    depth: int = 1


class QuantumCircuit(BaseModel):
    """Quantum circuit representation."""

    circuit_id: str
    name: str
    num_qubits: int
    num_clbits: int
    layers: list[CircuitLayer]
    total_gates: int
    depth: int
    created_at: str


class CircuitExecution(BaseModel):
    """Circuit execution state."""

    execution_id: str
    circuit_id: str
    status: str
    current_layer: int
    total_layers: int
    measurements: dict[str, Any] | None = None
    statevector: list[complex] | None = None
    started_at: str
    completed_at: str | None = None


class VisualizationConfig(BaseModel):
    """Visualization configuration."""

    style: str = Field(default="circuit", pattern="^(circuit|timeline|bloch)$")
    theme: str = Field(default="dark", pattern="^(dark|light)$")
    animate: bool = True
    show_measurements: bool = True
    show_state: bool = False
    highlight_active: bool = True


_in_memory_circuits: dict[str, QuantumCircuit] = {}
_in_memory_executions: dict[str, CircuitExecution] = {}
_active_websockets: dict[str, list[WebSocket]] = {}


def generate_sample_circuit(num_qubits: int = 4, depth: int = 3) -> QuantumCircuit:
    """Generate a sample QAOA-like circuit."""
    layers: list[CircuitLayer] = []
    gate_count = 0

    for layer_id in range(depth):
        gates = []

        if layer_id % 2 == 0:
            for q in range(num_qubits):
                gates.append(
                    CircuitGate(
                        name="H",
                        qubits=[q],
                    )
                )
                gate_count += 1

            for q in range(num_qubits - 1):
                gates.append(
                    CircuitGate(
                        name="CZ",
                        qubits=[q, q + 1],
                    )
                )
                gate_count += 1
        else:
            for q in range(num_qubits):
                gates.append(
                    CircuitGate(
                        name="RZ",
                        qubits=[q],
                        params=[0.5 + layer_id * 0.1],
                    )
                )
                gate_count += 1

            for q in range(num_qubits):
                gates.append(
                    CircuitGate(
                        name="RX",
                        qubits=[q],
                        params=[0.3 + layer_id * 0.05],
                    )
                )
                gate_count += 1

        layers.append(CircuitLayer(layer_id=layer_id, gates=gates, depth=len(gates)))

    circuit_id = f"circ_{uuid4().hex[:8]}"
    return QuantumCircuit(
        circuit_id=circuit_id,
        name=f"QAOA-{num_qubits}q-{depth}p",
        num_qubits=num_qubits,
        num_clbits=num_qubits,
        layers=layers,
        total_gates=gate_count,
        depth=depth,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


async def broadcast_execution_update(execution_id: str, data: dict[str, Any]):
    """Broadcast execution update to all connected WebSocket clients."""
    if execution_id in _active_websockets:
        message = json.dumps(data)
        for ws in _active_websockets[execution_id]:
            try:
                await ws.send_text(message)
            except Exception as e:
                logger.warning(f"WebSocket send failed: {e}")


async def simulate_circuit_execution(execution_id: str, circuit: QuantumCircuit):
    """Simulate circuit execution with real-time updates."""
    execution = _in_memory_executions[execution_id]

    for layer_id, layer in enumerate(circuit.layers):
        if execution.status == "cancelled":
            break

        execution.current_layer = layer_id

        await broadcast_execution_update(
            execution_id,
            {
                "type": "layer_update",
                "execution_id": execution_id,
                "layer_id": layer_id,
                "total_layers": len(circuit.layers),
                "gates": [g.model_dump() for g in layer.gates],
                "progress": (layer_id + 1) / len(circuit.layers) * 100,
            },
        )

        await asyncio.sleep(0.3)

    if execution.status != "cancelled":
        import random

        measurements = {}
        for c in range(circuit.num_clbits):
            measurements[f"c{c}"] = random.choice([0, 1])

        execution.status = "completed"
        execution.current_layer = len(circuit.layers)
        execution.measurements = measurements
        execution.completed_at = datetime.now(timezone.utc).isoformat()

        await broadcast_execution_update(
            execution_id,
            {
                "type": "execution_complete",
                "execution_id": execution_id,
                "status": "completed",
                "measurements": measurements,
                "duration_ms": 300 * len(circuit.layers),
                "completed_at": execution.completed_at,
            },
        )


@router.get("/circuits", response_model=list[QuantumCircuit])
async def list_circuits():
    """List all stored circuits."""
    return list(_in_memory_circuits.values())


@router.post("/circuits/generate", response_model=QuantumCircuit)
async def generate_circuit(
    num_qubits: int = 4,
    depth: int = 3,
    algorithm: str = "qaoa",
):
    """Generate a sample quantum circuit."""
    circuit = generate_sample_circuit(num_qubits, depth)
    _in_memory_circuits[circuit.circuit_id] = circuit
    return circuit


@router.get("/circuits/{circuit_id}", response_model=QuantumCircuit)
async def get_circuit(circuit_id: str):
    """Get a specific circuit by ID."""
    if circuit_id not in _in_memory_circuits:
        raise HTTPException(status_code=404, detail="Circuit not found")
    return _in_memory_circuits[circuit_id]


@router.post("/circuits/{circuit_id}/execute", response_model=CircuitExecution)
async def execute_circuit(circuit_id: str, shots: int = 1024):
    """Start circuit execution."""
    if circuit_id not in _in_memory_circuits:
        raise HTTPException(status_code=404, detail="Circuit not found")

    circuit = _in_memory_circuits[circuit_id]

    execution_id = f"exec_{uuid4().hex[:8]}"
    execution = CircuitExecution(
        execution_id=execution_id,
        circuit_id=circuit_id,
        status="running",
        current_layer=0,
        total_layers=len(circuit.layers),
        started_at=datetime.now(timezone.utc).isoformat(),
    )

    _in_memory_executions[execution_id] = execution
    _active_websockets[execution_id] = []

    asyncio.create_task(simulate_circuit_execution(execution_id, circuit))

    return execution


@router.get("/executions/{execution_id}", response_model=CircuitExecution)
async def get_execution(execution_id: str):
    """Get execution status."""
    if execution_id not in _in_memory_executions:
        raise HTTPException(status_code=404, detail="Execution not found")
    return _in_memory_executions[execution_id]


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(execution_id: str):
    """Cancel a running execution."""
    if execution_id not in _in_memory_executions:
        raise HTTPException(status_code=404, detail="Execution not found")

    execution = _in_memory_executions[execution_id]
    if execution.status not in ("running", "queued"):
        raise HTTPException(status_code=400, detail="Execution already completed")

    execution.status = "cancelled"
    execution.completed_at = datetime.now(timezone.utc).isoformat()

    await broadcast_execution_update(
        execution_id,
        {
            "type": "execution_cancelled",
            "execution_id": execution_id,
            "completed_at": execution.completed_at,
        },
    )

    return {"status": "cancelled", "execution_id": execution_id}


@router.websocket("/ws/executions/{execution_id}")
async def websocket_execution_visualization(websocket: WebSocket, execution_id: str):
    """WebSocket endpoint for real-time circuit visualization."""
    await websocket.accept()

    if execution_id not in _in_memory_executions:
        await websocket.send_text(json.dumps({"type": "error", "message": "Execution not found"}))
        await websocket.close()
        return

    _active_websockets.setdefault(execution_id, []).append(websocket)

    try:
        execution = _in_memory_executions[execution_id]
        circuit = _in_memory_circuits[execution.circuit_id]

        await websocket.send_text(
            json.dumps(
                {
                    "type": "init",
                    "execution_id": execution_id,
                    "circuit": circuit.model_dump(),
                    "status": execution.status,
                    "current_layer": execution.current_layer,
                }
            )
        )

        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)

                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif message.get("type") == "get_state":
                    execution = _in_memory_executions.get(execution_id)
                    if execution:
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "state",
                                    "execution": execution.model_dump(),
                                }
                            )
                        )

            except asyncio.TimeoutError:
                execution = _in_memory_executions.get(execution_id)
                if execution and execution.status in ("completed", "cancelled", "failed"):
                    break
                await websocket.send_text(json.dumps({"type": "ping"}))

    except WebSocketDisconnect:
        pass
    finally:
        if execution_id in _active_websockets:
            try:
                _active_websockets[execution_id].remove(websocket)
            except ValueError:
                pass


@router.get("/styles", response_model=dict[str, Any])
async def get_visualization_styles():
    """Get available visualization styles and themes."""
    return {
        "styles": [
            {
                "id": "circuit",
                "name": "Circuit Diagram",
                "description": "Standard quantum circuit notation",
            },
            {
                "id": "timeline",
                "name": "Timeline View",
                "description": "Gates arranged by time step",
            },
            {
                "id": "bloch",
                "name": "Bloch Sphere",
                "description": "Single qubit state visualization",
            },
        ],
        "themes": [
            {"id": "dark", "name": "Dark Mode", "primary": "#6366f1"},
            {"id": "light", "name": "Light Mode", "primary": "#4f46e5"},
        ],
        "gate_colors": {
            "H": "#10b981",
            "X": "#ef4444",
            "Y": "#f59e0b",
            "Z": "#3b82f6",
            "RX": "#8b5cf6",
            "RY": "#ec4899",
            "RZ": "#06b6d4",
            "CNOT": "#6366f1",
            "CZ": "#6366f1",
            "SWAP": "#84cc16",
            "Measure": "#f97316",
        },
    }

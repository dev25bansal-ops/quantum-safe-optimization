"""Algorithm and backend listing endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter()


class AlgorithmInfo(BaseModel):
    """Information about an available algorithm."""

    name: str
    display_name: str
    description: str
    category: str
    supported_backends: list[str]
    parameters: dict[str, dict]
    version: str = "1.0.0"


class AlgorithmListResponse(BaseModel):
    """List of available algorithms."""

    algorithms: list[AlgorithmInfo]
    total: int


class BackendInfo(BaseModel):
    """Information about a quantum backend."""

    name: str
    display_name: str
    provider: str
    backend_type: str  # "simulator" or "hardware"
    qubits: int | None
    status: str  # "online", "offline", "maintenance"
    description: str


class BackendListResponse(BaseModel):
    """List of available backends."""

    backends: list[BackendInfo]
    total: int


# Static algorithm definitions (in production, load from registry)
ALGORITHMS: dict[str, AlgorithmInfo] = {
    "qaoa": AlgorithmInfo(
        name="qaoa",
        display_name="QAOA",
        description="Quantum Approximate Optimization Algorithm for combinatorial optimization",
        category="optimization",
        supported_backends=["qiskit_aer", "ibm_quantum", "ionq"],
        parameters={
            "p": {"type": "integer", "min": 1, "max": 10, "default": 1, "description": "Number of QAOA layers"},
            "optimizer": {"type": "string", "options": ["COBYLA", "SPSA", "ADAM"], "default": "COBYLA"},
            "max_iterations": {"type": "integer", "min": 1, "max": 1000, "default": 100},
        },
    ),
    "vqe": AlgorithmInfo(
        name="vqe",
        display_name="VQE",
        description="Variational Quantum Eigensolver for finding ground state energies",
        category="chemistry",
        supported_backends=["qiskit_aer", "ibm_quantum", "ionq"],
        parameters={
            "ansatz": {"type": "string", "options": ["RY", "UCCSD", "HEA"], "default": "RY"},
            "optimizer": {"type": "string", "options": ["COBYLA", "SPSA", "L-BFGS-B"], "default": "COBYLA"},
            "max_iterations": {"type": "integer", "min": 1, "max": 1000, "default": 100},
        },
    ),
    "grover": AlgorithmInfo(
        name="grover",
        display_name="Grover's Search",
        description="Quantum search algorithm for unstructured search problems",
        category="search",
        supported_backends=["qiskit_aer", "ibm_quantum"],
        parameters={
            "iterations": {"type": "integer", "min": 1, "max": 100, "default": None, "description": "Auto-calculated if not specified"},
        },
    ),
    "qsvm": AlgorithmInfo(
        name="qsvm",
        display_name="Quantum SVM",
        description="Quantum Support Vector Machine for classification",
        category="machine_learning",
        supported_backends=["qiskit_aer", "ibm_quantum"],
        parameters={
            "feature_map": {"type": "string", "options": ["ZZFeatureMap", "PauliFeatureMap"], "default": "ZZFeatureMap"},
            "kernel": {"type": "string", "options": ["quantum", "precomputed"], "default": "quantum"},
        },
    ),
}

BACKENDS: dict[str, BackendInfo] = {
    "qiskit_aer": BackendInfo(
        name="qiskit_aer",
        display_name="Qiskit Aer Simulator",
        provider="local",
        backend_type="simulator",
        qubits=32,
        status="online",
        description="High-performance local quantum simulator",
    ),
    "ibm_quantum": BackendInfo(
        name="ibm_quantum",
        display_name="IBM Quantum",
        provider="ibm",
        backend_type="hardware",
        qubits=127,
        status="online",
        description="IBM quantum hardware via Qiskit Runtime",
    ),
    "ionq": BackendInfo(
        name="ionq",
        display_name="IonQ Trapped Ion",
        provider="ionq",
        backend_type="hardware",
        qubits=32,
        status="online",
        description="IonQ trapped ion quantum computer",
    ),
    "rigetti": BackendInfo(
        name="rigetti",
        display_name="Rigetti Aspen",
        provider="rigetti",
        backend_type="hardware",
        qubits=80,
        status="maintenance",
        description="Rigetti superconducting quantum processor",
    ),
}


@router.get("/algorithms", response_model=AlgorithmListResponse)
async def list_algorithms() -> AlgorithmListResponse:
    """
    List all available quantum optimization algorithms.
    """
    return AlgorithmListResponse(
        algorithms=list(ALGORITHMS.values()),
        total=len(ALGORITHMS),
    )


@router.get("/algorithms/{name}", response_model=AlgorithmInfo)
async def get_algorithm(name: str) -> AlgorithmInfo:
    """
    Get details of a specific algorithm.
    """
    algorithm = ALGORITHMS.get(name.lower())
    
    if algorithm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Algorithm '{name}' not found",
        )
    
    return algorithm


@router.get("/backends", response_model=BackendListResponse)
async def list_backends() -> BackendListResponse:
    """
    List all available quantum backends.
    """
    return BackendListResponse(
        backends=list(BACKENDS.values()),
        total=len(BACKENDS),
    )


@router.get("/backends/{name}", response_model=BackendInfo)
async def get_backend(name: str) -> BackendInfo:
    """
    Get details of a specific backend.
    """
    backend = BACKENDS.get(name.lower())
    
    if backend is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backend '{name}' not found",
        )
    
    return backend

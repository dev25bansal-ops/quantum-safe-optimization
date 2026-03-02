"""Job-related Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .crypto import CryptoSettings


class JobStatus(str, Enum):
    """Possible job statuses."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class QAOAMaxCutConfig(BaseModel):
    """QAOA MaxCut problem configuration."""

    type: Literal["qaoa_maxcut"] = "qaoa_maxcut"
    graph: dict[str, Any] = Field(
        ...,
        description="Graph definition with nodes and edges",
    )
    weighted: bool = Field(
        default=False,
        description="Whether edges have weights",
    )
    edge_weights: list[float] | None = Field(
        default=None,
        description="Optional edge weights (must match edges count)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "qaoa_maxcut",
                "graph": {"nodes": 4, "edges": [[0, 1], [1, 2], [2, 3], [3, 0], [0, 2]]},
                "weighted": False,
            }
        }
    )


class VQEMolecularHamiltonianConfig(BaseModel):
    """VQE molecular Hamiltonian configuration."""

    type: Literal["vqe_molecular_hamiltonian"] = "vqe_molecular_hamiltonian"
    molecule: str = Field(
        ...,
        description="Molecular formula or identifier",
    )
    basis: str = Field(
        default="sto-3g",
        description="Basis set for Hamiltonian construction",
    )
    geometry: list[list[float]] = Field(
        ...,
        description="Atomic positions in Angstroms as [[x, y, z], ...]",
    )
    charge: int = Field(
        default=0,
        description="Molecular charge",
    )
    spin: int = Field(
        default=0,
        description="Total spin (multiplicity - 1)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "vqe_molecular_hamiltonian",
                "molecule": "H2",
                "basis": "sto-3g",
                "geometry": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.735]],
                "charge": 0,
                "spin": 0,
            }
        }
    )


class AnnealingQUBOConfig(BaseModel):
    """Quantum annealing QUBO configuration."""

    type: Literal["annealing_qubo"] = "annealing_qubo"
    q_matrix: list[list[float]] = Field(
        ...,
        description="QUBO coefficient matrix",
    )
    num_qubits: int = Field(
        ...,
        description="Number of qubits (variables)",
    )
    offset: float = Field(
        default=0.0,
        description="Constant offset in objective",
    )

    @field_validator("q_matrix")
    @classmethod
    def validate_q_matrix(cls, v: list[list[float]], info: Any) -> list[list[float]]:
        num_qubits = info.data.get("num_qubits")
        if num_qubits is not None:
            if len(v) != num_qubits or any(len(row) != num_qubits for row in v):
                raise ValueError("Q matrix must be square with size num_qubits x num_qubits")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "annealing_qubo",
                "q_matrix": [
                    [1.0, -0.5, 0.0],
                    [-0.5, 1.0, -0.5],
                    [0.0, -0.5, 1.0],
                ],
                "num_qubits": 3,
                "offset": 0.0,
            }
        }
    )


class GenericOptimizationConfig(BaseModel):
    """Generic optimization problem configuration."""

    type: Literal["generic_optimization"] = "generic_optimization"
    objective_function: str = Field(
        ...,
        description="Type of objective function",
    )
    variables: int = Field(
        ...,
        description="Number of decision variables",
    )
    variable_type: Literal["binary", "integer", "continuous"] = Field(
        default="binary",
        description="Type of decision variables",
    )
    bounds: list[list[float]] | None = Field(
        default=None,
        description="Variable bounds [[lower1, upper1], [lower2, upper2], ...]",
    )
    constraints: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of constraint definitions",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "generic_optimization",
                "objective_function": "portfolio_optimization",
                "variables": 10,
                "variable_type": "continuous",
                "bounds": [[0.0, 1.0], [0.0, 1.0], [0.0, 1.0], [0.0, 1.0], [0.0, 1.0]],
                "constraints": [{"type": "equality", "expression": "sum(weights) = 1.0"}],
            }
        }
    )


ProblemConfig = (
    QAOAMaxCutConfig
    | VQEMolecularHamiltonianConfig
    | AnnealingQUBOConfig
    | GenericOptimizationConfig
)


class JobCreate(BaseModel):
    """Request body for creating a new job."""

    algorithm: str = Field(
        ...,
        description="Name of the optimization algorithm to use",
    )
    backend: str = Field(
        ...,
        description="Quantum backend to execute on",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Algorithm-specific parameters",
    )
    crypto: CryptoSettings = Field(
        default_factory=CryptoSettings,
        description="Cryptographic settings for the job",
    )
    problem_config: ProblemConfig = Field(
        ...,
        description="Problem configuration (discriminated union type)",
    )
    name: str | None = Field(
        None,
        max_length=255,
        description="Optional human-readable job name",
    )
    priority: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Job priority (1=lowest, 10=highest)",
    )
    callback_url: str | None = Field(
        None,
        description="Webhook URL to call when job completes",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "algorithm": "qaoa",
                "backend": "qiskit_aer",
                "parameters": {"p": 2, "optimizer": "COBYLA", "max_iterations": 100},
                "problem_config": {
                    "type": "qaoa_maxcut",
                    "graph": {"nodes": 4, "edges": [[0, 1], [1, 2], [2, 3], [3, 0], [0, 2]]},
                    "weighted": False,
                },
                "name": "MaxCut-4Nodes-Trial1",
                "priority": 5,
            }
        }
    )


class JobResponse(BaseModel):
    """Response model for job details."""

    id: UUID
    tenant_id: str
    name: str | None
    algorithm: str
    backend: str
    parameters: dict[str, Any]
    status: JobStatus
    priority: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None = None
    progress: float | None = Field(None, ge=0, le=100)
    estimated_completion: datetime | None = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "tenant_id": "tenant-123",
                "name": "MaxCut-4Nodes-Trial1",
                "algorithm": "qaoa",
                "backend": "qiskit_aer",
                "parameters": {"p": 2, "optimizer": "COBYLA"},
                "status": "completed",
                "priority": 5,
                "created_at": "2024-01-15T10:30:00Z",
                "started_at": "2024-01-15T10:30:05Z",
                "completed_at": "2024-01-15T10:30:45Z",
                "error_message": None,
                "progress": 100.0,
                "estimated_completion": "2024-01-15T10:30:45Z",
            }
        },
    )


class JobListResponse(BaseModel):
    """Paginated list of jobs."""

    jobs: list[JobResponse]
    total: int
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        """Check if there are more results available."""
        return self.offset + len(self.jobs) < self.total

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "jobs": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "tenant_id": "tenant-123",
                        "name": "MaxCut-4Nodes-Trial1",
                        "algorithm": "qaoa",
                        "backend": "qiskit_aer",
                        "parameters": {"p": 2, "optimizer": "COBYLA"},
                        "status": "completed",
                        "priority": 5,
                        "created_at": "2024-01-15T10:30:00Z",
                        "started_at": "2024-01-15T10:30:05Z",
                        "completed_at": "2024-01-15T10:30:45Z",
                        "error_message": None,
                        "progress": 100.0,
                    }
                ],
                "total": 1,
                "limit": 20,
                "offset": 0,
            }
        }
    )


class JobProgress(BaseModel):
    """Job progress update model."""

    job_id: UUID
    status: JobStatus
    progress: float = Field(ge=0, le=100)
    message: str | None = None
    current_iteration: int | None = None
    total_iterations: int | None = None
    timestamp: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "running",
                "progress": 45.0,
                "message": "Optimizing parameters",
                "current_iteration": 45,
                "total_iterations": 100,
                "timestamp": "2024-01-15T10:30:25Z",
            }
        }
    )

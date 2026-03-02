"""Result-related Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QuantumMetrics(BaseModel):
    """Quantum execution metrics."""

    circuit_depth: int = Field(..., description="Depth of the quantum circuit")
    gate_count: int = Field(..., description="Total number of gates")
    qubit_count: int = Field(..., description="Number of qubits used")
    shots: int = Field(..., description="Number of measurement shots")
    execution_time_ms: float = Field(..., description="Backend execution time in milliseconds")
    queue_time_ms: float | None = Field(None, description="Time spent in queue")
    transpilation_time_ms: float | None = None

    readout_error: float | None = None
    gate_error: float | None = None
    t1_time_us: float | None = None
    t2_time_us: float | None = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "circuit_depth": 120,
                "gate_count": 480,
                "qubit_count": 4,
                "shots": 1024,
                "execution_time_ms": 2500.5,
                "queue_time_ms": 150.0,
                "transpilation_time_ms": 25.3,
                "readout_error": 0.012,
                "gate_error": 0.001,
                "t1_time_us": 120.5,
                "t2_time_us": 95.2,
            }
        },
    )


class OptimizationResult(BaseModel):
    """Result of an optimization run."""

    optimal_value: float = Field(..., description="Optimal objective function value")
    optimal_solution: dict[str, Any] = Field(..., description="Optimal solution vector/bitstring")
    convergence_history: list[float] = Field(
        default_factory=list,
        description="Objective values over iterations",
    )
    iterations: int = Field(..., description="Number of optimization iterations")
    converged: bool = Field(..., description="Whether optimization converged")

    solution_quality: float | None = Field(
        None,
        ge=0,
        le=1,
        description="Solution quality metric (0-1)",
    )
    approximation_ratio: float | None = Field(
        None,
        description="Ratio to known optimal (if available)",
    )
    confidence_interval: tuple[float, float] | None = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "optimal_value": -5.0,
                "optimal_solution": {"bitstring": "0101", "cut_edges": [1, 2, 4]},
                "convergence_history": [-2.5, -3.8, -4.5, -4.9, -5.0],
                "iterations": 100,
                "converged": True,
                "solution_quality": 0.95,
                "approximation_ratio": 0.98,
                "confidence_interval": [-5.1, -4.9],
            }
        },
    )


class CountsResult(BaseModel):
    """Measurement counts from quantum execution."""

    counts: dict[str, int] = Field(
        ...,
        description="Bitstring counts",
        examples=[{"0101": 512, "1010": 256, "0011": 128, "1100": 128}],
    )
    probabilities: dict[str, float] = Field(
        ...,
        description="Bitstring probabilities",
        examples=[{"0101": 0.5, "1010": 0.25, "0011": 0.125, "1100": 0.125}],
    )
    most_likely: str = Field(
        ...,
        description="Most frequently measured bitstring",
        examples=["0101"],
    )
    entropy: float | None = Field(None, description="Shannon entropy of distribution")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "counts": {"0101": 512, "1010": 256, "0011": 128, "1100": 128},
                "probabilities": {"0101": 0.5, "1010": 0.25, "0011": 0.125, "1100": 0.125},
                "most_likely": "0101",
                "entropy": 1.75,
            }
        }
    )


class JobResultsResponse(BaseModel):
    """Complete job results response."""

    job_id: UUID
    algorithm: str
    backend: str
    status: str = "completed"

    optimization: OptimizationResult | None = None
    counts: CountsResult | None = None
    raw_results: dict[str, Any] | None = Field(
        None,
        description="Raw backend results (backend-specific format)",
    )

    quantum_metrics: QuantumMetrics

    total_time_ms: float
    created_at: datetime
    completed_at: datetime

    circuit_diagram_url: str | None = None
    results_file_url: str | None = None

    result_artifact_id: UUID | None = None
    signature: str | None = Field(None, description="Hex-encoded signature of the result")
    is_verified: bool = False
    is_encrypted: bool = True

    random_seed: int | None = None
    backend_version: str | None = None
    qsop_version: str = "1.0.0"

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "algorithm": "qaoa",
                "backend": "qiskit_aer",
                "status": "completed",
                "optimization": {
                    "optimal_value": -5.0,
                    "optimal_solution": {"bitstring": "0101", "cut_edges": [1, 2, 4]},
                    "convergence_history": [-2.5, -3.8, -4.5, -4.9, -5.0],
                    "iterations": 100,
                    "converged": True,
                    "solution_quality": 0.95,
                    "approximation_ratio": 0.98,
                },
                "counts": {
                    "counts": {"0101": 512, "1010": 256, "0011": 128, "1100": 128},
                    "probabilities": {"0101": 0.5, "1010": 0.25, "0011": 0.125, "1100": 0.125},
                    "most_likely": "0101",
                    "entropy": 1.75,
                },
                "quantum_metrics": {
                    "circuit_depth": 120,
                    "gate_count": 480,
                    "qubit_count": 4,
                    "shots": 1024,
                    "execution_time_ms": 2500.5,
                    "queue_time_ms": 150.0,
                },
                "total_time_ms": 2675.8,
                "created_at": "2024-01-15T10:30:00Z",
                "completed_at": "2024-01-15T10:30:45Z",
                "circuit_diagram_url": "s3://artifacts/jobs/550e8400-e29b-41d4-a716-446655440000/circuit.png",
                "results_file_url": "s3://artifacts/jobs/550e8400-e29b-41d4-a716-446655440000/results.json",
                "result_artifact_id": "660e8400-e29b-41d4-a716-446655440001",
                "signature": "a1b2c3d4e5f6...",
                "is_verified": True,
                "is_encrypted": True,
                "random_seed": 42,
                "backend_version": "0.45.0",
                "qsop_version": "1.0.0",
            }
        },
    )


class IntermediateResult(BaseModel):
    """Intermediate result during job execution."""

    job_id: UUID
    iteration: int
    current_value: float
    current_solution: dict[str, Any] | None = None
    timestamp: datetime
    metrics: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "iteration": 50,
                "current_value": -4.5,
                "current_solution": {"bitstring": "0101"},
                "timestamp": "2024-01-15T10:30:25Z",
                "metrics": {"gradient_norm": 0.01, "parameter_change": 0.001},
            }
        }
    )

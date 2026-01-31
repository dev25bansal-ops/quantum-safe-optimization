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
    
    # Error metrics (if available)
    readout_error: float | None = None
    gate_error: float | None = None
    t1_time_us: float | None = None
    t2_time_us: float | None = None

    model_config = ConfigDict(from_attributes=True)


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
    
    # Additional solution info
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

    model_config = ConfigDict(from_attributes=True)


class CountsResult(BaseModel):
    """Measurement counts from quantum execution."""

    counts: dict[str, int] = Field(..., description="Bitstring counts")
    probabilities: dict[str, float] = Field(..., description="Bitstring probabilities")
    most_likely: str = Field(..., description="Most frequently measured bitstring")
    entropy: float | None = Field(None, description="Shannon entropy of distribution")


class JobResultsResponse(BaseModel):
    """Complete job results response."""

    job_id: UUID
    algorithm: str
    backend: str
    status: str = "completed"
    
    # Core results
    optimization: OptimizationResult | None = None
    counts: CountsResult | None = None
    raw_results: dict[str, Any] | None = Field(
        None,
        description="Raw backend results (backend-specific format)",
    )
    
    # Metrics
    quantum_metrics: QuantumMetrics
    
    # Timing
    total_time_ms: float
    created_at: datetime
    completed_at: datetime
    
    # Artifacts
    circuit_diagram_url: str | None = None
    results_file_url: str | None = None
    
    # Security
    result_artifact_id: UUID | None = None
    signature: str | None = Field(None, description="Hex-encoded signature of the result")
    is_verified: bool = False
    is_encrypted: bool = True
    
    # Reproducibility
    random_seed: int | None = None
    backend_version: str | None = None
    qsop_version: str = "1.0.0"

    model_config = ConfigDict(from_attributes=True)


class IntermediateResult(BaseModel):
    """Intermediate result during job execution."""

    job_id: UUID
    iteration: int
    current_value: float
    current_solution: dict[str, Any] | None = None
    timestamp: datetime
    metrics: dict[str, Any] = Field(default_factory=dict)

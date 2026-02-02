"""
Pydantic models for optimization jobs.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job execution status."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProblemType(str, Enum):
    """Supported optimization problem types."""
    QAOA = "QAOA"
    VQE = "VQE"
    ANNEALING = "ANNEALING"


class BackendType(str, Enum):
    """Supported quantum backends."""
    LOCAL_SIMULATOR = "local_simulator"
    IBM_QUANTUM = "ibm_quantum"
    AWS_BRAKET = "aws_braket"
    AZURE_QUANTUM = "azure_quantum"
    DWAVE = "dwave"


# QAOA Configuration Models

class MaxCutConfig(BaseModel):
    """Configuration for MaxCut problem."""
    graph_edges: List[List[int]] = Field(..., description="List of edges as [node1, node2] pairs")
    weights: Optional[List[float]] = Field(None, description="Edge weights (optional)")


class PortfolioConfig(BaseModel):
    """Configuration for Portfolio Optimization problem."""
    expected_returns: List[float] = Field(..., description="Expected returns for each asset")
    covariance_matrix: List[List[float]] = Field(..., description="Covariance matrix")
    risk_factor: float = Field(default=0.5, ge=0, le=1, description="Risk aversion factor")
    budget: int = Field(default=2, ge=1, description="Number of assets to select")


class TSPConfig(BaseModel):
    """Configuration for Traveling Salesman Problem."""
    distance_matrix: List[List[float]] = Field(..., description="Distance matrix between cities")
    num_cities: int = Field(..., ge=2, description="Number of cities")


class GraphColoringConfig(BaseModel):
    """Configuration for Graph Coloring problem."""
    graph_edges: List[List[int]] = Field(..., description="List of edges")
    num_colors: int = Field(default=3, ge=2, description="Number of colors")


class QAOAConfig(BaseModel):
    """QAOA algorithm configuration."""
    problem_type: str = Field(..., description="max_cut, portfolio, tsp, graph_coloring")
    problem_data: Dict[str, Any] = Field(..., description="Problem-specific data")
    layers: int = Field(default=2, ge=1, le=20, description="Number of QAOA layers (p)")
    optimizer: str = Field(default="COBYLA", description="Classical optimizer")
    max_iterations: int = Field(default=100, ge=1)
    shots: int = Field(default=1024, ge=1)
    initial_params: Optional[List[float]] = Field(None, description="Initial gamma/beta parameters")


# VQE Configuration Models

class MolecularConfig(BaseModel):
    """Configuration for molecular simulation."""
    molecule: str = Field(..., description="Molecule string (e.g., 'H 0 0 0; H 0 0 0.74')")
    basis: str = Field(default="sto-3g", description="Basis set")
    charge: int = Field(default=0)
    multiplicity: int = Field(default=1)


class IsingModelConfig(BaseModel):
    """Configuration for Ising model."""
    h_coeffs: List[float] = Field(..., description="Local field coefficients")
    J_coeffs: Dict[str, float] = Field(..., description="Coupling coefficients as 'i,j': value")


class HeisenbergConfig(BaseModel):
    """Configuration for Heisenberg model."""
    num_sites: int = Field(..., ge=2, description="Number of lattice sites")
    Jx: float = Field(default=1.0, description="XX coupling")
    Jy: float = Field(default=1.0, description="YY coupling")
    Jz: float = Field(default=1.0, description="ZZ coupling")
    periodic: bool = Field(default=True, description="Periodic boundary conditions")


class VQEConfig(BaseModel):
    """VQE algorithm configuration."""
    hamiltonian_type: str = Field(..., description="molecular, ising, heisenberg")
    hamiltonian_data: Dict[str, Any] = Field(..., description="Hamiltonian-specific data")
    ansatz: str = Field(default="UCCSD", description="Ansatz type")
    optimizer: str = Field(default="L-BFGS-B", description="Classical optimizer")
    max_iterations: int = Field(default=200, ge=1)
    convergence_threshold: float = Field(default=1e-6, gt=0)
    shots: int = Field(default=1024, ge=1)


# Annealing Configuration Models

class QUBOConfig(BaseModel):
    """Configuration for QUBO problem."""
    Q_matrix: Dict[str, float] = Field(..., description="QUBO matrix as '(i,j)': value")
    offset: float = Field(default=0.0)


class AnnealingConfig(BaseModel):
    """Quantum Annealing configuration."""
    problem_type: str = Field(..., description="qubo, ising, constrained")
    problem_data: Dict[str, Any] = Field(..., description="Problem-specific data")
    num_reads: int = Field(default=1000, ge=1, description="Number of samples")
    annealing_time: int = Field(default=20, ge=1, description="Annealing time in microseconds")
    chain_strength: Optional[float] = Field(None, description="Chain strength for embedding")
    use_postprocessing: bool = Field(default=True)


# Job Models

class JobSubmission(BaseModel):
    """Job submission request."""
    problem_type: ProblemType = Field(..., description="QAOA, VQE, or ANNEALING")
    config: Dict[str, Any] = Field(..., description="Algorithm configuration")
    backend: BackendType = Field(default=BackendType.LOCAL_SIMULATOR)
    priority: int = Field(default=5, ge=1, le=10)
    callback_url: Optional[str] = Field(None, description="Webhook URL for completion notification")
    encrypted_payload: Optional[str] = Field(None, description="ML-KEM encrypted problem data")
    tags: Optional[List[str]] = Field(default_factory=list)


class JobResponse(BaseModel):
    """Job response model."""
    job_id: str
    status: str
    problem_type: str
    backend: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    message: Optional[str] = None


class JobListResponse(BaseModel):
    """Response for job listing."""
    jobs: List[JobResponse]
    total: int
    limit: int
    offset: int


# Result Models

class OptimizationResult(BaseModel):
    """Base optimization result."""
    optimal_value: float
    optimal_solution: Any
    iterations: int
    execution_time_ms: int
    backend_info: Dict[str, Any] = Field(default_factory=dict)


class QAOAResult(OptimizationResult):
    """QAOA-specific result."""
    optimal_params: Dict[str, List[float]] = Field(..., description="Optimal gamma/beta")
    bitstring: str
    probability: float
    convergence_history: List[float]
    expectation_values: List[float]


class VQEResult(OptimizationResult):
    """VQE-specific result."""
    ground_state_energy: float
    optimal_params: List[float]
    convergence_history: List[float]
    wavefunction_coeffs: Optional[List[complex]] = None


class AnnealingResult(OptimizationResult):
    """Annealing-specific result."""
    samples: List[Dict[str, Any]]
    energies: List[float]
    num_occurrences: List[int]
    timing_info: Dict[str, float]


# Encrypted Models

class EncryptedJobSubmission(BaseModel):
    """Job submission with PQC encryption."""
    encrypted_config: str = Field(..., description="ML-KEM encrypted configuration")
    signature: str = Field(..., description="ML-DSA signature of encrypted payload")
    sender_public_key: str = Field(..., description="Sender's public key for verification")
    algorithm_hint: str = Field(default="ML-KEM-768+AES-256-GCM")


class EncryptedJobResult(BaseModel):
    """Encrypted job result."""
    job_id: str
    encrypted_result: str = Field(..., description="ML-KEM encrypted result")
    signature: str = Field(..., description="Server's ML-DSA signature")
    encrypted_at: str

"""
Pydantic Validation Models for Problem Configurations

Provides strongly-typed, validated configuration models for all
quantum optimization problem types (QAOA, VQE, ANNEALING).

Replaces the unsafe `problem_config: dict[str, Any]` with
discriminated union models for comprehensive validation.

Benefits:
- Type safety with IDE autocomplete
- Automatic JSON schema generation for OpenAPI
- Comprehensive validation with clear error messages
- No more arbitrary exceptions from malformed configs
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


# Base problem configuration
class BaseProblemConfig(BaseModel):
    """Base configuration for all problem types."""

    problem: str
    backend: str = "local_simulator"


# QAOA Configuration Models
class QAOAMaxCutConfig(BaseProblemConfig):
    """Configuration for MaxCut problem using QAOA."""

    problem: Literal["maxcut"] = "maxcut"
    edges: list[tuple[int, int]] = Field(
        default_factory=lambda: [(0, 1), (1, 2), (2, 0)],
        min_length=1,
        description="List of graph edges as (i, j) tuples",
    )
    weights: list[float] | None = Field(
        default=None,
        description="Optional edge weights (must match edges length)",
    )
    num_nodes: int | None = Field(
        default=None,
        gt=0,
        description="Number of nodes (derived from edges if not provided)",
    )
    edge_probability: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Probability for random graph generation (if using num_nodes)",
    )

    @field_validator("weights")
    @classmethod
    def validate_weights(
        cls,
        v: list[float] | None,
        info,
    ) -> list[float] | None:
        if v is not None:
            if len(v) != len(info.data.get("edges", [])):
                raise ValueError(
                    f"weights length ({len(v)}) must match edges length "
                    f"({len(info.data.get('edges', []))})"
                )
        return v


class QAOPortfolioConfig(BaseProblemConfig):
    """Configuration for Portfolio Optimization using QAOA."""

    problem: Literal["portfolio"] = "portfolio"
    expected_returns: list[float] = Field(
        default_factory=lambda: [0.1, 0.12, 0.08],
        min_length=2,
        description="Expected returns for each asset",
    )
    covariance_matrix: list[list[float]] = Field(
        default_factory=lambda: [
            [0.1, 0.02, 0.01],
            [0.02, 0.15, 0.03],
            [0.01, 0.03, 0.12],
        ],
        description="Covariance matrix (square matrix)",
    )
    num_assets_to_select: int = Field(
        default=2,
        gt=0,
        description="Number of assets to select in the portfolio",
    )

    @field_validator("covariance_matrix")
    @classmethod
    def validate_covariance_matrix(
        cls,
        v: list[list[float]],
    ) -> list[list[float]]:
        if not v:
            raise ValueError("covariance_matrix cannot be empty")

        n = len(v)
        for row in v:
            if len(row) != n:
                raise ValueError(f"covariance_matrix must be square: got {len(row)}x{n}")
        return v

    @field_validator("num_assets_to_select")
    @classmethod
    def validate_num_assets_to_select(
        cls,
        v: int,
        info,
    ) -> int:
        num_assets = len(info.data.get("expected_returns", []))
        if v > num_assets:
            raise ValueError(
                f"num_assets_to_select ({v}) cannot exceed number of assets ({num_assets})"
            )
        return v


class QAOATSPConfig(BaseProblemConfig):
    """Configuration for Traveling Salesman Problem using QAOA."""

    problem: Literal["tsp"] = "tsp"
    distance_matrix: list[list[float]] = Field(
        description="Distance matrix (square matrix)",
        min_length=2,
    )
    num_cities: int | None = Field(
        default=None,
        gt=1,
        description="Number of cities (derived from distance_matrix if not provided)",
    )

    @field_validator("distance_matrix")
    @classmethod
    def validate_distance_matrix(
        cls,
        v: list[list[float]],
    ) -> list[list[float]]:
        n = len(v)
        for i, row in enumerate(v):
            if len(row) != n:
                raise ValueError(
                    f"distance_matrix[{i}] has {len(row)} elements, expected {n} (square matrix)"
                )
            for j, dist in enumerate(row):
                if i == j and dist != 0.0:
                    raise ValueError(f"distance_matrix[{i}][{i}] must be 0 (diagonal)")
                if dist < 0:
                    raise ValueError(f"distance_matrix[{i}][{j}] must be non-negative, got {dist}")
        return v


# VQE Configuration Models
class VQEMolecularHamiltonianConfig(BaseProblemConfig):
    """Configuration for molecular Hamiltonian problems using VQE."""

    problem: Literal["h2", "lih", "h2o", "water"] = Field(description="Molecule type")
    bond_length: float = Field(
        default=0.74,
        gt=0.0,
        description="Bond length in Angstroms",
    )
    basis_set: str = Field(
        default="sto-3g",
        description="Basis set for quantum chemistry calculation",
    )


class VQEIsingHamiltonianConfig(BaseProblemConfig):
    """Configuration for Ising model Hamiltonian using VQE."""

    problem: Literal["ising"] = "ising"
    num_spins: int = Field(
        default=4,
        gt=0,
        description="Number of spins in the Ising model",
    )
    coupling_strength: float = Field(
        default=1.0,
        description="Coupling strength between spins",
    )
    transverse_field: float = Field(
        default=0.5,
        description="Strength of transverse field",
    )


# Annealing Configuration Models
class AnnealingQUBOConfig(BaseProblemConfig):
    """Configuration for QUBO problems using Quantum/Simulated Annealing."""

    problem: Literal["qubo"] = "qubo"
    qubo_matrix: dict[tuple[int, int], float] = Field(
        description="QUBO matrix as dict {(i, j): value}",
        min_length=1,
    )
    num_variables: int | None = Field(
        default=None,
        gt=0,
        description="Number of variables (derived from qubo_matrix if not provided)",
    )

    @field_validator("qubo_matrix")
    @classmethod
    def validate_qubo_matrix(
        cls,
        v: dict[tuple[int, int], float],
    ) -> dict[tuple[int, int], float]:
        if not v:
            raise ValueError("qubo_matrix cannot be empty")

        for (i, j), val in v.items():
            if i < 0 or j < 0:
                raise ValueError(f"QUBO indices cannot be negative: ({i}, {j})")

        return v


# Discriminated union for all problem configs
ProblemConfig = (
    QAOAMaxCutConfig
    | QAOPortfolioConfig
    | QAOATSPConfig
    | VQEMolecularHamiltonianConfig
    | VQEIsingHamiltonianConfig
    | AnnealingQUBOConfig
)


# Algorithm parameter models
class QAOAParameters(BaseModel):
    """Parameters for QAOA optimization."""

    layers: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Number of QAOA layers (p)",
    )
    optimizer: Literal["COBYLA", "SPSA", "ADAM", "L-BFGS-B"] = Field(
        default="COBYLA",
        description="Classical optimizer",
    )
    shots: int = Field(
        default=1000,
        ge=100,
        le=100000,
        description="Number of shots per measurement",
    )
    max_iterations: int = Field(
        default=100,
        ge=10,
        le=10000,
        description="Maximum optimization iterations",
    )


class VQEParameters(BaseModel):
    """Parameters for VQE optimization."""

    optimizer: Literal["COBYLA", "SPSA", "ADAM", "L-BFGS-B"] = Field(
        default="COBYLA",
        description="Classical optimizer",
    )
    shots: int = Field(
        default=1000,
        ge=100,
        le=100000,
        description="Number of shots per measurement",
    )
    max_iterations: int = Field(
        default=100,
        ge=10,
        le=10000,
        description="Maximum optimization iterations",
    )
    ansatz_type: Literal["UCCSD", "HardwareEfficient", "TwoLocal"] = Field(
        default="UCCSD",
        description="Variational ansatz type",
    )
    ansatz_layers: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Number of ansatz layers",
    )


class AnnealingParameters(BaseModel):
    """Parameters for Quantum/Simulated Annealing."""

    num_reads: int = Field(
        default=1000,
        ge=10,
        le=100000,
        description="Number of annealing runs",
    )
    schedule: Literal["linear", "quadratic", "geometric"] = Field(
        default="linear",
        description="Annealing schedule type",
    )
    initial_temperature: float = Field(
        default=10.0,
        gt=0.0,
        description="Initial temperature",
    )
    final_temperature: float = Field(
        default=0.001,
        gt=0.0,
        description="Final temperature",
    )


# Discriminated union for algorithm parameters
AlgorithmParameters = QAOAParameters | VQEParameters | AnnealingParameters


# Simulator configuration models
class SimulatorConfig(BaseModel):
    """Configuration for quantum simulators."""

    simulator_type: Literal["statevector", "qasm", "aer"] = Field(
        default="statevector",
        description="Simulator type",
    )
    noise_model: Literal["ideal", "thermal", "dephasing", "bit_flip"] = Field(
        default="ideal",
        description="Noise model",
    )
    enable_error_mitigation: bool = Field(
        default=False,
        description="Enable quantum error mitigation",
    )
    single_qubit_error_rate: float = Field(
        default=0.001,
        ge=0.0,
        le=0.1,
        description="Single-qubit error rate (if using noise)",
    )
    two_qubit_error_rate: float = Field(
        default=0.01,
        ge=0.0,
        le=0.1,
        description="Two-qubit error rate (if using noise)",
    )


# Complete job submission configuration
class ValidatedJobSubmissionConfig(BaseModel):
    """
    Complete validated configuration for job submission.

    This replaces the unsafe JobSubmissionRequest.use_config field
    with fully validated, type-safe configuration.
    """

    problem_type: Literal["QAOA", "VQE", "ANNEALING"]
    problem_config: ProblemConfig
    parameters: AlgorithmParameters
    backend: str = "local_simulator"
    simulator_config: SimulatorConfig | None = None
    encrypt_result: bool = False
    callback_url: str | None = None
    priority: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10] = 5

    @field_validator("backend")
    @classmethod
    def validate_backend(
        cls,
        v: str,
        info,
    ) -> str:
        """Validate backend is compatible with problem type."""
        problem_type = info.data.get("problem_type")

        valid_backends = {
            "QAOA": ["local_simulator", "advanced_simulator", "ibm_quantum"],
            "VQE": ["local_simulator", "advanced_simulator", "ibm_quantum"],
            "ANNEALING": [
                "local_simulator",
                "advanced_simulator",
                "dwave_leap",
                "aws_braket",
            ],
        }

        if problem_type in valid_backends and v not in valid_backends[problem_type]:
            raise ValueError(
                f"Backend '{v}' not valid for problem type '{problem_type}'. "
                f"Valid backends: {valid_backends[problem_type]}"
            )

        return v


# Type hints for request/response models
def get_problem_config_model(problem_type: str, problem: str) -> type[BaseModel]:
    """Get the appropriate Pydantic model for a problem config."""
    models = {
        "QAOA": {
            "maxcut": QAOAMaxCutConfig,
            "portfolio": QAOPortfolioConfig,
            "tsp": QAOATSPConfig,
        },
        "VQE": {
            "h2": VQEMolecularHamiltonianConfig,
            "lih": VQEMolecularHamiltonianConfig,
            "h2o": VQEMolecularHamiltonianConfig,
            "water": VQEMolecularHamiltonianConfig,
            "ising": VQEIsingHamiltonianConfig,
        },
        "ANNEALING": {
            "qubo": AnnealingQUBOConfig,
        },
    }

    if problem_type in models and problem in models[problem_type]:
        return models[problem_type][problem]

    raise ValueError(f"Invalid problem config: problem_type='{problem_type}', problem='{problem}'")


def get_parameters_model(problem_type: str) -> type[BaseModel]:
    """Get the appropriate Pydantic model for algorithm parameters."""
    models = {
        "QAOA": QAOAParameters,
        "VQE": VQEParameters,
        "ANNEALING": AnnealingParameters,
    }

    if problem_type in models:
        return models[problem_type]

    raise ValueError(f"Invalid problem_type: '{problem_type}'")


# Export all models for EasyAPI schema generation
__all__ = [
    # Base models
    "BaseProblemConfig",
    "ProblemConfig",
    "AlgorithmParameters",
    "SimulatorConfig",
    # QAOA models
    "QAOAMaxCutConfig",
    "QAOPortfolioConfig",
    "QAOATSPConfig",
    "QAOAParameters",
    # VQE models
    "VQEMolecularHamiltonianConfig",
    "VQEIsingHamiltonianConfig",
    "VQEParameters",
    # Annealing models
    "AnnealingQUBOConfig",
    "AnnealingParameters",
    # Validation helpers
    "ValidatedJobSubmissionConfig",
    "get_problem_config_model",
    "get_parameters_model",
]

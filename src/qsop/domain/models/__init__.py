"""
Domain models for the Quantum-Safe Optimization Platform.

This module exports all core domain entities including optimization problems,
jobs, results, and artifacts.
"""

from qsop.domain.models.artifacts import (
    CircuitArtifact,
    EncryptedBlob,
    ParameterSnapshot,
)
from qsop.domain.models.job import (
    JobResult,
    JobSpec,
    JobStatus,
)
from qsop.domain.models.problem import (
    Constraint,
    ConstraintType,
    OptimizationProblem,
    ProblemMetadata,
    Variable,
    VariableType,
)
from qsop.domain.models.result import (
    OptimizationResult,
    QuantumExecutionResult,
)

__all__ = [
    # Problem
    "OptimizationProblem",
    "Variable",
    "VariableType",
    "Constraint",
    "ConstraintType",
    "ProblemMetadata",
    # Job
    "JobStatus",
    "JobSpec",
    "JobResult",
    # Result
    "OptimizationResult",
    "QuantumExecutionResult",
    # Artifacts
    "CircuitArtifact",
    "ParameterSnapshot",
    "EncryptedBlob",
]

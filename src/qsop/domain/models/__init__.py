"""
Domain models for the Quantum-Safe Optimization Platform.

This module exports all core domain entities including optimization problems,
jobs, results, and artifacts.
"""

from qsop.domain.models.problem import (
    OptimizationProblem,
    Variable,
    VariableType,
    Constraint,
    ConstraintType,
    ProblemMetadata,
)
from qsop.domain.models.job import (
    JobStatus,
    JobSpec,
    JobResult,
)
from qsop.domain.models.result import (
    OptimizationResult,
    QuantumExecutionResult,
)
from qsop.domain.models.artifacts import (
    CircuitArtifact,
    ParameterSnapshot,
    EncryptedBlob,
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

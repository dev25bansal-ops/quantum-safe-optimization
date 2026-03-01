"""
Quantum-Safe Optimization Platform (QSOP) - Domain Layer.

This module contains the core domain models, ports (interfaces), and errors
for the quantum-safe optimization platform.
"""

from qsop.domain.errors import (
    ArtifactError,
    CryptoError,
    DomainError,
    JobError,
    KeyStoreError,
    OptimizationError,
    QuantumBackendError,
    ValidationError,
)
from qsop.domain.models import (
    CircuitArtifact,
    Constraint,
    ConstraintType,
    EncryptedBlob,
    JobResult,
    JobSpec,
    JobStatus,
    OptimizationProblem,
    OptimizationResult,
    ParameterSnapshot,
    ProblemMetadata,
    QuantumExecutionResult,
    Variable,
    VariableType,
)
from qsop.domain.ports import (
    ArtifactStore,
    BackendCapabilities,
    DomainEvent,
    EventBus,
    JobStore,
    KEMScheme,
    KeyStore,
    Optimizer,
    QuantumBackend,
    SignatureScheme,
)

__all__ = [
    # Models
    "OptimizationProblem",
    "Variable",
    "VariableType",
    "Constraint",
    "ConstraintType",
    "ProblemMetadata",
    "JobStatus",
    "JobSpec",
    "JobResult",
    "OptimizationResult",
    "QuantumExecutionResult",
    "CircuitArtifact",
    "ParameterSnapshot",
    "EncryptedBlob",
    # Ports
    "Optimizer",
    "QuantumBackend",
    "BackendCapabilities",
    "KEMScheme",
    "SignatureScheme",
    "KeyStore",
    "ArtifactStore",
    "JobStore",
    "EventBus",
    "DomainEvent",
    # Errors
    "DomainError",
    "ValidationError",
    "OptimizationError",
    "QuantumBackendError",
    "CryptoError",
    "KeyStoreError",
    "ArtifactError",
    "JobError",
]

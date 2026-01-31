"""
Quantum-Safe Optimization Platform (QSOP) - Domain Layer.

This module contains the core domain models, ports (interfaces), and errors
for the quantum-safe optimization platform.
"""

from qsop.domain.models import (
    OptimizationProblem,
    Variable,
    VariableType,
    Constraint,
    ConstraintType,
    ProblemMetadata,
    JobStatus,
    JobSpec,
    JobResult,
    OptimizationResult,
    QuantumExecutionResult,
    CircuitArtifact,
    ParameterSnapshot,
    EncryptedBlob,
)
from qsop.domain.ports import (
    Optimizer,
    QuantumBackend,
    BackendCapabilities,
    KEMScheme,
    SignatureScheme,
    KeyStore,
    ArtifactStore,
    JobStore,
    EventBus,
    DomainEvent,
)
from qsop.domain.errors import (
    DomainError,
    ValidationError,
    OptimizationError,
    QuantumBackendError,
    CryptoError,
    KeyStoreError,
    ArtifactError,
    JobError,
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

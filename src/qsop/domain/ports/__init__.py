"""
Domain ports (interfaces) for the Quantum-Safe Optimization Platform.

Ports define the contracts that adapters must implement to integrate with
the domain layer. Following hexagonal architecture principles.
"""

from qsop.domain.ports.artifact_store import ArtifactStore
from qsop.domain.ports.event_bus import DomainEvent, EventBus
from qsop.domain.ports.job_store import JobStore
from qsop.domain.ports.keystore import KeyStore
from qsop.domain.ports.optimizer import Optimizer
from qsop.domain.ports.pqc import KEMScheme, SignatureScheme
from qsop.domain.ports.quantum_backend import BackendCapabilities, QuantumBackend

__all__ = [
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
]

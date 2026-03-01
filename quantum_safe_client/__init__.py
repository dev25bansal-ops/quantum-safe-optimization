"""
QuantumSafe Client SDK - Python client for the QuantumSafe Optimization Platform.

A comprehensive async/sync Python SDK for interacting with the QuantumSafe API.
"""

from quantum_safe_client.client import (
    AsyncQuantumSafeClient,
    QuantumSafeClient,
)
from quantum_safe_client.exceptions import (
    APIError,
    AuthenticationError,
    JobNotFoundError,
    QuantumSafeError,
    RateLimitError,
    ValidationError,
)
from quantum_safe_client.models import (
    AnnealingConfig,
    CostEstimate,
    Job,
    JobStatus,
    JobType,
    QAOAConfig,
    QuantumBackend,
    VQEConfig,
)

__version__ = "1.0.0"
__all__ = [
    # Clients
    "QuantumSafeClient",
    "AsyncQuantumSafeClient",
    # Models
    "Job",
    "JobStatus",
    "JobType",
    "QAOAConfig",
    "VQEConfig",
    "AnnealingConfig",
    "CostEstimate",
    "QuantumBackend",
    # Exceptions
    "QuantumSafeError",
    "AuthenticationError",
    "JobNotFoundError",
    "ValidationError",
    "RateLimitError",
    "APIError",
]

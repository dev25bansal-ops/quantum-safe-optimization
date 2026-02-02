"""
QuantumSafe Client SDK - Python client for the QuantumSafe Optimization Platform.

A comprehensive async/sync Python SDK for interacting with the QuantumSafe API.
"""

from quantum_safe_client.client import (
    QuantumSafeClient,
    AsyncQuantumSafeClient,
)
from quantum_safe_client.models import (
    Job,
    JobStatus,
    JobType,
    QAOAConfig,
    VQEConfig,
    AnnealingConfig,
    CostEstimate,
    QuantumBackend,
)
from quantum_safe_client.exceptions import (
    QuantumSafeError,
    AuthenticationError,
    JobNotFoundError,
    ValidationError,
    RateLimitError,
    APIError,
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

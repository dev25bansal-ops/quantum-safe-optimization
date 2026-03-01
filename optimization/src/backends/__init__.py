"""
Quantum Backend Abstraction Layer

Provides a unified interface for different quantum computing backends:
- IBM Quantum (via Qiskit Runtime)
- AWS Braket (IonQ, Rigetti, IQM, Simulators)
- Azure Quantum (IonQ, Quantinuum, Pasqal)
- D-Wave (Quantum Annealing)
- Local Simulators (Basic and Advanced)

Connection Management:
- Connection pooling and reuse
- Circuit breaker pattern for fault tolerance
- Health monitoring and automatic recovery
- Credential management from environment
"""

from .advanced_simulator import (
    AdvancedLocalSimulator,
    AdvancedSimulatorConfig,
    GradientOptimizer,
    NoiseModel,
    OptimizerType,
    SimulatorType,
    create_advanced_simulator,
)
from .aws import AWSBraketBackend
from .azure import AzureQuantumBackend
from .base import BackendConfig, BackendType, JobResult, JobStatus, QuantumBackend
from .connection_manager import (
    BackendConnectionManager,
    BackendContext,
    BackendCredentials,
    CircuitBreakerConfig,
    ConnectionPoolConfig,
    ConnectionState,
    ProviderStatus,
    RetryConfig,
    get_backend,
    get_connection_manager,
    release_backend,
)
from .dwave import DWaveBackend
from .ibm import IBMQuantumBackend
from .simulator import LocalSimulatorBackend

__all__ = [
    # Base classes
    "QuantumBackend",
    "BackendType",
    "BackendConfig",
    "JobResult",
    "JobStatus",
    # Cloud backends
    "IBMQuantumBackend",
    "AWSBraketBackend",
    "AzureQuantumBackend",
    "DWaveBackend",
    # Local simulators
    "LocalSimulatorBackend",
    "AdvancedLocalSimulator",
    "AdvancedSimulatorConfig",
    "SimulatorType",
    "NoiseModel",
    "OptimizerType",
    "GradientOptimizer",
    "create_advanced_simulator",
    # Connection management
    "BackendConnectionManager",
    "get_connection_manager",
    "get_backend",
    "release_backend",
    "BackendContext",
    "ConnectionState",
    "ProviderStatus",
    "BackendCredentials",
    "ConnectionPoolConfig",
    "CircuitBreakerConfig",
    "RetryConfig",
]

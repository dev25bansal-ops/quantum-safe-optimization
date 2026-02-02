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

from .base import QuantumBackend, BackendType, BackendConfig, JobResult, JobStatus
from .ibm import IBMQuantumBackend
from .aws import AWSBraketBackend
from .azure import AzureQuantumBackend
from .dwave import DWaveBackend
from .simulator import LocalSimulatorBackend
from .advanced_simulator import (
    AdvancedLocalSimulator,
    AdvancedSimulatorConfig,
    SimulatorType,
    NoiseModel,
    OptimizerType,
    GradientOptimizer,
    create_advanced_simulator,
)
from .connection_manager import (
    BackendConnectionManager,
    get_connection_manager,
    get_backend,
    release_backend,
    BackendContext,
    ConnectionState,
    ProviderStatus,
    BackendCredentials,
    ConnectionPoolConfig,
    CircuitBreakerConfig,
    RetryConfig,
)

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

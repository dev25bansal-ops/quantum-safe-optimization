"""
Registry Service for QSOP.

Provides discovery and management of available optimizers and quantum backends,
including algorithm metadata and capabilities.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Type

logger = logging.getLogger(__name__)


class AlgorithmCategory(str, Enum):
    """Categories of optimization algorithms."""
    
    VARIATIONAL = "variational"
    GROVER_BASED = "grover_based"
    ANNEALING = "annealing"
    CLASSICAL = "classical"
    HYBRID = "hybrid"


class ProblemType(str, Enum):
    """Types of optimization problems."""
    
    ENERGY_MINIMIZATION = "energy_minimization"
    COMBINATORIAL = "combinatorial"
    CONTINUOUS = "continuous"
    CONSTRAINED = "constrained"
    MULTI_OBJECTIVE = "multi_objective"


class BackendType(str, Enum):
    """Types of quantum backends."""
    
    SIMULATOR = "simulator"
    GATE_BASED = "gate_based"
    ANNEALER = "annealer"
    PHOTONIC = "photonic"


class BackendStatus(str, Enum):
    """Backend availability status."""
    
    AVAILABLE = "available"
    BUSY = "busy"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"


@dataclass
class AlgorithmCapabilities:
    """Capabilities of an optimization algorithm."""
    
    supports_gradients: bool = False
    supports_constraints: bool = False
    supports_multi_objective: bool = False
    requires_ansatz: bool = False
    requires_hamiltonian: bool = False
    max_parameters: Optional[int] = None
    supported_problem_types: Set[ProblemType] = field(default_factory=set)
    required_backend_features: Set[str] = field(default_factory=set)


@dataclass
class AlgorithmMetadata:
    """Metadata for an optimization algorithm."""
    
    id: str
    name: str
    description: str
    category: AlgorithmCategory
    version: str
    capabilities: AlgorithmCapabilities
    default_parameters: Dict[str, Any] = field(default_factory=dict)
    parameter_schema: Optional[Dict[str, Any]] = None
    documentation_url: Optional[str] = None
    tags: Set[str] = field(default_factory=set)


@dataclass
class BackendCapabilities:
    """Capabilities of a quantum backend."""
    
    num_qubits: int
    connectivity: str  # "all-to-all", "linear", "grid", etc.
    gate_set: Set[str]
    max_circuit_depth: Optional[int] = None
    supports_mid_circuit_measurement: bool = False
    supports_reset: bool = False
    native_gates: Set[str] = field(default_factory=set)
    error_rates: Dict[str, float] = field(default_factory=dict)


@dataclass
class BackendMetadata:
    """Metadata for a quantum backend."""
    
    id: str
    name: str
    description: str
    backend_type: BackendType
    provider: str
    version: str
    capabilities: BackendCapabilities
    status: BackendStatus = BackendStatus.AVAILABLE
    queue_depth: int = 0
    average_job_time_seconds: float = 0.0
    pricing_info: Optional[Dict[str, Any]] = None
    tags: Set[str] = field(default_factory=set)


class OptimizerRegistry:
    """
    Registry for discovering and managing available optimizers.
    
    Provides registration, lookup, and filtering of optimization
    algorithms based on capabilities and requirements.
    """
    
    def __init__(self) -> None:
        self._optimizers: Dict[str, AlgorithmMetadata] = {}
        self._factories: Dict[str, Callable[..., Any]] = {}
    
    def register(
        self,
        metadata: AlgorithmMetadata,
        factory: Optional[Callable[..., Any]] = None,
    ) -> None:
        """
        Register an optimizer.
        
        Args:
            metadata: Algorithm metadata
            factory: Optional factory function for creating optimizer instances
        """
        if metadata.id in self._optimizers:
            logger.warning(f"Overwriting existing optimizer: {metadata.id}")
        
        self._optimizers[metadata.id] = metadata
        
        if factory is not None:
            self._factories[metadata.id] = factory
        
        logger.info(f"Registered optimizer: {metadata.id} ({metadata.name})")
    
    def unregister(self, optimizer_id: str) -> bool:
        """
        Unregister an optimizer.
        
        Args:
            optimizer_id: Optimizer identifier
            
        Returns:
            True if unregistered, False if not found
        """
        if optimizer_id not in self._optimizers:
            return False
        
        del self._optimizers[optimizer_id]
        self._factories.pop(optimizer_id, None)
        
        logger.info(f"Unregistered optimizer: {optimizer_id}")
        return True
    
    def get(self, optimizer_id: str) -> Optional[AlgorithmMetadata]:
        """Get optimizer metadata by ID."""
        return self._optimizers.get(optimizer_id)
    
    def list_all(self) -> List[AlgorithmMetadata]:
        """List all registered optimizers."""
        return list(self._optimizers.values())
    
    def find_by_category(self, category: AlgorithmCategory) -> List[AlgorithmMetadata]:
        """Find optimizers by category."""
        return [
            opt for opt in self._optimizers.values()
            if opt.category == category
        ]
    
    def find_by_problem_type(self, problem_type: ProblemType) -> List[AlgorithmMetadata]:
        """Find optimizers supporting a problem type."""
        return [
            opt for opt in self._optimizers.values()
            if problem_type in opt.capabilities.supported_problem_types
        ]
    
    def find_by_capabilities(
        self,
        supports_gradients: Optional[bool] = None,
        supports_constraints: Optional[bool] = None,
        supports_multi_objective: Optional[bool] = None,
        requires_ansatz: Optional[bool] = None,
    ) -> List[AlgorithmMetadata]:
        """Find optimizers matching capability requirements."""
        results = []
        
        for opt in self._optimizers.values():
            caps = opt.capabilities
            
            if supports_gradients is not None and caps.supports_gradients != supports_gradients:
                continue
            if supports_constraints is not None and caps.supports_constraints != supports_constraints:
                continue
            if supports_multi_objective is not None and caps.supports_multi_objective != supports_multi_objective:
                continue
            if requires_ansatz is not None and caps.requires_ansatz != requires_ansatz:
                continue
            
            results.append(opt)
        
        return results
    
    def find_by_tags(self, tags: Set[str]) -> List[AlgorithmMetadata]:
        """Find optimizers with matching tags."""
        return [
            opt for opt in self._optimizers.values()
            if tags.issubset(opt.tags)
        ]
    
    def create_instance(self, optimizer_id: str, **kwargs: Any) -> Any:
        """
        Create an optimizer instance.
        
        Args:
            optimizer_id: Optimizer identifier
            **kwargs: Constructor arguments
            
        Returns:
            Optimizer instance
            
        Raises:
            ValueError: If optimizer not found or no factory registered
        """
        if optimizer_id not in self._optimizers:
            raise ValueError(f"Optimizer not found: {optimizer_id}")
        
        if optimizer_id not in self._factories:
            raise ValueError(f"No factory registered for optimizer: {optimizer_id}")
        
        factory = self._factories[optimizer_id]
        return factory(**kwargs)
    
    def get_default_parameters(self, optimizer_id: str) -> Dict[str, Any]:
        """Get default parameters for an optimizer."""
        metadata = self._optimizers.get(optimizer_id)
        if metadata is None:
            return {}
        return dict(metadata.default_parameters)
    
    def validate_parameters(
        self,
        optimizer_id: str,
        parameters: Dict[str, Any],
    ) -> List[str]:
        """
        Validate parameters for an optimizer.
        
        Args:
            optimizer_id: Optimizer identifier
            parameters: Parameters to validate
            
        Returns:
            List of validation errors
        """
        metadata = self._optimizers.get(optimizer_id)
        if metadata is None:
            return [f"Optimizer not found: {optimizer_id}"]
        
        errors: List[str] = []
        
        # Basic validation if schema exists
        if metadata.parameter_schema:
            required = metadata.parameter_schema.get("required", [])
            for req in required:
                if req not in parameters:
                    errors.append(f"Missing required parameter: {req}")
        
        return errors


class BackendRegistry:
    """
    Registry for discovering and managing quantum backends.
    
    Provides registration, lookup, and status tracking of quantum
    backends with capability filtering.
    """
    
    def __init__(self) -> None:
        self._backends: Dict[str, BackendMetadata] = {}
        self._connectors: Dict[str, Callable[..., Any]] = {}
    
    def register(
        self,
        metadata: BackendMetadata,
        connector: Optional[Callable[..., Any]] = None,
    ) -> None:
        """
        Register a backend.
        
        Args:
            metadata: Backend metadata
            connector: Optional connector factory for creating connections
        """
        if metadata.id in self._backends:
            logger.warning(f"Overwriting existing backend: {metadata.id}")
        
        self._backends[metadata.id] = metadata
        
        if connector is not None:
            self._connectors[metadata.id] = connector
        
        logger.info(f"Registered backend: {metadata.id} ({metadata.name})")
    
    def unregister(self, backend_id: str) -> bool:
        """
        Unregister a backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            True if unregistered, False if not found
        """
        if backend_id not in self._backends:
            return False
        
        del self._backends[backend_id]
        self._connectors.pop(backend_id, None)
        
        logger.info(f"Unregistered backend: {backend_id}")
        return True
    
    def get(self, backend_id: str) -> Optional[BackendMetadata]:
        """Get backend metadata by ID."""
        return self._backends.get(backend_id)
    
    def list_all(self) -> List[BackendMetadata]:
        """List all registered backends."""
        return list(self._backends.values())
    
    def find_by_type(self, backend_type: BackendType) -> List[BackendMetadata]:
        """Find backends by type."""
        return [
            b for b in self._backends.values()
            if b.backend_type == backend_type
        ]
    
    def find_by_provider(self, provider: str) -> List[BackendMetadata]:
        """Find backends by provider."""
        return [
            b for b in self._backends.values()
            if b.provider.lower() == provider.lower()
        ]
    
    def find_available(self) -> List[BackendMetadata]:
        """Find all available backends."""
        return [
            b for b in self._backends.values()
            if b.status == BackendStatus.AVAILABLE
        ]
    
    def find_by_qubit_count(self, min_qubits: int) -> List[BackendMetadata]:
        """Find backends with at least the specified qubit count."""
        return [
            b for b in self._backends.values()
            if b.capabilities.num_qubits >= min_qubits
        ]
    
    def find_by_gate_support(self, gates: Set[str]) -> List[BackendMetadata]:
        """Find backends supporting the specified gates."""
        return [
            b for b in self._backends.values()
            if gates.issubset(b.capabilities.gate_set)
        ]
    
    def find_by_tags(self, tags: Set[str]) -> List[BackendMetadata]:
        """Find backends with matching tags."""
        return [
            b for b in self._backends.values()
            if tags.issubset(b.tags)
        ]
    
    def update_status(self, backend_id: str, status: BackendStatus) -> bool:
        """
        Update backend status.
        
        Args:
            backend_id: Backend identifier
            status: New status
            
        Returns:
            True if updated, False if not found
        """
        backend = self._backends.get(backend_id)
        if backend is None:
            return False
        
        backend.status = status
        logger.info(f"Backend {backend_id} status updated to {status}")
        return True
    
    def update_queue_depth(self, backend_id: str, queue_depth: int) -> bool:
        """
        Update backend queue depth.
        
        Args:
            backend_id: Backend identifier
            queue_depth: Current queue depth
            
        Returns:
            True if updated, False if not found
        """
        backend = self._backends.get(backend_id)
        if backend is None:
            return False
        
        backend.queue_depth = queue_depth
        return True
    
    def get_best_available(
        self,
        min_qubits: int = 0,
        required_gates: Optional[Set[str]] = None,
        backend_type: Optional[BackendType] = None,
    ) -> Optional[BackendMetadata]:
        """
        Get the best available backend matching requirements.
        
        Args:
            min_qubits: Minimum qubit count
            required_gates: Required gate set
            backend_type: Required backend type
            
        Returns:
            Best matching backend or None
        """
        candidates = self.find_available()
        
        if min_qubits > 0:
            candidates = [b for b in candidates if b.capabilities.num_qubits >= min_qubits]
        
        if required_gates:
            candidates = [b for b in candidates if required_gates.issubset(b.capabilities.gate_set)]
        
        if backend_type:
            candidates = [b for b in candidates if b.backend_type == backend_type]
        
        if not candidates:
            return None
        
        # Sort by queue depth, then by qubit count (prefer larger)
        candidates.sort(key=lambda b: (b.queue_depth, -b.capabilities.num_qubits))
        
        return candidates[0]
    
    def create_connection(self, backend_id: str, **kwargs: Any) -> Any:
        """
        Create a connection to a backend.
        
        Args:
            backend_id: Backend identifier
            **kwargs: Connection arguments
            
        Returns:
            Backend connection
            
        Raises:
            ValueError: If backend not found or no connector registered
        """
        if backend_id not in self._backends:
            raise ValueError(f"Backend not found: {backend_id}")
        
        if backend_id not in self._connectors:
            raise ValueError(f"No connector registered for backend: {backend_id}")
        
        connector = self._connectors[backend_id]
        return connector(**kwargs)


def create_default_optimizer_registry() -> OptimizerRegistry:
    """Create an optimizer registry with default algorithms."""
    registry = OptimizerRegistry()
    
    # VQE
    registry.register(AlgorithmMetadata(
        id="vqe",
        name="Variational Quantum Eigensolver",
        description="Hybrid quantum-classical algorithm for finding ground state energies",
        category=AlgorithmCategory.VARIATIONAL,
        version="1.0.0",
        capabilities=AlgorithmCapabilities(
            supports_gradients=True,
            requires_ansatz=True,
            requires_hamiltonian=True,
            supported_problem_types={ProblemType.ENERGY_MINIMIZATION},
        ),
        default_parameters={"optimizer": "cobyla", "max_iterations": 100},
        tags={"quantum", "variational", "chemistry"},
    ))
    
    # QAOA
    registry.register(AlgorithmMetadata(
        id="qaoa",
        name="Quantum Approximate Optimization Algorithm",
        description="Variational algorithm for combinatorial optimization",
        category=AlgorithmCategory.VARIATIONAL,
        version="1.0.0",
        capabilities=AlgorithmCapabilities(
            supports_gradients=True,
            requires_ansatz=True,
            supported_problem_types={ProblemType.COMBINATORIAL},
        ),
        default_parameters={"p": 1, "optimizer": "cobyla"},
        tags={"quantum", "variational", "optimization"},
    ))
    
    # Grover
    registry.register(AlgorithmMetadata(
        id="grover",
        name="Grover's Search Algorithm",
        description="Quantum search algorithm with quadratic speedup",
        category=AlgorithmCategory.GROVER_BASED,
        version="1.0.0",
        capabilities=AlgorithmCapabilities(
            supports_constraints=True,
            supported_problem_types={ProblemType.COMBINATORIAL},
        ),
        default_parameters={"iterations": "auto"},
        tags={"quantum", "search"},
    ))
    
    # SPSA
    registry.register(AlgorithmMetadata(
        id="spsa",
        name="Simultaneous Perturbation Stochastic Approximation",
        description="Gradient-free optimizer using finite differences",
        category=AlgorithmCategory.CLASSICAL,
        version="1.0.0",
        capabilities=AlgorithmCapabilities(
            supports_gradients=False,
            supported_problem_types={
                ProblemType.CONTINUOUS,
                ProblemType.ENERGY_MINIMIZATION,
            },
        ),
        default_parameters={"a": 0.1, "c": 0.1, "max_iterations": 100},
        tags={"classical", "gradient-free"},
    ))
    
    return registry


def create_default_backend_registry() -> BackendRegistry:
    """Create a backend registry with default backends."""
    registry = BackendRegistry()
    
    # Local simulator
    registry.register(BackendMetadata(
        id="local_simulator",
        name="Local State Vector Simulator",
        description="High-performance local quantum simulator",
        backend_type=BackendType.SIMULATOR,
        provider="qsop",
        version="1.0.0",
        capabilities=BackendCapabilities(
            num_qubits=30,
            connectivity="all-to-all",
            gate_set={"h", "x", "y", "z", "cx", "cz", "rz", "ry", "rx", "swap"},
            supports_mid_circuit_measurement=True,
            supports_reset=True,
        ),
        tags={"simulator", "local", "fast"},
    ))
    
    # Noisy simulator
    registry.register(BackendMetadata(
        id="noisy_simulator",
        name="Noisy Quantum Simulator",
        description="Simulator with realistic noise models",
        backend_type=BackendType.SIMULATOR,
        provider="qsop",
        version="1.0.0",
        capabilities=BackendCapabilities(
            num_qubits=20,
            connectivity="all-to-all",
            gate_set={"h", "x", "y", "z", "cx", "cz", "rz", "ry", "rx"},
            error_rates={"single_qubit": 0.001, "two_qubit": 0.01},
        ),
        tags={"simulator", "noisy", "realistic"},
    ))
    
    return registry

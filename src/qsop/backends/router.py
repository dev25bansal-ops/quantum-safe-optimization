"""
Backend Router and Routing Strategies for QSOP.
"""

from __future__ import annotations

import abc
from typing import Any, List, Optional, Protocol, runtime_checkable

from qsop.domain.ports.quantum_backend import QuantumBackend
from qsop.backends.pool import BackendPool


@runtime_checkable
class RoutingStrategy(Protocol):
    """Protocol for backend routing strategies."""
    
    @abc.abstractmethod
    def select(
        self, 
        backends: List[QuantumBackend], 
        circuit: Any, 
        **options: Any
    ) -> Optional[QuantumBackend]:
        """Select the best backend from the provided list."""
        ...


class LeastBusyStrategy:
    """Selects the backend with the fewest pending jobs."""
    
    def select(
        self, 
        backends: List[QuantumBackend], 
        circuit: Any, 
        **options: Any
    ) -> Optional[QuantumBackend]:
        online_backends = [b for b in backends if b.capabilities.online]
        if not online_backends:
            return None
            
        return min(online_backends, key=lambda b: b.capabilities.pending_jobs)


class CostOptimizedStrategy:
    """
    Selects the most cost-effective backend.
    
    Prioritizes simulators and local backends over cloud-based hardware.
    """
    
    def select(
        self, 
        backends: List[QuantumBackend], 
        circuit: Any, 
        **options: Any
    ) -> Optional[QuantumBackend]:
        online_backends = [b for b in backends if b.capabilities.online]
        if not online_backends:
            return None
            
        # Preference: 
        # 1. Local Simulators
        # 2. Remote Simulators
        # 3. Hardware
        def cost_score(backend: QuantumBackend) -> int:
            caps = backend.capabilities
            if caps.simulator and caps.local:
                return 0
            if caps.simulator:
                return 1
            return 2
            
        return min(online_backends, key=cost_score)


class DepthAwareStrategy:
    """
    Selects a backend based on circuit depth and backend capabilities.
    
    Filters out backends with insufficient qubits or unsupported gates,
    then picks based on a combination of queue time and hardware quality.
    """
    
    def select(
        self, 
        backends: List[QuantumBackend], 
        circuit: Any, 
        **options: Any
    ) -> Optional[QuantumBackend]:
        # This strategy would ideally analyze the circuit
        # For now, we perform basic filtering and fallback to least busy
        online_backends = [b for b in backends if b.capabilities.online]
        if not online_backends:
            return None
            
        # In a real implementation, we'd check circuit.num_qubits vs backend.num_qubits
        # and circuit depth vs coherence times.
        
        return min(online_backends, key=lambda b: b.capabilities.pending_jobs)


class BackendRouter:
    """
    Routes quantum circuits to the most appropriate backend.
    """
    
    def __init__(
        self, 
        pool: BackendPool, 
        default_strategy: Optional[RoutingStrategy] = None
    ) -> None:
        self.pool = pool
        self.strategy = default_strategy or LeastBusyStrategy()
        
    def route(self, circuit: Any, **options: Any) -> QuantumBackend:
        """
        Select a backend for the given circuit.
        
        Args:
            circuit: The circuit to execute.
            **options: Optional overrides, e.g., 'strategy' or 'backend_name'.
            
        Returns:
            The selected backend.
            
        Raises:
            RuntimeError: If no suitable backend is found.
        """
        # 1. Check for explicit backend request
        if "backend_name" in options:
            backend = self.pool.get_backend(options["backend_name"])
            if backend:
                return backend
            raise ValueError(f"Requested backend '{options['backend_name']}' not found in pool")
            
        # 2. Use strategy to select
        strategy = options.get("strategy", self.strategy)
        backends = self.pool.list_backends(only_online=True)
        
        selected = strategy.select(backends, circuit, **options)
        if not selected:
            raise RuntimeError("No online quantum backends available in the pool")
            
        return selected

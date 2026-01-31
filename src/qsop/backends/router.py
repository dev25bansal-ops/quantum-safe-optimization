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
    
    Filters out backends with insufficient qubits, then picks based on 
    a combination of queue time and whether it's a simulator (for deep circuits).
    """
    
    def select(
        self, 
        backends: List[QuantumBackend], 
        circuit: Any, 
        **options: Any
    ) -> Optional[QuantumBackend]:
        # 1. Extract circuit requirements
        num_qubits = getattr(circuit, "num_qubits", 0)
        depth = 0
        if hasattr(circuit, "depth"):
            try:
                depth = circuit.depth()
            except Exception:
                pass

        # 2. Filter backends by qubit count
        suitable = [b for b in backends if b.capabilities.online and b.capabilities.num_qubits >= num_qubits]
        if not suitable:
            return None
            
        # 3. Decision logic:
        # If circuit is "deep" (arbitrary threshold > 50 gates), prefer simulators for reliability
        # unless hardware is specifically requested.
        is_deep = depth > 50
        
        if is_deep:
            simulators = [b for b in suitable if b.capabilities.simulator]
            if simulators:
                return min(simulators, key=lambda b: b.capabilities.pending_jobs)
        else:
            # For shallow circuits, prefer hardware if available
            hardware = [b for b in suitable if not b.capabilities.simulator]
            if hardware:
                return min(hardware, key=lambda b: b.capabilities.pending_jobs)
                
        # Fallback to least busy among all suitable
        return min(suitable, key=lambda b: b.capabilities.pending_jobs)


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


class FailoverRouter(BackendRouter):
    """
    A router that supports failover if the primary selection fails.
    """
    
    def route_with_failover(self, circuit: Any, **options: Any) -> QuantumBackend:
        """
        Attempts to route to the best backend, but provides fallbacks 
        if the selection criteria are too strict.
        """
        try:
            return self.route(circuit, **options)
        except RuntimeError:
            # Fallback: try any online backend if preferred strategy failed
            backends = self.pool.list_backends(only_online=True)
            if not backends:
                raise RuntimeError("No online quantum backends available even for failover")
            
            # Use least busy as absolute fallback
            return min(backends, key=lambda b: b.capabilities.pending_jobs)

"""
Transpilation service port definition.

Defines the protocol for hardware-aware circuit transpilation and optimization.
"""

from typing import Any, Protocol, runtime_checkable

from qsop.domain.ports.quantum_backend import BackendCapabilities


@runtime_checkable
class TranspilationService(Protocol):
    """
    Protocol for circuit transpilation services.

    Optimizes quantum circuits for specific hardware topologies and gate sets.
    """

    def transpile_for_backend(
        self,
        circuit: Any,
        capabilities: BackendCapabilities,
        optimization_level: int = 1,
        **options: Any,
    ) -> Any:
        """
        Transpile a circuit for a specific backend's capabilities.

        Args:
            circuit: The quantum circuit to transpile.
            capabilities: Target backend capabilities (coupling map, basis gates).
            optimization_level: Optimization level (0-3).
            **options: Additional transpilation options.

        Returns:
            The transpiled circuit.
        """
        ...

    def optimize_qaoa_layout(
        self,
        circuit: Any,
        capabilities: BackendCapabilities,
        **options: Any,
    ) -> Any:
        """
        Specific optimization for QAOA circuits to minimize SWAPs.

        Args:
            circuit: The QAOA circuit.
            capabilities: Target backend capabilities.
            **options: Additional options.

        Returns:
            Optimized circuit with hardware-aware qubit mapping.
        """
        ...

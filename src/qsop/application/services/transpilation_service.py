"""
Hardware-aware transpilation service implementation.

Uses Qiskit's transpiler to optimize circuits for specific backend topologies.
"""

import logging
from typing import Any

from qsop.domain.ports.quantum_backend import BackendCapabilities
from qsop.domain.ports.transpilation import TranspilationService

logger = logging.getLogger(__name__)


class QiskitTranspilationService(TranspilationService):
    """
    Qiskit-based transpilation service.

    Provides hardware-aware optimization and algorithm-specific layout mapping.
    """

    def transpile_for_backend(
        self,
        circuit: Any,
        capabilities: BackendCapabilities,
        optimization_level: int = 1,
        **options: Any,
    ) -> Any:
        """
        Transpile circuit for backend using Qiskit.
        """
        try:
            from qiskit import transpile
            from qiskit.transpiler import CouplingMap
        except ImportError:
            logger.error("Qiskit not installed. Cannot transpile.")
            return circuit

        # Convert BackendCapabilities to Qiskit-compatible objects
        basis_gates = list(capabilities.basis_gates) if capabilities.basis_gates else None
        coupling_map = (
            CouplingMap(list(capabilities.coupling_map)) if capabilities.coupling_map else None
        )

        logger.debug(
            f"Transpiling for backend {capabilities.name} "
            f"(opt_level={optimization_level}, qubits={capabilities.num_qubits})"
        )

        transpiled_circuit = transpile(
            circuit,
            basis_gates=basis_gates,
            coupling_map=coupling_map,
            optimization_level=optimization_level,
            **options,
        )

        return transpiled_circuit

    def optimize_qaoa_layout(
        self,
        circuit: Any,
        capabilities: BackendCapabilities,
        **options: Any,
    ) -> Any:
        """
        Optimize QAOA layout to minimize SWAP gates on constrained topologies.

        Uses noise-adaptive or Sabre layout if available.
        """
        try:
            from qiskit import transpile
            from qiskit.transpiler import CouplingMap
        except ImportError:
            return circuit

        if not capabilities.coupling_map:
            return self.transpile_for_backend(circuit, capabilities, optimization_level=3)

        coupling_map = CouplingMap(list(capabilities.coupling_map))

        # QAOA specific: we prefer SabreLayout for initial mapping
        # and SabreSwap for routing as they perform well on structured circuits.
        # We override optimization_level to 3 for QAOA layout optimization
        final_options = {**options, "optimization_level": 3}
        return transpile(
            circuit,
            coupling_map=coupling_map,
            basis_gates=list(capabilities.basis_gates) if capabilities.basis_gates else None,
            layout_method="sabre",
            routing_method="sabre",
            **final_options,
        )

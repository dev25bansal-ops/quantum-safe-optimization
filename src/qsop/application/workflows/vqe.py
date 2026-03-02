"""
VQE workflow for ground state energy estimation.

Implements the Variational Quantum Eigensolver for chemistry and physics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
from numpy.typing import NDArray

from ...backends.mitigation import ReadoutMitigatedBackend, ZNEMitigatedBackend
from ...domain.models.result import ConvergenceInfo, OptimizationResult, QuantumExecutionResult
from ...domain.ports.quantum_backend import QuantumBackend
from ...domain.ports.transpilation import TranspilationService


class AnsatzType(str, Enum):
    """Variational ansatz types."""

    RY_LINEAR = "ry_linear"
    HARDWARE_EFFICIENT = "hardware_efficient"
    UCCSD = "uccsd"


@dataclass
class HamiltonianTerm:
    """A term in the Hamiltonian."""

    coefficient: complex
    pauli_string: str  # e.g., "XZIY" for X⊗Z⊗I⊗Y

    def __post_init__(self):
        self.pauli_string = self.pauli_string.upper()


@dataclass
class Hamiltonian:
    """Qubit Hamiltonian representation."""

    n_qubits: int
    terms: list[HamiltonianTerm] = field(default_factory=list)

    def add_term(self, coefficient: complex, pauli_string: str) -> None:
        """Add a Pauli term to the Hamiltonian."""
        if len(pauli_string) != self.n_qubits:
            raise ValueError(f"Pauli string length must be {self.n_qubits}")
        self.terms.append(HamiltonianTerm(coefficient, pauli_string))

    @classmethod
    def from_ising(
        cls,
        n_qubits: int,
        h: list[float],
        J: dict[tuple[int, int], float],
    ) -> Hamiltonian:
        """Create Hamiltonian from Ising model parameters."""
        ham = cls(n_qubits)

        # Single-qubit terms
        for i, hi in enumerate(h):
            if hi != 0:
                pauli = "I" * i + "Z" + "I" * (n_qubits - i - 1)
                ham.add_term(hi, pauli)

        # Two-qubit terms
        for (i, j), Jij in J.items():
            if Jij != 0:
                pauli = list("I" * n_qubits)
                pauli[i] = "Z"
                pauli[j] = "Z"
                ham.add_term(Jij, "".join(pauli))

        return ham


@dataclass
class VQEWorkflowConfig:
    """Configuration for VQE workflow."""

    ansatz_type: AnsatzType = AnsatzType.HARDWARE_EFFICIENT
    ansatz_layers: int = 2
    shots: int = 1024
    optimizer: str = "COBYLA"
    max_iterations: int = 100
    grouping: bool = True  # Group commuting Pauli terms
    enable_readout_mitigation: bool = False
    enable_zne: bool = False
    optimization_level: int = 1
    random_seed: int | None = None


class VQEWorkflow:
    """
    VQE workflow for ground state estimation.

    Estimates the ground state energy of a Hamiltonian using
    a parameterized quantum circuit (ansatz).
    """

    def __init__(
        self,
        config: VQEWorkflowConfig | None = None,
        backend: QuantumBackend | None = None,
        transpiler: TranspilationService | None = None,
    ):
        self.config = config or VQEWorkflowConfig()
        self.backend = self._apply_mitigation(backend) if backend else None
        self.transpiler = transpiler

        if self.config.random_seed is not None:
            import numpy as np

            try:
                import qiskit

                qiskit.qi.random.seed(self.config.random_seed)
            except (ImportError, AttributeError):
                pass
            np.random.seed(self.config.random_seed)

    def _apply_mitigation(self, backend: QuantumBackend) -> QuantumBackend:
        """Apply configured error mitigation to the backend."""
        mitigated = backend
        if self.config.enable_readout_mitigation:
            mitigated = ReadoutMitigatedBackend(mitigated)
        if self.config.enable_zne:
            mitigated = ZNEMitigatedBackend(mitigated)
        return mitigated

    def run(self, hamiltonian: Hamiltonian) -> OptimizationResult:
        """Execute VQE workflow."""
        from scipy.optimize import minimize

        n_qubits = hamiltonian.n_qubits
        n_params = self._count_params(n_qubits)

        initial_params = np.random.uniform(-np.pi, np.pi, n_params)
        history = []

        def energy_function(params: NDArray) -> float:
            """Compute energy expectation."""
            energy = self._compute_energy(hamiltonian, params)
            history.append({"params": params.tolist(), "energy": energy})
            return energy

        result = minimize(
            energy_function,
            initial_params,
            method=self.config.optimizer,
            options={"maxiter": self.config.max_iterations},
            seed=self.config.random_seed if self.config.random_seed is not None else None,
        )

        return OptimizationResult(
            optimal_value=float(result.fun),
            optimal_parameters={f"θ_{i}": val for i, val in enumerate(result.x)},
            iterations=result.nit if hasattr(result, "nit") else len(history),
            function_evaluations=result.nfev if hasattr(result, "nfev") else 0,
            convergence=ConvergenceInfo(
                converged=result.success if hasattr(result, "success") else True,
                reason=result.message if hasattr(result, "message") else "",
            ),
            objective_history=tuple(h["energy"] for h in history),
            metadata={
                "algorithm": "vqe",
                "ansatz": self.config.ansatz_type.value,
                "layers": self.config.ansatz_layers,
            },
        )

    def _count_params(self, n_qubits: int) -> int:
        """Count variational parameters."""
        if self.config.ansatz_type == AnsatzType.RY_LINEAR:
            return n_qubits * self.config.ansatz_layers
        elif self.config.ansatz_type == AnsatzType.HARDWARE_EFFICIENT:
            return 2 * n_qubits * self.config.ansatz_layers
        return n_qubits * self.config.ansatz_layers

    def _compute_energy(
        self,
        hamiltonian: Hamiltonian,
        params: NDArray,
    ) -> float:
        """Compute Hamiltonian expectation value."""
        if self.config.grouping:
            return self._compute_grouped(hamiltonian, params)
        return self._compute_naive(hamiltonian, params)

    def _compute_naive(
        self,
        hamiltonian: Hamiltonian,
        params: NDArray,
    ) -> float:
        """Compute energy by measuring each term separately."""
        energy = 0.0

        for term in hamiltonian.terms:
            if all(p == "I" for p in term.pauli_string):
                # Identity term
                energy += term.coefficient.real
                continue

            # Build circuit with measurement basis rotation
            circuit = self._build_ansatz_circuit(hamiltonian.n_qubits, params)
            self._add_measurement_rotations(circuit, term.pauli_string)

            # Hardware-aware transpilation
            if self.transpiler and self.backend:
                circuit = self.transpiler.transpile_for_backend(
                    circuit,
                    self.backend.capabilities,
                    optimization_level=self.config.optimization_level,
                )

            result = self.backend.run(circuit, shots=self.config.shots)
            expectation = self._compute_pauli_expectation(result, term.pauli_string)

            energy += term.coefficient.real * expectation

        return energy

    def _compute_grouped(
        self,
        hamiltonian: Hamiltonian,
        params: NDArray,
    ) -> float:
        """Compute energy by grouping commuting terms."""
        # Group terms by measurement basis
        groups = self._group_commuting_terms(hamiltonian)

        energy = 0.0
        for basis, terms in groups.items():
            circuit = self._build_ansatz_circuit(hamiltonian.n_qubits, params)
            self._add_measurement_rotations(circuit, basis)

            # Hardware-aware transpilation
            if self.transpiler and self.backend:
                circuit = self.transpiler.transpile_for_backend(
                    circuit,
                    self.backend.capabilities,
                    optimization_level=self.config.optimization_level,
                )

            result = self.backend.run(circuit, shots=self.config.shots)

            for term in terms:
                if all(p == "I" for p in term.pauli_string):
                    energy += term.coefficient.real
                else:
                    expectation = self._compute_pauli_expectation(result, term.pauli_string)
                    energy += term.coefficient.real * expectation

        return energy

    def _group_commuting_terms(
        self,
        hamiltonian: Hamiltonian,
    ) -> dict[str, list[HamiltonianTerm]]:
        """Group terms that can be measured simultaneously."""
        # Simple grouping: same non-identity positions
        groups: dict[str, list[HamiltonianTerm]] = {}

        for term in hamiltonian.terms:
            # Create measurement basis key
            basis = "".join(p if p != "I" else "Z" for p in term.pauli_string)

            if basis not in groups:
                groups[basis] = []
            groups[basis].append(term)

        return groups

    def _build_ansatz_circuit(self, n_qubits: int, params: NDArray) -> Any:
        """Build variational ansatz circuit."""
        try:
            from qiskit import QuantumCircuit
        except ImportError as e:
            raise ImportError("Qiskit required") from e

        qc = QuantumCircuit(n_qubits)
        param_idx = 0

        for _layer in range(self.config.ansatz_layers):
            # Single-qubit rotations
            for q in range(n_qubits):
                if self.config.ansatz_type == AnsatzType.RY_LINEAR:
                    qc.ry(params[param_idx], q)
                    param_idx += 1
                elif self.config.ansatz_type == AnsatzType.HARDWARE_EFFICIENT:
                    qc.ry(params[param_idx], q)
                    param_idx += 1
                    qc.rz(params[param_idx], q)
                    param_idx += 1

            # Entangling layer
            if self.config.ansatz_type == AnsatzType.HARDWARE_EFFICIENT:
                for q in range(n_qubits - 1):
                    qc.cx(q, q + 1)

        return qc

    def _add_measurement_rotations(self, circuit: Any, pauli_string: str) -> None:
        """Add rotations to measure in Pauli basis."""
        for i, pauli in enumerate(pauli_string):
            if pauli == "X":
                circuit.h(i)
            elif pauli == "Y":
                circuit.sdg(i)
                circuit.h(i)

        circuit.measure_all()

    def _compute_pauli_expectation(
        self,
        result: QuantumExecutionResult,
        pauli_string: str,
    ) -> float:
        """Compute Pauli expectation from measurement results."""
        counts = result.counts
        total = result.total_counts

        expectation = 0.0
        for bitstring, count in counts.items():
            # Compute parity of relevant bits
            parity = 1
            for i, pauli in enumerate(pauli_string):
                if pauli != "I":
                    # Qiskit uses little-endian for bitstrings (q0 is rightmost)
                    # We need to check the bit corresponding to qubit i
                    if bitstring[::-1][i] == "1":
                        parity *= -1

            expectation += parity * count / total

        return expectation


def estimate_ground_state(
    hamiltonian: Hamiltonian,
    ansatz_layers: int = 2,
    shots: int = 1024,
    backend: QuantumBackend | None = None,
) -> OptimizationResult:
    """
    Convenience function to estimate ground state energy.

    Args:
        hamiltonian: The Hamiltonian to minimize
        ansatz_layers: Number of ansatz layers
        shots: Measurement shots
        backend: Quantum backend

    Returns:
        Result with estimated ground state energy
    """
    config = VQEWorkflowConfig(ansatz_layers=ansatz_layers, shots=shots)
    workflow = VQEWorkflow(config=config, backend=backend)
    return workflow.run(hamiltonian)

"""VQE (Variational Quantum Eigensolver) optimizer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter


class AnsatzType(Enum):
    """Types of variational ansatz circuits."""

    RY = "ry"
    RY_RZ = "ry_rz"
    HARDWARE_EFFICIENT = "hardware_efficient"
    UCCSD = "uccsd"
    TWO_LOCAL = "two_local"


@dataclass
class PauliTerm:
    """A Pauli term in a Hamiltonian.

    Attributes:
        coefficient: Complex coefficient.
        paulis: Dictionary mapping qubit index to Pauli operator ('I', 'X', 'Y', 'Z').
    """

    coefficient: complex
    paulis: dict[int, str]

    def __repr__(self) -> str:
        if not self.paulis:
            return f"{self.coefficient:.4f} * I"
        terms = " ".join(f"{p}{i}" for i, p in sorted(self.paulis.items()))
        return f"{self.coefficient:.4f} * {terms}"


@dataclass
class Hamiltonian:
    """Represents a quantum Hamiltonian as sum of Pauli terms.

    Attributes:
        terms: List of PauliTerm objects.
        num_qubits: Number of qubits.
    """

    terms: list[PauliTerm]
    num_qubits: int

    @classmethod
    def from_ising(
        cls,
        h: dict[int, float],
        J: dict[tuple[int, int], float],
        offset: float = 0.0,
    ) -> Hamiltonian:
        """Create Hamiltonian from Ising model.

        H = sum_i h_i Z_i + sum_{ij} J_{ij} Z_i Z_j + offset
        """
        all_qubits = set(h.keys())
        for i, j in J.keys():
            all_qubits.add(i)
            all_qubits.add(j)
        num_qubits = max(all_qubits) + 1 if all_qubits else 0

        terms: list[PauliTerm] = []

        if offset != 0:
            terms.append(PauliTerm(coefficient=offset, paulis={}))

        for qubit, coeff in h.items():
            if coeff != 0:
                terms.append(PauliTerm(coefficient=coeff, paulis={qubit: "Z"}))

        for (i, j), coeff in J.items():
            if coeff != 0:
                terms.append(PauliTerm(coefficient=coeff, paulis={i: "Z", j: "Z"}))

        return cls(terms=terms, num_qubits=num_qubits)

    @classmethod
    def from_pauli_list(
        cls,
        pauli_list: list[tuple[str, complex]],
    ) -> Hamiltonian:
        """Create Hamiltonian from list of (pauli_string, coefficient) tuples.

        Example: [("ZZ", 1.0), ("XI", 0.5), ("IY", -0.3)]
        """
        if not pauli_list:
            return cls(terms=[], num_qubits=0)

        num_qubits = len(pauli_list[0][0])
        terms: list[PauliTerm] = []

        for pauli_str, coeff in pauli_list:
            paulis: dict[int, str] = {}
            for i, p in enumerate(pauli_str):
                if p != "I":
                    paulis[i] = p
            terms.append(PauliTerm(coefficient=coeff, paulis=paulis))

        return cls(terms=terms, num_qubits=num_qubits)

    def to_matrix(self) -> NDArray[np.complex128]:
        """Convert Hamiltonian to matrix representation."""
        identity_matrix = np.array([[1, 0], [0, 1]], dtype=np.complex128)
        X = np.array([[0, 1], [1, 0]], dtype=np.complex128)
        Y = np.array([[0, -1j], [1j, 0]], dtype=np.complex128)
        Z = np.array([[1, 0], [0, -1]], dtype=np.complex128)
        pauli_map = {"I": identity_matrix, "X": X, "Y": Y, "Z": Z}

        dim = 2**self.num_qubits
        H = np.zeros((dim, dim), dtype=np.complex128)

        for term in self.terms:
            term_matrix = np.array([[1.0]], dtype=np.complex128)
            for qubit in range(self.num_qubits):
                pauli = term.paulis.get(qubit, "I")
                term_matrix = np.kron(term_matrix, pauli_map[pauli])
            H += term.coefficient * term_matrix

        return H


@dataclass
class VQEResult:
    """Result from VQE optimization.

    Attributes:
        optimal_params: Optimized variational parameters.
        optimal_value: Lowest energy eigenvalue found.
        eigenstate: Approximate ground state (if computed).
        num_iterations: Number of optimization iterations.
        history: Energy values at each iteration.
    """

    optimal_params: NDArray[np.float64]
    optimal_value: float
    eigenstate: NDArray[np.complex128] | None = None
    num_iterations: int = 0
    history: list[float] = field(default_factory=list)


class QuantumBackend(Protocol):
    """Protocol for quantum backends."""

    def run(
        self,
        circuit: QuantumCircuit,
        shots: int = 1024,
    ) -> dict[str, int]:
        """Execute circuit and return measurement counts."""
        ...

    def get_statevector(
        self,
        circuit: QuantumCircuit,
    ) -> NDArray[np.complex128]:
        """Get statevector from circuit execution."""
        ...


class VQEOptimizer:
    """VQE optimizer for finding ground state energies.

    Implements the Variational Quantum Eigensolver with configurable
    ansatz circuits and Hamiltonian encoding.

    Example:
        >>> hamiltonian = Hamiltonian.from_ising(h={0: 1.0}, J={(0, 1): -1.0})
        >>> optimizer = VQEOptimizer(ansatz_type=AnsatzType.RY, depth=2)
        >>> result = optimizer.optimize(hamiltonian, backend=backend)
        >>> print(f"Ground state energy: {result.optimal_value}")
    """

    def __init__(
        self,
        ansatz_type: AnsatzType = AnsatzType.HARDWARE_EFFICIENT,
        depth: int = 1,
        entanglement: str = "linear",
        seed: int | None = None,
    ):
        """Initialize VQE optimizer.

        Args:
            ansatz_type: Type of variational ansatz.
            depth: Number of ansatz layers.
            entanglement: Entanglement pattern ('linear', 'circular', 'full').
            seed: Random seed for reproducibility.
        """
        self.ansatz_type = ansatz_type
        self.depth = depth
        self.entanglement = entanglement
        self.rng = np.random.default_rng(seed)

        self._params: list[Parameter] = []
        self._backend: QuantumBackend | None = None

    def _get_entanglement_map(self, num_qubits: int) -> list[tuple[int, int]]:
        """Get qubit pairs for entanglement based on pattern."""
        if num_qubits < 2:
            return []

        if self.entanglement == "linear":
            return [(i, i + 1) for i in range(num_qubits - 1)]
        elif self.entanglement == "circular":
            pairs = [(i, i + 1) for i in range(num_qubits - 1)]
            pairs.append((num_qubits - 1, 0))
            return pairs
        elif self.entanglement == "full":
            return [(i, j) for i in range(num_qubits) for j in range(i + 1, num_qubits)]
        else:
            raise ValueError(f"Unknown entanglement: {self.entanglement}")

    def build_ry_ansatz(
        self,
        num_qubits: int,
        params: list[Parameter] | None = None,
    ) -> QuantumCircuit:
        """Build RY variational ansatz.

        Args:
            num_qubits: Number of qubits.
            params: Optional parameter list.

        Returns:
            Parameterized circuit.
        """
        circuit = QuantumCircuit(num_qubits)
        param_idx = 0

        if params is None:
            total_params = num_qubits * self.depth
            params = [Parameter(f"θ_{i}") for i in range(total_params)]
            self._params = params

        for _layer in range(self.depth):
            for qubit in range(num_qubits):
                circuit.ry(params[param_idx], qubit)
                param_idx += 1

            for i, j in self._get_entanglement_map(num_qubits):
                circuit.cx(i, j)

        return circuit

    def build_ry_rz_ansatz(
        self,
        num_qubits: int,
        params: list[Parameter] | None = None,
    ) -> QuantumCircuit:
        """Build RY-RZ variational ansatz."""
        circuit = QuantumCircuit(num_qubits)
        param_idx = 0

        if params is None:
            total_params = 2 * num_qubits * self.depth
            params = [Parameter(f"θ_{i}") for i in range(total_params)]
            self._params = params

        for _layer in range(self.depth):
            for qubit in range(num_qubits):
                circuit.ry(params[param_idx], qubit)
                param_idx += 1
            for qubit in range(num_qubits):
                circuit.rz(params[param_idx], qubit)
                param_idx += 1

            for i, j in self._get_entanglement_map(num_qubits):
                circuit.cx(i, j)

        return circuit

    def build_hardware_efficient_ansatz(
        self,
        num_qubits: int,
        params: list[Parameter] | None = None,
    ) -> QuantumCircuit:
        """Build hardware-efficient variational ansatz."""
        circuit = QuantumCircuit(num_qubits)
        param_idx = 0

        if params is None:
            total_params = 3 * num_qubits * self.depth + num_qubits
            params = [Parameter(f"θ_{i}") for i in range(total_params)]
            self._params = params

        for qubit in range(num_qubits):
            circuit.ry(params[param_idx], qubit)
            param_idx += 1

        for _layer in range(self.depth):
            for i, j in self._get_entanglement_map(num_qubits):
                circuit.cx(i, j)

            for qubit in range(num_qubits):
                circuit.ry(params[param_idx], qubit)
                param_idx += 1
                circuit.rz(params[param_idx], qubit)
                param_idx += 1
                circuit.ry(params[param_idx], qubit)
                param_idx += 1

        return circuit

    def build_uccsd_ansatz(
        self,
        num_electrons: int = 2,
        num_qubits: int = 4,
        params: list[Parameter] | None = None,
    ) -> QuantumCircuit:
        """Build UCCSD ansatz for chemistry problems.

        Implements Unitary Coupled Cluster with Singles and Doubles (UCCSD):
        - Single excitations: t_{i→a} (a^†_a a_i - h.c.)
        - Double excitations: t_{ij→ab} (a^†_a a^†_b a_j a_i - h.c.)

        Args:
            num_electrons: Number of electrons (occupied orbitals)
            num_qubits: Number of molecular orbitals (qubits)
            params: Optional list of variational parameters

        Returns:
            Parameterized UCCSD circuit
        """
        circuit = QuantumCircuit(num_qubits)

        # Count parameters needed
        num_occupied = num_electrons
        num_virtual = num_qubits - num_electrons

        num_singles = num_occupied * num_virtual
        num_doubles = (num_singles * (num_singles - 1)) // 2
        total_params = num_singles + num_doubles

        if params is None:
            params = [Parameter(f"t_{i}") for i in range(max(1, total_params))]
            self._params = params

        # Prepare Hartree-Fock reference state (occupied spin-orbitals filled)
        for i in range(num_occupied):
            circuit.x(i)

        param_idx = 0

        # Single excitations: exp(t_{i→a} (a^†_a a_i - h.c.))
        for i in range(num_occupied):
            for a in range(num_occupied, num_qubits):
                if param_idx < len(params):
                    t = params[param_idx]
                    # Using approximation: exp(-i t X_i Y_a) ≈ CX(i,a) RY(2t) CX(i,a)
                    circuit.cx(i, a)
                    circuit.ry(2 * t, a)
                    circuit.cx(i, a)
                    param_idx += 1

        # Double excitations: exp(t_{ij→ab} (a^†_a a^†_b a_j a_i - h.c.))
        # Simplified implementation using chain of entangling gates
        for i in range(num_occupied):
            for j in range(i + 1, num_occupied):
                for a in range(num_occupied, num_qubits):
                    for b in range(a + 1, num_qubits):
                        if param_idx < len(params):
                            t = params[param_idx]
                            # Simplified double excitation pattern
                            # Maps to four qubits: i, j (occupied) -> a, b (virtual)
                            circuit.cx(i, a)
                            circuit.cx(j, b)
                            circuit.cx(a, i)
                            circuit.cx(b, j)
                            circuit.ry(2 * t, a)
                            circuit.ry(2 * t, b)
                            circuit.cx(a, i)
                            circuit.cx(b, j)
                            circuit.cx(i, a)
                            circuit.cx(j, b)
                            param_idx += 1

        return circuit

    def build_ansatz(
        self,
        num_qubits: int,
        params: list[Parameter] | None = None,
        **kwargs: Any,
    ) -> QuantumCircuit:
        """Build variational ansatz based on configured type.

        Args:
            num_qubits: Number of qubits.
            params: Optional parameter list.
            **kwargs: Additional arguments for specific ansatz types.

        Returns:
            Parameterized circuit.
        """
        if self.ansatz_type == AnsatzType.RY:
            return self.build_ry_ansatz(num_qubits, params)
        elif self.ansatz_type == AnsatzType.RY_RZ:
            return self.build_ry_rz_ansatz(num_qubits, params)
        elif self.ansatz_type == AnsatzType.HARDWARE_EFFICIENT:
            return self.build_hardware_efficient_ansatz(num_qubits, params)
        elif self.ansatz_type == AnsatzType.UCCSD:
            return self.build_uccsd_ansatz(
                num_qubits,
                kwargs.get("num_electrons", 2),
                params,
            )
        elif self.ansatz_type == AnsatzType.TWO_LOCAL:
            return self.build_hardware_efficient_ansatz(num_qubits, params)
        else:
            raise ValueError(f"Unknown ansatz type: {self.ansatz_type}")

    def get_num_parameters(self, num_qubits: int) -> int:
        """Get the number of parameters for the configured ansatz."""
        if self.ansatz_type == AnsatzType.RY:
            return num_qubits * self.depth
        elif self.ansatz_type == AnsatzType.RY_RZ:
            return 2 * num_qubits * self.depth
        elif self.ansatz_type in (AnsatzType.HARDWARE_EFFICIENT, AnsatzType.TWO_LOCAL):
            return 3 * num_qubits * self.depth + num_qubits
        elif self.ansatz_type == AnsatzType.UCCSD:
            return max(1, num_qubits * (num_qubits - 2) // 2)
        else:
            raise ValueError(f"Unknown ansatz type: {self.ansatz_type}")

    def measure_pauli_term(
        self,
        circuit: QuantumCircuit,
        term: PauliTerm,
        backend: QuantumBackend,
        shots: int = 1024,
    ) -> float:
        """Measure expectation value of a Pauli term.

        Args:
            circuit: Ansatz circuit (without measurements).
            term: PauliTerm to measure.
            backend: Quantum backend.
            shots: Number of measurement shots.

        Returns:
            Expectation value estimate.
        """
        if not term.paulis:
            return float(term.coefficient.real)

        meas_circuit = circuit.copy()
        meas_circuit.add_register(circuit.qregs[0])

        measured_qubits = sorted(term.paulis.keys())

        for qubit, pauli in term.paulis.items():
            if pauli == "X":
                meas_circuit.h(qubit)
            elif pauli == "Y":
                meas_circuit.sdg(qubit)
                meas_circuit.h(qubit)

        meas_circuit.measure(measured_qubits, list(range(len(measured_qubits))))

        counts = backend.run(meas_circuit, shots=shots)

        expectation = 0.0
        for bitstring, count in counts.items():
            parity = sum(int(b) for b in bitstring) % 2
            expectation += (1 - 2 * parity) * count
        expectation /= shots

        return float(term.coefficient.real) * expectation

    def compute_expectation_statevector(
        self,
        circuit: QuantumCircuit,
        hamiltonian: Hamiltonian,
        backend: QuantumBackend,
    ) -> float:
        """Compute expectation value using statevector simulation.

        Args:
            circuit: Ansatz circuit.
            hamiltonian: Hamiltonian to measure.
            backend: Quantum backend with statevector support.

        Returns:
            Expectation value.
        """
        statevector = backend.get_statevector(circuit)
        H_matrix = hamiltonian.to_matrix()
        expectation = np.vdot(statevector, H_matrix @ statevector)
        return float(expectation.real)

    def compute_expectation_shots(
        self,
        circuit: QuantumCircuit,
        hamiltonian: Hamiltonian,
        backend: QuantumBackend,
        shots: int = 1024,
    ) -> float:
        """Compute expectation value using shot-based measurements.

        Args:
            circuit: Ansatz circuit.
            hamiltonian: Hamiltonian to measure.
            backend: Quantum backend.
            shots: Number of shots per term.

        Returns:
            Expectation value estimate.
        """
        total = 0.0
        for term in hamiltonian.terms:
            total += self.measure_pauli_term(circuit, term, backend, shots)
        return total

    def optimize(
        self,
        hamiltonian: Hamiltonian,
        backend: QuantumBackend,
        initial_params: NDArray[np.float64] | None = None,
        shots: int | None = None,
        maxiter: int = 100,
        callback: Callable[[NDArray[np.float64], float], None] | None = None,
    ) -> VQEResult:
        """Run VQE optimization to find ground state energy.

        Args:
            hamiltonian: Hamiltonian to minimize.
            backend: Quantum backend.
            initial_params: Optional initial parameter values.
            shots: Number of shots (None for statevector mode).
            maxiter: Maximum optimization iterations.
            callback: Optional callback(params, energy) at each iteration.

        Returns:
            VQEResult with optimal parameters and energy.
        """
        from scipy.optimize import minimize

        self._backend = backend
        num_params = self.get_num_parameters(hamiltonian.num_qubits)

        if initial_params is None:
            initial_params = self.rng.uniform(0, 2 * np.pi, num_params)

        history: list[float] = []

        def objective(params: NDArray[np.float64]) -> float:
            param_list = [Parameter(f"θ_{i}") for i in range(len(params))]
            circuit = self.build_ansatz(hamiltonian.num_qubits, param_list)

            bound_circuit = circuit.assign_parameters(dict(zip(param_list, params, strict=False)))

            if shots is None:
                energy = self.compute_expectation_statevector(bound_circuit, hamiltonian, backend)
            else:
                energy = self.compute_expectation_shots(bound_circuit, hamiltonian, backend, shots)

            history.append(energy)
            if callback:
                callback(params, energy)

            return energy

        result = minimize(
            objective,
            initial_params,
            method="COBYLA",
            options={"maxiter": maxiter},
        )

        eigenstate = None
        if shots is None:
            param_list = [Parameter(f"θ_{i}") for i in range(len(result.x))]
            circuit = self.build_ansatz(hamiltonian.num_qubits, param_list)
            bound_circuit = circuit.assign_parameters(dict(zip(param_list, result.x, strict=False)))
            eigenstate = backend.get_statevector(bound_circuit)

        return VQEResult(
            optimal_params=result.x,
            optimal_value=result.fun,
            eigenstate=eigenstate,
            num_iterations=len(history),
            history=history,
        )

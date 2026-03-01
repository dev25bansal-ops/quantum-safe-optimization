"""
Minimal statevector simulator.

A lightweight numpy-based simulator for testing and small circuits.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
from numpy.typing import NDArray

from qsop.domain.models.result import MeasurementResult, QuantumExecutionResult
from qsop.domain.ports.quantum_backend import BackendCapabilities

# Basic gate matrices
GATES = {
    "I": np.eye(2, dtype=complex),
    "X": np.array([[0, 1], [1, 0]], dtype=complex),
    "Y": np.array([[0, -1j], [1j, 0]], dtype=complex),
    "Z": np.array([[1, 0], [0, -1]], dtype=complex),
    "H": np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2),
    "S": np.array([[1, 0], [0, 1j]], dtype=complex),
    "T": np.array([[1, 0], [0, np.exp(1j * np.pi / 4)]], dtype=complex),
    "CNOT": np.array(
        [
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 0, 1],
            [0, 0, 1, 0],
        ],
        dtype=complex,
    ),
    "CZ": np.array(
        [
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, -1],
        ],
        dtype=complex,
    ),
    "SWAP": np.array(
        [
            [1, 0, 0, 0],
            [0, 0, 1, 0],
            [0, 1, 0, 0],
            [0, 0, 0, 1],
        ],
        dtype=complex,
    ),
}


def rx(theta: float) -> NDArray:
    """Rotation around X axis."""
    c, s = np.cos(theta / 2), np.sin(theta / 2)
    return np.array([[c, -1j * s], [-1j * s, c]], dtype=complex)


def ry(theta: float) -> NDArray:
    """Rotation around Y axis."""
    c, s = np.cos(theta / 2), np.sin(theta / 2)
    return np.array([[c, -s], [s, c]], dtype=complex)


def rz(theta: float) -> NDArray:
    """Rotation around Z axis."""
    return np.array(
        [
            [np.exp(-1j * theta / 2), 0],
            [0, np.exp(1j * theta / 2)],
        ],
        dtype=complex,
    )


@dataclass
class StatevectorSimulator:
    """
    Minimal statevector simulator for testing.

    Supports basic gates and measurements on small circuits.
    """

    name: str = "statevector"
    _rng: np.random.Generator = field(
        default_factory=lambda: np.random.default_rng(),
        repr=False,
    )
    _pending_jobs: dict[str, QuantumExecutionResult] = field(
        default_factory=dict,
        repr=False,
    )

    @property
    def capabilities(self) -> BackendCapabilities:
        """Return backend capabilities."""
        return BackendCapabilities(
            name=self.name,
            num_qubits=20,
            basis_gates=frozenset(
                ["i", "x", "y", "z", "h", "s", "t", "rx", "ry", "rz", "u", "u3", "cx", "cz", "swap"]
            ),
            max_shots=100000,
            simulator=True,
            local=True,
            metadata={
                "supports_statevector": True,
                "supports_density_matrix": False,
                "gpu_acceleration": False,
            },
        )

    def transpile(self, circuit: Any, optimization_level: int = 1, **options: Any) -> Any:
        """No compilation needed for this simulator."""
        return circuit

    def compile(self, circuit: Any, *, options: dict | None = None) -> Any:
        """Legacy compilation method."""
        return self.transpile(circuit)

    def run(
        self,
        circuit: Any,
        shots: int = 1024,
        **options: Any,
    ) -> QuantumExecutionResult:
        """
        Run circuit and return measurement results.

        Supports Qiskit circuits or internal circuit format.
        """
        seed = options.get("seed")
        if seed is not None:
            self._rng = np.random.default_rng(seed)

        # Try to convert Qiskit circuit
        if hasattr(circuit, "num_qubits"):
            return self._run_qiskit_circuit(circuit, shots)

        # Internal format: list of (gate_name, qubits, params)
        return self._run_internal_circuit(circuit, shots)

    def _run_qiskit_circuit(self, circuit: Any, shots: int) -> QuantumExecutionResult:
        """Execute a Qiskit circuit."""
        n_qubits = circuit.num_qubits
        start_time = datetime.utcnow()
        state = self._initialize_state(n_qubits)

        # Execute gates
        for instruction in circuit.data:
            gate_name = instruction.operation.name
            qubits = [circuit.find_bit(q).index for q in instruction.qubits]
            params = instruction.operation.params

            state = self._apply_gate(state, gate_name, qubits, params, n_qubits)

        # Measure
        counts = self._measure(state, shots, n_qubits)
        end_time = datetime.utcnow()

        total_shots = sum(counts.values())
        measurements = tuple(
            MeasurementResult(
                bitstring=bs, count=cnt, probability=cnt / total_shots if total_shots > 0 else 0.0
            )
            for bs, cnt in counts.items()
        )

        return QuantumExecutionResult(
            measurements=measurements,
            counts=counts,
            num_qubits=n_qubits,
            shots=shots,
            execution_time_seconds=(end_time - start_time).total_seconds(),
            backend_name=self.name,
            timestamp=start_time,
            metadata={"backend": self.name},
        )

    def _run_internal_circuit(
        self,
        circuit: list[tuple],
        shots: int,
    ) -> QuantumExecutionResult:
        """Execute internal circuit format."""
        # Infer number of qubits
        n_qubits = 0
        for gate_name, qubits, params in circuit:
            if isinstance(qubits, int):
                n_qubits = max(n_qubits, qubits + 1)
            else:
                n_qubits = max(n_qubits, max(qubits) + 1)

        start_time = datetime.utcnow()
        state = self._initialize_state(n_qubits)

        for gate_name, qubits, params in circuit:
            if isinstance(qubits, int):
                qubits = [qubits]
            state = self._apply_gate(state, gate_name, qubits, params, n_qubits)

        counts = self._measure(state, shots, n_qubits)
        end_time = datetime.utcnow()

        total_shots = sum(counts.values())
        measurements = tuple(
            MeasurementResult(
                bitstring=bs, count=cnt, probability=cnt / total_shots if total_shots > 0 else 0.0
            )
            for bs, cnt in counts.items()
        )

        return QuantumExecutionResult(
            measurements=measurements,
            counts=counts,
            num_qubits=n_qubits,
            shots=shots,
            execution_time_seconds=(end_time - start_time).total_seconds(),
            backend_name=self.name,
            timestamp=start_time,
            metadata={"backend": self.name},
        )

    def _initialize_state(self, n_qubits: int) -> NDArray:
        """Initialize |0...0> state."""
        dim = 2**n_qubits
        state = np.zeros(dim, dtype=complex)
        state[0] = 1.0
        return state

    def _apply_gate(
        self,
        state: NDArray,
        gate_name: str,
        qubits: list[int],
        params: list[float],
        n_qubits: int,
    ) -> NDArray:
        """Apply a gate to the state."""
        gate_name = gate_name.upper()

        # Handle measurement (skip, will measure at end)
        if gate_name in ["MEASURE", "BARRIER"]:
            return state

        # Get gate matrix
        if gate_name == "RX":
            gate = rx(params[0])
        elif gate_name == "RY":
            gate = ry(params[0])
        elif gate_name == "RZ":
            gate = rz(params[0])
        elif gate_name == "U" or gate_name == "U3":
            # General rotation U(theta, phi, lambda)
            theta, phi, lam = params[0], params[1], params[2]
            gate = np.array(
                [
                    [np.cos(theta / 2), -np.exp(1j * lam) * np.sin(theta / 2)],
                    [
                        np.exp(1j * phi) * np.sin(theta / 2),
                        np.exp(1j * (phi + lam)) * np.cos(theta / 2),
                    ],
                ],
                dtype=complex,
            )
        elif gate_name in GATES:
            gate = GATES[gate_name]
        elif gate_name == "CX":
            gate = GATES["CNOT"]
        else:
            # Default to identity for unknown gates
            return state

        # Apply gate
        if len(qubits) == 1:
            return self._apply_single_qubit_gate(state, gate, qubits[0], n_qubits)
        elif len(qubits) == 2:
            return self._apply_two_qubit_gate(state, gate, qubits[0], qubits[1], n_qubits)

        return state

    def _apply_single_qubit_gate(
        self,
        state: NDArray,
        gate: NDArray,
        qubit: int,
        n_qubits: int,
    ) -> NDArray:
        """Apply single-qubit gate using tensor operations.

        Statevector uses little-endian: qubit k is at bit position k.
        Kronecker product builds from high to low bit, so we place the gate
        at position (n_qubits - 1 - qubit) in the ops list, but since kron
        goes left-to-right as high-to-low bits, we actually want the gate
        at the rightmost position for qubit 0.

        ops[0] @ ops[1] @ ... @ ops[n-1] via kron gives:
        ops[0] controls highest bit, ops[n-1] controls lowest bit.
        So for qubit k, we place gate at ops[n_qubits - 1 - k].
        """
        # Build full operator using Kronecker products
        ops = [np.eye(2)] * n_qubits
        # qubit k -> position (n_qubits - 1 - k) in kron order
        ops[n_qubits - 1 - qubit] = gate

        full_op = ops[0]
        for op in ops[1:]:
            full_op = np.kron(full_op, op)

        return full_op @ state

    def _apply_two_qubit_gate(
        self,
        state: NDArray,
        gate: NDArray,
        qubit1: int,
        qubit2: int,
        n_qubits: int,
    ) -> NDArray:
        """Apply two-qubit gate.

        Gate matrix uses standard ordering: |q1 q2> where q1 is high bit.
        qubit1 = control (or first qubit), qubit2 = target (or second qubit).

        Statevector uses little-endian: index i has q_k at bit position k.
        So qubit k's value in state index i is: (i >> k) & 1
        """
        dim = 2**n_qubits
        new_state = np.zeros(dim, dtype=complex)

        for i in range(dim):
            # Extract qubit values directly (little-endian: qubit k at bit k)
            bit1 = (i >> qubit1) & 1  # first qubit (control) value
            bit2 = (i >> qubit2) & 1  # second qubit (target) value

            # Map to gate matrix index: |q1, q2> where q1 is high bit
            basis_in = (bit1 << 1) | bit2

            for basis_out in range(4):
                coeff = gate[basis_out, basis_in]
                if coeff == 0:
                    continue

                # Extract output bits from basis_out
                new_bit1 = (basis_out >> 1) & 1
                new_bit2 = basis_out & 1

                # Build new state index by replacing bits
                j = i
                j = (j & ~(1 << qubit1)) | (new_bit1 << qubit1)
                j = (j & ~(1 << qubit2)) | (new_bit2 << qubit2)

                new_state[j] += coeff * state[i]

        return new_state

    def _measure(
        self,
        state: NDArray,
        shots: int,
        n_qubits: int,
    ) -> dict[str, int]:
        """Perform measurement and return counts."""
        probabilities = np.abs(state) ** 2

        # Normalize (handle numerical errors)
        probabilities = probabilities / probabilities.sum()

        # Sample outcomes
        outcomes = self._rng.choice(
            len(state),
            size=shots,
            p=probabilities,
        )

        # Count occurrences
        counts: dict[str, int] = {}
        for outcome in outcomes:
            bitstring = format(outcome, f"0{n_qubits}b")
            counts[bitstring] = counts.get(bitstring, 0) + 1

        return counts

    def submit(
        self,
        circuit: Any,
        shots: int = 1024,
        **options: Any,
    ) -> str:
        """Submit for async execution."""
        job_id = str(uuid.uuid4())
        # For simulator, we run synchronously but store in pending
        result = self.run(circuit, shots=shots, **options)
        self._pending_jobs[job_id] = result
        return job_id

    def get_result(self, job_id: str) -> QuantumExecutionResult:
        """Get result of submitted job."""
        if job_id not in self._pending_jobs:
            raise ValueError(f"Job {job_id} not found")
        return self._pending_jobs.pop(job_id)

    def get_job_status(self, job_id: str) -> str:
        """Get status of a submitted job."""
        if job_id in self._pending_jobs:
            return "DONE"
        return "NOT_FOUND"

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a submitted job."""
        if job_id in self._pending_jobs:
            self._pending_jobs.pop(job_id)
            return True
        return False

    def get_statevector(self, circuit: Any) -> NDArray:
        """Get final statevector without measurement."""
        if hasattr(circuit, "num_qubits"):
            n_qubits = circuit.num_qubits
            state = self._initialize_state(n_qubits)

            for instruction in circuit.data:
                if instruction.operation.name.lower() == "measure":
                    continue
                gate_name = instruction.operation.name
                qubits = [circuit.find_bit(q).index for q in instruction.qubits]
                params = instruction.operation.params
                state = self._apply_gate(state, gate_name, qubits, params, n_qubits)

            return state

        raise ValueError("Unsupported circuit format")

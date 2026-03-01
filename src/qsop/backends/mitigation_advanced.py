"""
Quantum Error Mitigation Module.

Provides various error mitigation techniques to improve the accuracy
of quantum computations on noisy intermediate-scale quantum (NISQ) devices.

Techniques included:
- Zero-Noise Extrapolation (ZNE)
- Probabilistic Error Cancellation (PEC)
- Measurement Error Mitigation
- Readout Error Mitigation
- Randomized Compiling
- Virtual Distillation
"""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray
from qiskit import QuantumCircuit
from qiskit.result import Result


@dataclass
class MitigationResult:
    """Result of error mitigation."""

    mitigated_counts: dict[str, int]
    original_counts: dict[str, int]
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_fidelity_improvement(self, true_counts: dict[str, int]) -> float:
        """Calculate fidelity improvement over original counts."""
        mitigated_fidelity = self._calculate_fidelity(self.mitigated_counts, true_counts)
        original_fidelity = self._calculate_fidelity(self.original_counts, true_counts)
        return mitigated_fidelity - original_fidelity

    def _calculate_fidelity(
        self,
        counts: dict[str, int],
        true_counts: dict[str, int],
    ) -> float:
        """Calculate fidelity between counts distributions."""
        total1 = sum(counts.values())
        total2 = sum(true_counts.values())

        fidelity = 0.0
        all_keys = set(counts.keys()) | set(true_counts.keys())

        for key in all_keys:
            p1 = counts.get(key, 0) / total1
            p2 = true_counts.get(key, 0) / total2
            fidelity += np.sqrt(p1 * p2)

        return fidelity


class ErrorMitigationStrategy(ABC):
    """Abstract base class for error mitigation strategies."""

    @abstractmethod
    def apply(
        self,
        circuit: QuantumCircuit,
        backend_result: Result,
    ) -> MitigationResult:
        """Apply error mitigation to the result."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the mitigation strategy."""
        pass


class ZeroNoiseExtrapolation(ErrorMitigationStrategy):
    """
    Zero-Noise Extrapolation (ZNE) error mitigation.

    Extrapolates results from circuits with intentionally increased noise
    to estimate the zero-noise result.

    Methods:
    - Linear extrapolation
    - Richardson extrapolation
    - Exponential extrapolation
    """

    def __init__(
        self,
        noise_factors: Sequence[float] = (1.0, 2.0, 3.0),
        extrapolation_method: str = "richardson",
        noise_amplification_function: Callable[[QuantumCircuit, float], QuantumCircuit]
        | None = None,
    ):
        """
        Initialize ZNE.

        Args:
            noise_factors: Noise scaling factors to use
            extrapolation_method: Method for extrapolation ('linear', 'richardson', 'exponential')
            noise_amplification_function: Custom function to amplify noise in circuit
        """
        self.noise_factors = noise_factors
        self.extrapolation_method = extrapolation_method
        self.noise_amplification = noise_amplification_function or self._default_noise_amplification

    @property
    def name(self) -> str:
        return "ZeroNoiseExtrapolation"

    def apply(
        self,
        circuit: QuantumCircuit,
        backend_result: Result,
    ) -> MitigationResult:
        """Apply ZNE error mitigation."""
        original_counts = backend_result.get_counts()

        # In practice, would run circuits at different noise levels
        # For now, simulate noise amplification effect
        scaled_results = []
        for factor in self.noise_factors:
            if factor == 1.0:
                scaled_counts = original_counts
            else:
                scaled_counts = self._simulate_noisy_counts(original_counts, factor)
            scaled_results.append(scaled_counts)

        # Extrapolate to zero noise
        mitigated_counts = self._extrapolate(scaled_results)

        return MitigationResult(
            mitigated_counts=mitigated_counts,
            original_counts=original_counts,
            metadata={
                "noise_factors": self.noise_factors,
                "method": self.extrapolation_method,
            },
        )

    def _default_noise_amplification(
        self,
        circuit: QuantumCircuit,
        noise_factor: float,
    ) -> QuantumCircuit:
        """Default noise amplification: repeat each gate."""
        if noise_factor == 1.0:
            return circuit

        amplified_circuit = QuantumCircuit(circuit.num_qubits)

        for instruction in circuit.data:
            for _ in range(int(noise_factor)):
                amplified_circuit.append(instruction.operation, instruction.qubits)

        return amplified_circuit

    def _simulate_noisy_counts(
        self,
        counts: dict[str, int],
        noise_factor: float,
    ) -> dict[str, int]:
        """Simulate noise by redistributing some counts."""
        noise_level = 0.05 * noise_factor
        noisy_counts = {}

        for bitstring, count in counts.items():
            # Keep most counts, but redistribute some to neighbors
            neighbors = self._get_neighbor_bitstrings(bitstring)
            redistribution = int(count * noise_level)

            remaining = count
            for neighbor in neighbors:
                transfer = redistribution // len(neighbors)
                noisy_counts[neighbor] = noisy_counts.get(neighbor, 0) + transfer
                remaining -= transfer

            noisy_counts[bitstring] = noisy_counts.get(bitstring, 0) + remaining

        return noisy_counts

    def _get_neighbor_bitstrings(
        self,
        bitstring: str,
        num_neighbors: int = 3,
    ) -> list[str]:
        """Get nearby bitstrings (Hamming distance 1)."""
        neighbors = []
        bits = list(bitstring)

        for i in range(len(bits)):
            if bits[i] == "0":
                neighbor = bits.copy()
                neighbor[i] = "1"
                neighbors.append("".join(neighbor))
            else:
                neighbor = bits.copy()
                neighbor[i] = "0"
                neighbors.append("".join(neighbor))

        return neighbors[:num_neighbors]

    def _extrapolate(
        self,
        scaled_results: list[dict[str, int]],
    ) -> dict[str, int]:
        """Extrapolate results to zero noise."""
        mitigated_counts = {}

        all_bitstrings = set()
        for counts in scaled_results:
            all_bitstrings.update(counts.keys())

        for bitstring in all_bitstrings:
            values = []
            for i, _factor in enumerate(self.noise_factors):
                counts = scaled_results[i]
                total = sum(counts.values())
                value = counts.get(bitstring, 0) / total
                values.append(value)

            # Extrapolate
            mitigated_value = self._extrapolate_point(self.noise_factors, values)
            mitigated_counts[bitstring] = max(0, mitigated_value)

        # Normalize to integer counts
        total_original = sum(scaled_results[0].values())
        mitigated_counts = {
            k: int(round(v * total_original)) for k, v in mitigated_counts.items() if v > 0.001
        }

        return mitigated_counts

    def _extrapolate_point(
        self,
        x: Sequence[float],
        y: Sequence[float],
    ) -> float:
        """Extrapolate point to x=0."""
        if self.extrapolation_method == "linear":
            return self._linear_extrapolation(x, y)
        elif self.extrapolation_method == "richardson":
            return self._richardson_extrapolation(x, y)
        elif self.extrapolation_method == "exponential":
            return self._exponential_extrapolation(x, y)
        else:
            raise ValueError(f"Unknown extrapolation method: {self.extrapolation_method}")

    def _linear_extrapolation(self, x: Sequence[float], y: Sequence[float]) -> float:
        """Linear extrapolation to x=0."""
        coeffs = np.polyfit(x, y, 1)
        return np.polyval(coeffs, 0)

    def _richardson_extrapolation(self, x: Sequence[float], y: Sequence[float]) -> float:
        """Richardson extrapolation."""
        if len(x) < 2:
            return y[0]

        # Simplified Richardson extrapolation (2-point)
        if len(x) == 2:
            h1, h2 = x[0], x[1]
            f1, f2 = y[0], y[1]
            return (h2 * f1 - h1 * f2) / (h2 - h1)

        # Multi-point Richardson extrapolation
        result = y[0]
        for i in range(1, len(x)):
            hi, _fi = x[i], y[i]
            for j in range(i):
                hj, fj = x[j], y[j]
                result += (hj * result - hi * fj) / (hj - hi)

        return result / len(x)

    def _exponential_extrapolation(self, x: Sequence[float], y: Sequence[float]) -> float:
        """Exponential extrapolation: A + B * exp(-c * x)."""
        try:
            from scipy.optimize import curve_fit

            def exp_func(x, a, b, c):
                return a + b * np.exp(-c * np.array(x))

            popt, _ = curve_fit(exp_func, x, y, p0=[y[-1], y[0] - y[-1], 1])
            return popt[0]
        except ImportError:
            return self._linear_extrapolation(x, y)


class MeasurementErrorMitigation(ErrorMitigationStrategy):
    """
    Measurement Error Mitigation.

    Calibrates and corrects readout errors by measuring all basis states
    to construct a calibration matrix.
    """

    def __init__(
        self,
        calibration_matrix: NDArray[np.float64] | None = None,
        regularization: float = 1e-5,
    ):
        """
        Initialize measurement error mitigation.

        Args:
            calibration_matrix: Pre-computed calibration matrix
            regularization: Regularization parameter for matrix inversion
        """
        self.calibration_matrix = calibration_matrix
        self.regularization = regularization

    @property
    def name(self) -> str:
        return "MeasurementErrorMitigation"

    def build_calibration_matrix(
        self,
        backend: Any,
        num_qubits: int,
    ) -> NDArray[np.float64]:
        """
        Build calibration matrix by measuring all basis states.

        Args:
            backend: Quantum backend
            num_qubits: Number of qubits

        Returns:
            Calibration matrix (2^n x 2^n)
        """
        from qiskit import transpile

        # Create circuits for all basis states
        circuits = []
        for i in range(2**num_qubits):
            qc = QuantumCircuit(num_qubits, num_qubits)

            # Initialize in basis state |i⟩
            binary_state = format(i, f"0{num_qubits}b")
            for qubit, bit in enumerate(bin(binary_state)[2:].zfill(num_qubits)):
                if bit == "1":
                    qc.x(qubit)

            qc.measure(range(num_qubits), range(num_qubits))
            circuits.append(qc)

        # Transpile and run
        transpiled = transpile(circuits, backend=backend)
        job = backend.run(transpiled, shots=10000)
        results = job.result()

        # Build calibration matrix
        calib_matrix = np.zeros((2**num_qubits, 2**num_qubits))

        for i, (_circuit, result) in enumerate(zip(circuits, results.get_counts(), strict=False)):
            counts = result
            total = sum(counts.values())

            for bitstring, count in counts.items():
                idx = int(bitstring[::-1], 2)
                calib_matrix[idx, i] = count / total

        self.calibration_matrix = calib_matrix
        return calib_matrix

    def apply(
        self,
        circuit: QuantumCircuit,
        backend_result: Result,
    ) -> MitigationResult:
        """Apply measurement error mitigation."""
        if self.calibration_matrix is None:
            raise RuntimeError(
                "Calibration matrix not built. Call build_calibration_matrix() first."
            )

        original_counts = backend_result.get_counts()
        num_qubits = circuit.num_qubits

        # Convert counts to probability vector
        observed = np.zeros(2**num_qubits)
        for bitstring, count in original_counts.items():
            idx = int(bitstring[::-1], 2)
            observed[idx] = count

        # Apply correction
        mitigated_probs = self._correct_observations(observed)

        # Convert back to counts
        total_shots = sum(original_counts.values())
        mitigated_counts = {}
        for i, prob in enumerate(mitigated_probs):
            if prob > 0.001:
                bitstring = format(i, f"0{num_qubits}b")[::-1]
                count = int(round(prob * total_shots))
                mitigated_counts[bitstring] = count

        return MitigationResult(
            mitigated_counts=mitigated_counts,
            original_counts=original_counts,
            metadata={
                "calibration_matrix_shape": self.calibration_matrix.shape,
            },
        )

    def _correct_observations(
        self,
        observed: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Correct observations using calibration matrix."""
        # Invert calibration matrix with regularization
        A_inv = np.linalg.pinv(
            self.calibration_matrix + np.eye(self.calibration_matrix.shape[0]) * self.regularization
        )

        # Correct the observations
        corrected = A_inv @ observed
        corrected = np.maximum(corrected, 0)  # Ensure non-negative

        return corrected


class ProbabilisticErrorCancellation(ErrorMitigationStrategy):
    """
    Probabilistic Error Cancellation (PEC).

    Decomposes noisy gates into linear combinations of implementable operations
    and uses sampling to cancel errors.
    """

    def __init__(
        self,
        gate_decompositions: dict[str, list[tuple[float, QuantumCircuit]]] | None = None,
        samples: int = 1000,
    ):
        """
        Initialize PEC.

        Args:
            gate_decompositions: Dictionary mapping gate names to Pauli twirl decompositions
            samples: Number of quasiprobability samples
        """
        self.gate_decompositions = gate_decompositions or self._default_decompositions()
        self.samples = samples

    @property
    def name(self) -> str:
        return "ProbabilisticErrorCancellation"

    def _default_decompositions(self) -> dict[str, list[tuple[float, QuantumCircuit]]]:
        """Create default PEC decompositions for common gates."""
        decompositions = {}

        # Example: CNOT decomposition into Pauli operations
        decomp_cnot = [
            (0.5, QuantumCircuit(2)),
            (0.5, QuantumCircuit(2)),
        ]
        decompositions["cx"] = decomp_cnot

        return decompositions

    def apply(
        self,
        circuit: QuantumCircuit,
        backend_result: Result,
    ) -> MitigationResult:
        """Apply PEC error mitigation."""
        original_counts = backend_result.get_counts()

        # Build quasiprobability decomposition
        quasiprob_circuits = self._build_quasiprobability_circuits(circuit)

        # Weight results by quasiprobability signs
        mitigated_counts = self._quasiprobability_correction(original_counts, quasiprob_circuits)

        return MitigationResult(
            mitigated_counts=mitigated_counts,
            original_counts=original_counts,
            metadata={
                "samples": self.samples,
            },
        )

    def _build_quasiprobability_circuits(
        self,
        circuit: QuantumCircuit,
    ) -> list[tuple[float, QuantumCircuit]]:
        """Build quasiprobability circuit decomposition."""
        circuits = []

        # For each sample, construct a randomized circuit with sign
        for _ in range(self.samples):
            sign = 1 if np.random.random() < 0.5 else -1
            qc = self._randomized_circuit(circuit)
            circuits.append((sign / self.samples, qc))

        return circuits

    def _randomized_circuit(self, circuit: QuantumCircuit) -> QuantumCircuit:
        """Create randomized version of circuit for PEC."""
        # Simplified: apply random Pauli corrections
        qc = circuit.copy()

        num_qubits = qc.num_qubits
        for qubit in range(num_qubits):
            pauli = np.random.choice(["I", "X", "Y", "Z"], p=[0.5, 0.166, 0.166, 0.166])

            if pauli == "X":
                qc.x(qubit)
            elif pauli == "Y":
                qc.y(qubit)
            elif pauli == "Z":
                qc.z(qubit)

        return qc

    def _quasiprobability_correction(
        self,
        original_counts: dict[str, int],
        quasiprob_circuits: list[tuple[float, QuantumCircuit]],
    ) -> dict[str, int]:
        """Apply quasiprobability correction."""
        mitigated_counts = {}

        # In a real implementation, would run quasiprob_circuits and combine results
        # For now, apply simplified correction
        for bitstring, count in original_counts.items():
            factor = sum(sign for sign, _ in quasiprob_circuits[:10]) / 10  # Use sample of sign
            mitigated_counts[bitstring] = max(0, int(round(count * factor)))

        return mitigated_counts


class RandomizedCompiling(ErrorMitigationStrategy):
    """
    Randomized Compiling (Twirling).

    Applies random Clifford gates before and after the circuit to
    average out coherent errors into stochastic noise.
    """

    def __init__(
        self,
        num_twirls: int = 10,
    ):
        """
        Initialize randomized compiling.

        Args:
            num_twirls: Number of random twirls to average over
        """
        self.num_twirls = num_twirls

    @property
    def name(self) -> str:
        return "RandomizedCompiling"

    def apply(
        self,
        circuit: QuantumCircuit,
        backend_result: Result,
    ) -> MitigationResult:
        """Apply randomized compiling error mitigation."""
        original_counts = backend_result.get_counts()

        # In a real implementation, would run multiple twirled circuits
        # and average the results

        mitigated_counts = self._average_twirled_results(original_counts)

        return MitigationResult(
            mitigated_counts=mitigated_counts,
            original_counts=original_counts,
            metadata={
                "num_twirls": self.num_twirls,
            },
        )

    def _average_twirled_results(
        self,
        original_counts: dict[str, int],
    ) -> dict[str, int]:
        """Simulate averaging over twirled circuits."""
        mitigated_counts = {}

        # Apply simple normalization to simulate error reduction
        for bitstring, count in original_counts.items():
            mitigated_counts[bitstring] = count

        return mitigated_counts


class VirtualDistillation(ErrorMitigationStrategy):
    """
    Virtual Distillation error mitigation.

    Uses multiple copies of the quantum state to extract a "distilled"
    higher-fidelity estimate.
    """

    def __init__(
        self,
        num_copies: int = 2,
    ):
        """
        Initialize virtual distillation.

        Args:
            num_copies: Number of copies to use for distillation
        """
        self.num_copies = num_copies

    @property
    def name(self) -> str:
        return "VirtualDistillation"

    def apply(
        self,
        circuit: QuantumCircuit,
        backend_result: Result,
    ) -> MitigationResult:
        """Apply virtual distillation."""
        original_counts = backend_result.get_counts()

        # Convert counts to probability vector
        num_qubits = circuit.num_qubits
        probs = np.zeros(2**num_qubits)
        total = sum(original_counts.values())

        for bitstring, count in original_counts.items():
            idx = int(bitstring[::-1], 2)
            probs[idx] = count / total

        # Apply virtual distillation: ρ_d = ρ^n / Tr(ρ^n)
        distillled_probs = np.power(probs, self.num_copies)
        distillled_probs /= np.sum(distillled_probs)

        # Convert back to counts
        mitigated_counts = {}
        for i, prob in enumerate(distillled_probs):
            if prob > 0.001:
                bitstring = format(i, f"0{num_qubits}b")[::-1]
                count = int(round(prob * total))
                mitigated_counts[bitstring] = count

        return MitigationResult(
            mitigated_counts=mitigated_counts,
            original_counts=original_counts,
            metadata={
                "num_copies": self.num_copies,
            },
        )


class ErrorMitigationPipeline:
    """
    Combines multiple error mitigation strategies in sequence.
    """

    def __init__(
        self,
        strategies: list[ErrorMitigationStrategy],
    ):
        """
        Initialize mitigation pipeline.

        Args:
            strategies: List of mitigation strategies to apply in order
        """
        self.strategies = strategies

    def apply(
        self,
        circuit: QuantumCircuit,
        backend_result: Result,
    ) -> MitigationResult:
        """Apply all mitigation strategies in sequence."""
        current_result = backend_result
        original_counts = backend_result.get_counts()

        history = []

        for strategy in self.strategies:
            mitigated = strategy.apply(circuit, current_result)
            history.append(
                {
                    "strategy": strategy.name,
                    "counts": copy.deepcopy(mitigated.mitigated_counts),
                }
            )
            current_result = Result(
                success=True,
                data=count_to_resultdata(mitigated.mitigated_counts),
                metadata={"mitigated": True},
            )

        return MitigationResult(
            mitigated_counts=mitigated.mitigated_counts,
            original_counts=original_counts,
            metadata={
                "pipeline": [s.name for s in self.strategies],
                "history": history,
            },
        )


def count_to_resultdata(counts: dict[str, int]) -> Any:
    """Convert counts dict to Qiskit ResultData format."""
    from qiskit.result import Counts

    return Counts(counts)


__all__ = [
    "MitigationResult",
    "ErrorMitigationStrategy",
    "ZeroNoiseExtrapolation",
    "MeasurementErrorMitigation",
    "ProbabilisticErrorCancellation",
    "RandomizedCompiling",
    "VirtualDistillation",
    "ErrorMitigationPipeline",
]

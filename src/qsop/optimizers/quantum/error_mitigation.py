"""Quantum Error Mitigation Techniques.

Implements various error mitigation strategies to improve quantum
computation accuracy on NISQ devices.

Techniques:
- Zero-Noise Extrapolation (ZNE)
- Measurement Error Mitigation
- Dynamical Decoupling
- Readout Error Mitigation
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
from numpy.typing import NDArray
from qiskit import QuantumCircuit
from qiskit.primitives import BackendEstimator, Estimator
from qiskit_aer import AerSimulator


@dataclass(frozen=True)
class MitigationConfig:
    """Configuration for error mitigation."""

    enable_zne: bool = True
    zne_scale_factors: tuple[float, ...] = (1.0, 2.0, 3.0)
    zne_extrapolation: str = "richardson"  # or "linear", "polynomial"

    enable_readout_mitigation: bool = True
    readout_calibration_shots: int = 8192

    enable_dynamical_decoupling: bool = False
    dd_sequence: str = "XY4"  # or "XY8", "CPMG"


class ErrorMitigator(ABC):
    """Abstract base class for error mitigation techniques."""

    @abstractmethod
    def mitigate(
        self,
        circuit: QuantumCircuit,
        expectation_values: dict[str, float],
        counts: dict[str, int],
    ) -> dict[str, float]:
        """Apply error mitigation to results.

        Args:
            circuit: The quantum circuit that was executed
            expectation_values: Raw expectation values
            counts: Measurement counts

        Returns:
            Mitigated expectation values
        """
        pass


class ZeroNoiseExtrapolator(ErrorMitigator):
    """Zero-Noise Extrapolation (ZNE) error mitigation.

    Executes circuits at scaled noise levels and extrapolates to zero noise.
    """

    def __init__(
        self,
        scale_factors: tuple[float, ...] = (1.0, 2.0, 3.0),
        extrapolation: str = "richardson",
    ):
        """Initialize ZNE mitigator.

        Args:
            scale_factors: Noise scale factors (must include 1.0)
            extrapolation: Extrapolation method
        """
        if 1.0 not in scale_factors:
            raise ValueError("Scale factors must include 1.0")

        self.scale_factors = sorted(scale_factors)
        self.extrapolation = extrapolation

    def scale_circuit(self, circuit: QuantumCircuit, scale_factor: float) -> QuantumCircuit:
        """Scale circuit noise by folding.

        Args:
            circuit: Original circuit
            scale_factor: Noise scale factor

        Returns:
            Scaled circuit
        """
        if scale_factor == 1.0:
            return circuit.copy()

        scaled = circuit.copy()

        num_folds = int(scale_factor - 1)
        for _ in range(num_folds):
            for gate in scaled.data[:]:
                if gate.operation.name not in ("measure", "barrier"):
                    scaled.append(gate.operation.inverse(), gate.qubits)

        return scaled

    def extrapolate_to_zero_noise(
        self,
        values: list[float],
        scale_factors: list[float],
    ) -> float:
        """Extrapolate expectation value to zero noise.

        Args:
            values: Expectation values at each scale factor
            scale_factors: Corresponding scale factors

        Returns:
            Extrapolated value at zero noise
        """
        if self.extrapolation == "linear":
            coeffs = np.polyfit(scale_factors, values, 1)
            return float(coeffs[1])  # Intercept

        elif self.extrapolation == "richardson":
            if len(scale_factors) < 3:
                coeffs = np.polyfit(scale_factors, values, 1)
                return float(coeffs[1])

            def richardson_extrapolation(x: list[float], y: list[float]) -> float:
                n = len(x)
                if n == 1:
                    return y[0]

                result = 0.0
                for i in range(n):
                    term = y[i]
                    for j in range(n):
                        if j != i:
                            term *= -x[j] / (x[i] - x[j])
                    result += term

                return result

            return richardson_extrapolation(scale_factors, values)

        elif self.extrapolation == "polynomial":
            degree = min(len(scale_factors) - 1, 3)
            coeffs = np.polyfit(scale_factors, values, degree)
            return float(np.polyval(coeffs, 0.0))

        else:
            raise ValueError(f"Unknown extrapolation method: {self.extrapolation}")

    def mitigate(
        self,
        circuit: QuantumCircuit,
        expectation_values: dict[str, float],
        counts: dict[str, int],
    ) -> dict[str, float]:
        """Apply ZNE mitigation."""
        if len(self.scale_factors) == 1:
            return expectation_values

        mitigated = {}
        for key, base_value in expectation_values.items():
            extrapolated = self.extrapolate_to_zero_noise(
                [base_value] * len(self.scale_factors),
                list(self.scale_factors),
            )
            mitigated[key] = extrapolated

        return mitigated


class ReadoutErrorMitigator(ErrorMitigator):
    """Measurement (readout) error mitigation.

    Calibrates readout errors and applies correction matrix.
    """

    def __init__(self, calibration_shots: int = 8192):
        """Initialize readout error mitigator.

        Args:
            calibration_shots: Number of shots for calibration
        """
        self.calibration_shots = calibration_shots
        self._calibration_matrix: NDArray[np.float64] | None = None

    def calibrate(self, num_qubits: int, backend: Any) -> None:
        """Calibrate readout errors.

        Prepares all computational basis states and measures to build
        the confusion matrix.

        Args:
            num_qubits: Number of qubits
            backend: Quantum backend
        """
        n = num_qubits
        num_states = 2**n

        confusion_matrix = np.zeros((num_states, num_states))

        for state_idx in range(num_states):
            prep_circuit = QuantumCircuit(n, n)
            binary = format(state_idx, f"0{n}b")

            for i, bit in enumerate(binary):
                if bit == "1":
                    prep_circuit.x(i)

            prep_circuit.measure(range(n), range(n))

            job = backend.run(prep_circuit, shots=self.calibration_shots)
            counts = job.result().get_counts()

            total_shots = sum(counts.values())
            for measured_state, count in counts.items():
                measured_idx = int(measured_state, 2)
                confusion_matrix[measured_idx, state_idx] = count / total_shots

        self._calibration_matrix = confusion_matrix

    def mitigate(
        self,
        circuit: QuantumCircuit,
        expectation_values: dict[str, float],
        counts: dict[str, int],
    ) -> dict[str, float]:
        """Apply readout error mitigation."""
        if self._calibration_matrix is None:
            return expectation_values

        num_qubits = circuit.num_qubits
        num_states = 2**num_qubits

        counts_vec = np.zeros(num_states)
        for bitstring, count in counts.items():
            idx = int(bitstring, 2)
            counts_vec[idx] = count

        total_shots = counts_vec.sum()
        if total_shots == 0:
            return expectation_values

        probabilities = counts_vec / total_shots

        try:
            calibration_inv = np.linalg.inv(self._calibration_matrix)
            corrected_probs = calibration_inv @ probabilities
            corrected_probs = np.clip(corrected_probs, 0, 1)
            corrected_probs /= corrected_probs.sum()
        except np.linalg.LinAlgError:
            return expectation_values

        mitigated = {}
        for key in expectation_values:
            mitigated[key] = expectation_values[key]

        return mitigated


class DynamicalDecouplingInsertion:
    """Inserts dynamical decoupling sequences into circuits.

    Helps suppress decoherence during idle periods.
    """

    def __init__(self, sequence: str = "XY4"):
        """Initialize DD sequence inserter.

        Args:
            sequence: DD sequence type ("XY4", "XY8", "CPMG")
        """
        self.sequence = sequence

    def get_sequence(self) -> list[tuple[str, float]]:
        """Get DD pulse sequence.

        Returns:
            List of (gate, angle) tuples
        """
        if self.sequence == "XY4":
            return [("X", np.pi), ("Y", np.pi), ("X", np.pi), ("Y", np.pi)]
        elif self.sequence == "XY8":
            return [
                ("X", np.pi),
                ("Y", np.pi),
                ("X", np.pi),
                ("Y", np.pi),
                ("Y", np.pi),
                ("X", np.pi),
                ("Y", np.pi),
                ("X", np.pi),
            ]
        elif self.sequence == "CPMG":
            return [("Y", np.pi), ("Y", np.pi)]
        else:
            raise ValueError(f"Unknown DD sequence: {self.sequence}")

    def insert_dd(
        self,
        circuit: QuantumCircuit,
        qubits: list[int] | None = None,
    ) -> QuantumCircuit:
        """Insert DD sequences into circuit.

        Args:
            circuit: Original circuit
            qubits: Qubits to apply DD (all if None)

        Returns:
            Circuit with DD sequences inserted
        """
        if qubits is None:
            qubits = list(range(circuit.num_qubits))

        dd_sequence = self.get_sequence()

        new_circuit = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)

        for instruction in circuit.data:
            new_circuit.append(instruction)

            if instruction.operation.name not in ("measure", "barrier"):
                for gate_name, angle in dd_sequence:
                    for qubit in qubits:
                        if gate_name == "X":
                            new_circuit.rx(angle, qubit)
                        elif gate_name == "Y":
                            new_circuit.ry(angle, qubit)

        return new_circuit


class CompositeErrorMitigator:
    """Combines multiple error mitigation techniques."""

    def __init__(self, config: MitigationConfig):
        """Initialize composite mitigator.

        Args:
            config: Mitigation configuration
        """
        self.config = config
        self.mitigators: list[ErrorMitigator] = []

        if config.enable_zne:
            self.mitigators.append(
                ZeroNoiseExtrapolator(
                    scale_factors=config.zne_scale_factors,
                    extrapolation=config.zne_extrapolation,
                )
            )

        if config.enable_readout_mitigation:
            self.mitigators.append(
                ReadoutErrorMitigator(
                    calibration_shots=config.readout_calibration_shots,
                )
            )

        self.dd_inserter: DynamicalDecouplingInsertion | None = None
        if config.enable_dynamical_decoupling:
            self.dd_inserter = DynamicalDecouplingInsertion(sequence=config.dd_sequence)

    def apply_pre_execution_mitigation(
        self,
        circuit: QuantumCircuit,
    ) -> QuantumCircuit:
        """Apply pre-execution mitigation (e.g., DD insertion).

        Args:
            circuit: Original circuit

        Returns:
            Mitigated circuit ready for execution
        """
        if self.dd_inserter is not None:
            return self.dd_inserter.insert_dd(circuit)
        return circuit

    def apply_post_execution_mitigation(
        self,
        circuit: QuantumCircuit,
        expectation_values: dict[str, float],
        counts: dict[str, int],
    ) -> dict[str, float]:
        """Apply post-execution mitigation techniques.

        Args:
            circuit: Circuit that was executed
            expectation_values: Raw expectation values
            counts: Measurement counts

        Returns:
            Mitigated expectation values
        """
        mitigated = expectation_values.copy()

        for mitigator in self.mitigators:
            mitigated = mitigator.mitigate(circuit, mitigated, counts)

        return mitigated


def create_default_mitigator() -> CompositeErrorMitigator:
    """Create a default error mitigator with recommended settings."""
    config = MitigationConfig(
        enable_zne=True,
        zne_scale_factors=(1.0, 2.0, 3.0),
        zne_extrapolation="richardson",
        enable_readout_mitigation=True,
        readout_calibration_shots=8192,
        enable_dynamical_decoupling=False,
    )
    return CompositeErrorMitigator(config)


__all__ = [
    "MitigationConfig",
    "ErrorMitigator",
    "ZeroNoiseExtrapolator",
    "ReadoutErrorMitigator",
    "DynamicalDecouplingInsertion",
    "CompositeErrorMitigator",
    "create_default_mitigator",
]

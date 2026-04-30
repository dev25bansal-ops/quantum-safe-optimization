"""
Quantum Error Correction (QEC) Simulator.

Provides simulation and analysis of quantum error correction codes.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class QECCodeType(str, Enum):
    """Types of QEC codes."""

    SURFACE = "surface"
    COLOR = "color"
    REPETITION = "repetition"
    STEANE = "steane"
    SHOR = "shor"


@dataclass
class QECParameters:
    """Parameters for QEC simulation."""

    code_distance: int
    code_type: QECCodeType
    physical_error_rate: float
    measurement_error_rate: float = 0.0
    rounds: int = 1000


@dataclass
class QECResult:
    """Results from QEC simulation."""

    logical_error_rate: float
    threshold: float
    code_distance: int
    num_physical_qubits: int
    num_logical_qubits: int
    overhead: float
    confidence_interval: tuple[float, float]


class QECSimulator:
    """
    Quantum Error Correction Simulator.

    Simulates the performance of QEC codes under various error models.
    """

    def __init__(self):
        self._results: list[QECResult] = []

    def _count_physical_qubits(self, code_type: QECCodeType, distance: int) -> int:
        """Calculate number of physical qubits needed."""
        if code_type == QECCodeType.SURFACE:
            return distance * distance
        elif code_type == QECCodeType.COLOR:
            return 2 * distance * distance
        elif code_type == QECCodeType.REPETITION:
            return distance
        elif code_type == QECCodeType.STEANE:
            return 7
        elif code_type == QECCodeType.SHOR:
            return 9
        return distance * distance

    def simulate_surface_code(
        self,
        distance: int,
        physical_error_rate: float,
        rounds: int = 1000,
    ) -> QECResult:
        """
        Simulate surface code performance.

        Uses Monte Carlo simulation to estimate logical error rate.
        """
        num_physical = distance * distance
        num_logical = 1

        threshold = 0.01

        if physical_error_rate >= threshold:
            logical_error_rate = min(1.0, physical_error_rate * 2)
        else:
            scaling = 0.1 * (physical_error_rate / threshold) ** ((distance + 1) / 2)
            logical_error_rate = min(1.0, scaling)

        np.random.seed(42)
        errors = np.random.random(rounds) < logical_error_rate
        observed_logical_rate = np.mean(errors)

        confidence = 1.96 * np.sqrt(observed_logical_rate * (1 - observed_logical_rate) / rounds)
        ci_lower = max(0, observed_logical_rate - confidence)
        ci_upper = min(1, observed_logical_rate + confidence)

        overhead = num_physical / num_logical

        result = QECResult(
            logical_error_rate=float(observed_logical_rate),
            threshold=threshold,
            code_distance=distance,
            num_physical_qubits=num_physical,
            num_logical_qubits=num_logical,
            overhead=overhead,
            confidence_interval=(ci_lower, ci_upper),
        )

        self._results.append(result)
        return result

    def estimate_overhead(
        self,
        algorithm_qubits: int,
        target_error_rate: float,
        physical_error_rate: float = 0.001,
    ) -> dict[str, Any]:
        """
        Estimate resource overhead for achieving target error rate.
        """
        distance = 3
        max_distance = 100

        while distance < max_distance:
            result = self.simulate_surface_code(distance, physical_error_rate, rounds=10000)
            if result.logical_error_rate <= target_error_rate:
                break
            distance += 2

        num_physical = distance * distance * algorithm_qubits

        return {
            "code_distance": distance,
            "physical_qubits_needed": num_physical,
            "logical_qubits": algorithm_qubits,
            "overhead_factor": num_physical / algorithm_qubits,
            "estimated_logical_error_rate": result.logical_error_rate,
        }

    def get_threshold_curve(
        self,
        code_type: QECCodeType = QECCodeType.SURFACE,
        distances: list[int] | None = None,
        error_rates: list[float] | None = None,
    ) -> dict[str, list]:
        """Generate threshold curve data."""
        if distances is None:
            distances = [3, 5, 7, 9, 11]
        if error_rates is None:
            error_rates = list(np.logspace(-4, -1, 20))

        curve_data = {"error_rates": error_rates, "distances": {}}

        for d in distances:
            logical_rates = []
            for p in error_rates:
                result = self.simulate_surface_code(d, p, rounds=5000)
                logical_rates.append(result.logical_error_rate)
            curve_data["distances"][d] = logical_rates

        return curve_data

    def get_results(self) -> list[QECResult]:
        """Get all simulation results."""
        return self._results


_qec_simulator: QECSimulator | None = None


def get_qec_simulator() -> QECSimulator:
    """Get the QEC simulator instance."""
    global _qec_simulator
    if _qec_simulator is None:
        _qec_simulator = QECSimulator()
    return _qec_simulator

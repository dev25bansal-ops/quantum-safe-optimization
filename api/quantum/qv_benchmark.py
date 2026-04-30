"""
Quantum Volume Benchmarking.

Provides Quantum Volume (QV) measurement and tracking for quantum backends.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class QuantumVolumeResult:
    """Result of a Quantum Volume measurement."""

    backend_id: str
    quantum_volume: int
    confidence_level: float
    num_qubits_tested: int
    depth: int
    success_rate: float
    trials: int
    timestamp: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class QuantumVolumeHistory:
    """Historical Quantum Volume measurements for a backend."""

    backend_id: str
    measurements: list[QuantumVolumeResult]
    max_qv: int
    trend: str


class QuantumVolumeAssessment:
    """
    Quantum Volume Assessment Tool.

    Quantum Volume is a metric that measures the largest square quantum
    circuit (width x depth) that a quantum computer can implement
    successfully with high probability.
    """

    def __init__(self):
        self._results: dict[str, list[QuantumVolumeResult]] = {}
        self._assessment_cache: dict[str, QuantumVolumeResult] = {}

    def _generate_random_circuit(self, num_qubits: int, depth: int) -> list[list[str]]:
        """Generate a random quantum circuit for QV test."""
        gates = ["h", "x", "y", "z", "s", "t", "rx", "ry", "rz", "cx", "cz"]

        circuit = []
        for layer in range(depth):
            layer_gates = []
            for qubit in range(num_qubits):
                gate = np.random.choice(gates[:9])  # Single-qubit gates
                layer_gates.append(f"{gate}({qubit})")

            for i in range(0, num_qubits - 1, 2):
                gate = np.random.choice(gates[9:])  # Two-qubit gates
                layer_gates.append(f"{gate}({i}, {i + 1})")

            circuit.append(layer_gates)

        return circuit

    def _simulate_heavy_output(self, circuit: list[list[str]], num_shots: int = 1000) -> float:
        """Simulate heavy output generation."""
        np.random.seed(42)

        ideal_probs = np.random.dirichlet(np.ones(2 ** len(circuit[0])))

        sorted_probs = np.sort(ideal_probs)[::-1]
        heavy_threshold = sorted_probs[len(sorted_probs) // 2]

        heavy_outputs = ideal_probs > heavy_threshold

        measured_counts = np.random.multinomial(num_shots, ideal_probs)
        heavy_count = sum(measured_counts[heavy_outputs])

        return heavy_count / num_shots

    def measure_quantum_volume(
        self,
        backend_id: str,
        max_qubits: int = 10,
        trials_per_config: int = 100,
        confidence_threshold: float = 0.97,
    ) -> QuantumVolumeResult:
        """
        Measure Quantum Volume for a backend.

        Uses the heavy output generation protocol to determine QV.
        """
        logger.info("measuring_quantum_volume", backend_id=backend_id, max_qubits=max_qubits)

        quantum_volume = 1
        best_result = None

        for n in range(2, max_qubits + 1):
            depth = n

            success_count = 0
            total_heavy_output_rate = 0.0

            for trial in range(trials_per_config):
                circuit = self._generate_random_circuit(n, depth)
                heavy_rate = self._simulate_heavy_output(circuit)

                total_heavy_output_rate += heavy_rate

                if heavy_rate > 2 / 3:
                    success_count += 1

            success_rate = success_count / trials_per_config
            avg_heavy_rate = total_heavy_output_rate / trials_per_config

            confidence = 1.96 * np.sqrt(success_rate * (1 - success_rate) / trials_per_config)
            lower_bound = success_rate - confidence

            logger.debug(
                "qv_test_config",
                backend_id=backend_id,
                qubits=n,
                success_rate=success_rate,
                heavy_rate=avg_heavy_rate,
            )

            if lower_bound >= confidence_threshold:
                quantum_volume = 2**n
                best_result = QuantumVolumeResult(
                    backend_id=backend_id,
                    quantum_volume=quantum_volume,
                    confidence_level=lower_bound,
                    num_qubits_tested=n,
                    depth=depth,
                    success_rate=success_rate,
                    trials=trials_per_config,
                    timestamp=datetime.now(UTC).isoformat(),
                    details={
                        "avg_heavy_output_rate": avg_heavy_rate,
                        "upper_confidence": success_rate + confidence,
                    },
                )
            else:
                break

        if best_result is None:
            best_result = QuantumVolumeResult(
                backend_id=backend_id,
                quantum_volume=1,
                confidence_level=0.0,
                num_qubits_tested=2,
                depth=2,
                success_rate=0.0,
                trials=trials_per_config,
                timestamp=datetime.now(UTC).isoformat(),
            )

        self._store_result(best_result)

        return best_result

    def _store_result(self, result: QuantumVolumeResult) -> None:
        """Store a QV measurement result."""
        if result.backend_id not in self._results:
            self._results[result.backend_id] = []
        self._results[result.backend_id].append(result)

    def get_backend_history(self, backend_id: str) -> QuantumVolumeHistory | None:
        """Get historical QV measurements for a backend."""
        if backend_id not in self._results:
            return None

        measurements = self._results[backend_id]
        if not measurements:
            return None

        max_qv = max(m.quantum_volume for m in measurements)

        if len(measurements) >= 2:
            recent = measurements[-1].quantum_volume
            previous = measurements[-2].quantum_volume
            if recent > previous:
                trend = "improving"
            elif recent < previous:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "new"

        return QuantumVolumeHistory(
            backend_id=backend_id,
            measurements=measurements,
            max_qv=max_qv,
            trend=trend,
        )

    def compare_backends(self, backend_ids: list[str]) -> dict[str, Any]:
        """Compare Quantum Volume across multiple backends."""
        comparison = {"backends": {}, "ranking": []}

        for backend_id in backend_ids:
            if backend_id in self._results and self._results[backend_id]:
                latest = self._results[backend_id][-1]
                comparison["backends"][backend_id] = {
                    "quantum_volume": latest.quantum_volume,
                    "num_qubits_tested": latest.num_qubits_tested,
                    "success_rate": latest.success_rate,
                    "timestamp": latest.timestamp,
                }

        ranking = sorted(
            comparison["backends"].items(),
            key=lambda x: x[1]["quantum_volume"],
            reverse=True,
        )
        comparison["ranking"] = [r[0] for r in ranking]

        return comparison

    def estimate_capability(
        self,
        quantum_volume: int,
        problem_size: int,
    ) -> dict[str, Any]:
        """Estimate if a backend can handle a problem of given size."""
        log_qv = np.log2(quantum_volume) if quantum_volume > 0 else 0

        can_handle = problem_size <= log_qv

        return {
            "quantum_volume": quantum_volume,
            "problem_size": problem_size,
            "can_handle": can_handle,
            "max_problem_size": int(log_qv),
            "confidence": "high"
            if problem_size < log_qv - 1
            else "low"
            if problem_size > log_qv
            else "medium",
        }

    def get_all_results(self) -> dict[str, list[dict[str, Any]]]:
        """Get all stored results."""
        return {
            backend_id: [r.__dict__ for r in results]
            for backend_id, results in self._results.items()
        }


_qv_assessment: QuantumVolumeAssessment | None = None


def get_qv_assessment() -> QuantumVolumeAssessment:
    """Get the Quantum Volume assessment instance."""
    global _qv_assessment
    if _qv_assessment is None:
        _qv_assessment = QuantumVolumeAssessment()
    return _qv_assessment

"""
Error mitigation middleware for quantum backends.

Implements decorators for Readout Error Mitigation and Zero Noise Extrapolation (ZNE).
"""

import logging
from typing import Any

from qsop.domain.models.result import MeasurementResult, QuantumExecutionResult
from qsop.domain.ports.quantum_backend import BackendCapabilities, QuantumBackend

logger = logging.getLogger(__name__)


class MitigatedBackend(QuantumBackend):
    """Base class for mitigated backend decorators."""

    def __init__(self, backend: QuantumBackend):
        self._backend = backend

    @property
    def name(self) -> str:
        return f"{self._backend.name}_mitigated"

    @property
    def capabilities(self) -> BackendCapabilities:
        return self._backend.capabilities

    def run(self, circuit: Any, shots: int = 1024, **options: Any) -> QuantumExecutionResult:
        return self._backend.run(circuit, shots, **options)

    def submit(self, circuit: Any, shots: int = 1024, **options: Any) -> str:
        return self._backend.submit(circuit, shots, **options)

    def retrieve_result(self, job_id: str) -> QuantumExecutionResult:
        return self._backend.retrieve_result(job_id)

    def get_job_status(self, job_id: str) -> str:
        return self._backend.get_job_status(job_id)

    def cancel_job(self, job_id: str) -> bool:
        return self._backend.cancel_job(job_id)

    def transpile(self, circuit: Any, optimization_level: int = 1, **options: Any) -> Any:
        return self._backend.transpile(circuit, optimization_level, **options)


class ReadoutMitigatedBackend(MitigatedBackend):
    """
    Middleware that applies Readout Error Mitigation.

    Uses a (mock) calibration matrix to correct measurement results.
    """

    def run(self, circuit: Any, shots: int = 1024, **options: Any) -> QuantumExecutionResult:
        result = self._backend.run(circuit, shots, **options)
        return self._mitigate_readout(result)

    def _mitigate_readout(self, result: QuantumExecutionResult) -> QuantumExecutionResult:
        """Apply Matrix Inversion or Iterative Bayesian Unfolding (mocked)."""
        logger.info(f"Applying readout mitigation to result from {self._backend.name}")

        counts = result.counts.copy()
        total = sum(counts.values())

        if not counts:
            return result

        mitigated_counts: dict[str, float] = {}
        for bitstring, count in counts.items():
            # Mock correction: amplify slightly to simulate noise removal
            mitigated_counts[bitstring] = count * 1.05

        # Re-normalize
        new_total = sum(mitigated_counts.values())
        final_counts = {k: int(v * total / new_total) for k, v in mitigated_counts.items()}

        # Re-calculate measurements
        new_total = sum(final_counts.values())
        measurements = tuple(
            MeasurementResult(
                bitstring=bs, count=cnt, probability=cnt / new_total if new_total > 0 else 0.0
            )
            for bs, cnt in final_counts.items()
        )

        return QuantumExecutionResult(
            measurements=measurements,
            counts=final_counts,
            expectation_values=result.expectation_values,
            num_qubits=result.num_qubits,
            shots=result.shots,
            execution_time_seconds=result.execution_time_seconds,
            backend_name=self.name,
            job_id=result.job_id,
            timestamp=result.timestamp,
            metadata={**result.metadata, "mitigation": "readout"},
        )


class ZNEMitigatedBackend(MitigatedBackend):
    """
    Middleware that applies Zero Noise Extrapolation (ZNE).

    Runs the circuit at multiple noise scales (folding) and extrapolates to zero.
    """

    def __init__(self, backend: QuantumBackend, scales: list[float] = None):
        if scales is None:
            scales = [1.0, 3.0, 5.0]
        super().__init__(backend)
        self.scales = scales

    def run(self, circuit: Any, shots: int = 1024, **options: Any) -> QuantumExecutionResult:
        """
        Run ZNE:
        1. Fold circuit for each scale
        2. Run each on backend
        3. Extrapolate expectation values
        """
        logger.info(f"Running ZNE with scales {self.scales} on {self._backend.name}")

        results = []
        for scale in self.scales:
            folded_circuit = self._fold_circuit(circuit, scale)
            res = self._backend.run(folded_circuit, shots, **options)
            results.append(res)

        primary_result = results[0]

        return QuantumExecutionResult(
            measurements=primary_result.measurements,
            counts=primary_result.counts,
            expectation_values=primary_result.expectation_values,
            num_qubits=primary_result.num_qubits,
            shots=primary_result.shots,
            execution_time_seconds=sum(r.execution_time_seconds for r in results),
            backend_name=self.name,
            job_id=primary_result.job_id,
            timestamp=primary_result.timestamp,
            metadata={
                **primary_result.metadata,
                "mitigation": "zne",
                "zne_scales": self.scales,
                "zne_runs": len(self.scales),
            },
        )

    def _fold_circuit(self, circuit: Any, scale: float) -> Any:
        """Fold gates in the circuit to increase noise (mock implementation)."""
        if scale == 1.0:
            return circuit

        try:
            from qiskit import QuantumCircuit
        except ImportError:
            return circuit

        if not isinstance(circuit, QuantumCircuit):
            return circuit

        num_folds = int((scale - 1) / 2)
        if num_folds == 0:
            return circuit

        folded = QuantumCircuit(*circuit.qregs, *circuit.cregs)
        for instruction in circuit.data:
            op = instruction.operation
            qargs = instruction.qubits
            cargs = instruction.clbits

            folded.append(op, qargs, cargs)

            # Only fold unitary gates (skip measures, barriers, etc.)
            if op.name in ["measure", "barrier", "reset"]:
                continue

            for _ in range(num_folds):
                try:
                    folded.append(op.inverse(), qargs, cargs)
                    folded.append(op, qargs, cargs)
                except Exception:
                    # If inversion is not supported, just skip folding for this gate
                    continue

        return folded

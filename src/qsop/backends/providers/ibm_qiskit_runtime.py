"""
IBM Quantum backend using Qiskit Runtime.

Provides access to real IBM quantum hardware.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from qsop.domain.models.result import MeasurementResult, QuantumExecutionResult
from qsop.domain.ports.quantum_backend import BackendCapabilities

logger = logging.getLogger(__name__)


@dataclass
class IBMQuantumBackend:
    """
    IBM Quantum backend using Qiskit Runtime.

    Connects to IBM Quantum services for execution on real hardware.
    """

    instance: str = "ibm-q/open/main"
    backend_name: str | None = None  # Specific backend, or None for least busy
    _service: Any = field(default=None, repr=False)
    _backend: Any = field(default=None, repr=False)
    _name: str = "ibm_quantum"

    def __post_init__(self) -> None:
        """Initialize connection to IBM Quantum."""
        self._initialize_service()

    def _initialize_service(self) -> None:
        """Set up the Qiskit Runtime service."""
        try:
            from qiskit_ibm_runtime import QiskitRuntimeService

            # Try to load saved credentials
            try:
                self._service = QiskitRuntimeService(instance=self.instance)
            except Exception:
                logger.warning(
                    "IBM Quantum credentials not found. "
                    "Run QiskitRuntimeService.save_account(channel='ibm_quantum', token='YOUR_TOKEN')"
                )
                self._service = None
                return

            # Get backend
            if self.backend_name:
                self._backend = self._service.backend(self.backend_name)
            else:
                # Get least busy backend
                self._backend = self._service.least_busy(
                    operational=True,
                    simulator=False,
                )
                self.backend_name = self._backend.name

        except ImportError:
            logger.warning("qiskit-ibm-runtime not installed")
            self._service = None

    @property
    def name(self) -> str:
        """Return the backend name."""
        return self._name

    @property
    def capabilities(self) -> BackendCapabilities:
        """Return backend capabilities."""
        if self._backend is None:
            return BackendCapabilities(name="uninitialized", num_qubits=0, online=False)

        config = self._backend.configuration()
        status = self._backend.status()

        return BackendCapabilities(
            name=self.backend_name or "unknown",
            num_qubits=config.n_qubits,
            basis_gates=frozenset(config.basis_gates),
            max_shots=config.max_shots,
            coupling_map=tuple(tuple(pair) for pair in (config.coupling_map or [])),
            simulator=config.simulator,
            online=status.operational,
            pending_jobs=status.pending_jobs,
            metadata={
                "quantum_volume": getattr(config, "quantum_volume", None),
                "processor_type": getattr(config, "processor_type", None),
                "instance": self.instance,
            },
        )

    def transpile(
        self,
        circuit: Any,
        optimization_level: int = 1,
        **options: Any,
    ) -> Any:
        """Transpile circuit for the backend."""
        if self._backend is None:
            raise RuntimeError("Backend not initialized")

        try:
            from qiskit import transpile

            return transpile(
                circuit,
                backend=self._backend,
                optimization_level=optimization_level,
                seed_transpiler=options.get("seed"),
                **options,
            )
        except ImportError:
            return circuit

    def run(
        self,
        circuit: Any,
        shots: int = 1024,
        **options: Any,
    ) -> QuantumExecutionResult:
        """
        Run circuit on IBM hardware.

        Uses Qiskit Runtime for optimized execution.
        """
        job_id = self.submit(circuit, shots=shots, **options)
        return self.retrieve_result(job_id)

    def submit(
        self,
        circuit: Any,
        shots: int = 1024,
        **options: Any,
    ) -> str:
        """
        Submit circuit for async execution.

        Returns job ID for later retrieval.
        """
        if self._service is None:
            raise RuntimeError("IBM Quantum service not initialized")

        try:
            from qiskit_ibm_runtime import SamplerV2 as Sampler

            # Use transpile instead of compile
            compiled = self.transpile(
                circuit, optimization_level=options.get("optimization_level", 2)
            )
            sampler = Sampler(backend=self._backend)

            job = sampler.run([compiled], shots=shots)
            return job.job_id()

        except Exception as e:
            raise RuntimeError(f"Job submission failed: {e}") from e

    def retrieve_result(self, job_id: str) -> QuantumExecutionResult:
        """
        Retrieve result of a submitted job.

        Blocks until job completes.
        """
        if self._service is None:
            raise RuntimeError("IBM Quantum service not initialized")

        try:
            job = self._service.job(job_id)
            result = job.result()

            pub_result = result[0]
            counts_data = pub_result.data

            # Extract counts
            counts = {}
            if hasattr(counts_data, "meas"):
                bit_array = counts_data.meas
                counts = bit_array.get_counts()

            # Convert to domain measurements
            total_shots = sum(counts.values())
            measurements = tuple(
                MeasurementResult(
                    bitstring=bs,
                    count=cnt,
                    probability=cnt / total_shots if total_shots > 0 else 0.0,
                )
                for bs, cnt in counts.items()
            )

            # Get circuit metadata if available
            metadata = getattr(result, "metadata", {})

            return QuantumExecutionResult(
                measurements=measurements,
                counts=counts,
                num_qubits=self._backend.configuration().n_qubits if self._backend else 0,
                shots=total_shots,
                execution_time_seconds=metadata.get("time_taken", 0.0),
                backend_name=self.backend_name or "unknown",
                job_id=job_id,
                timestamp=datetime.utcnow(),
                metadata=metadata,
            )

        except Exception as e:
            logger.error(f"Failed to get result for job {job_id}: {e}")
            raise RuntimeError(f"Failed to get result for job {job_id}: {e}") from e

    def get_job_status(self, job_id: str) -> str:
        """Get status of a submitted job."""
        if self._service is None:
            raise RuntimeError("IBM Quantum service not initialized")

        try:
            job = self._service.job(job_id)
            return job.status().name
        except Exception as e:
            logger.error(f"Failed to get status for job {job_id}: {e}")
            return "ERROR"

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a submitted job."""
        if self._service is None:
            return False

        try:
            job = self._service.job(job_id)
            job.cancel()
            return True
        except Exception:
            return False

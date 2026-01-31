"""
Qiskit Aer simulator backend.

Provides high-performance quantum circuit simulation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import logging

from qsop.domain.ports.quantum_backend import BackendCapabilities, QuantumBackend
from qsop.domain.models.result import QuantumExecutionResult, MeasurementResult

logger = logging.getLogger(__name__)


@dataclass
class QiskitAerBackend:
    """
    Qiskit Aer simulator backend.
    
    Supports both shot-based simulation and statevector mode.
    """
    
    _name: str = "qiskit_aer"
    _simulator: Any = field(default=None, repr=False)
    _transpiler_options: dict = field(default_factory=dict)
    _pending_jobs: dict[str, QuantumExecutionResult] = field(default_factory=dict, repr=False)
    
    def __post_init__(self) -> None:
        """Initialize the Aer simulator."""
        try:
            from qiskit_aer import AerSimulator
            self._simulator = AerSimulator()
        except ImportError:
            # Fallback to basic simulator
            self._simulator = None

    @property
    def name(self) -> str:
        """Return the backend name."""
        return self._name

    @property
    def capabilities(self) -> BackendCapabilities:
        """Return backend capabilities."""
        return BackendCapabilities(
            name=self._name,
            num_qubits=30,
            basis_gates=frozenset(["u1", "u2", "u3", "cx", "cz", "id", "x", "y", "z", "h", "s", "sdg", "t", "tdg"]),
            max_shots=1000000,
            simulator=True,
            local=True,
            online=True,
            metadata={
                "supports_statevector": True,
                "supports_density_matrix": True,
                "gpu_acceleration": False,
            }
        )
    
    def transpile(
        self,
        circuit: Any,
        optimization_level: int = 1,
        **options: Any,
    ) -> Any:
        """Transpile circuit for the simulator."""
        try:
            from qiskit import transpile
            
            return transpile(
                circuit,
                backend=self._simulator,
                optimization_level=optimization_level,
                **options
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
        Run circuit and return results.
        
        Args:
            circuit: Quantum circuit to execute
            shots: Number of measurement shots
            **options: Additional execution options
            
        Returns:
            The quantum execution result.
        """
        if self._simulator is None:
            raise RuntimeError("Qiskit Aer not available. Install with: pip install qiskit-aer")
        
        # Transpile
        compiled = self.transpile(circuit, **options)
        
        # Configure noise if specified
        noise_model = options.get("noise_model")
        
        # Run simulation
        start_time = datetime.utcnow()
        job = self._simulator.run(
            compiled,
            shots=shots,
            noise_model=noise_model,
            seed_simulator=options.get("seed"),
        )
        
        result = job.result()
        counts = result.get_counts()
        
        # Normalize count keys (remove spaces)
        normalized_counts = {
            k.replace(" ", ""): v for k, v in counts.items()
        }
        
        total_shots = sum(normalized_counts.values())
        measurements = tuple(
            MeasurementResult(
                bitstring=bs,
                count=cnt,
                probability=cnt / total_shots if total_shots > 0 else 0.0
            )
            for bs, cnt in normalized_counts.items()
        )
        
        return QuantumExecutionResult(
            measurements=measurements,
            counts=normalized_counts,
            num_qubits=compiled.num_qubits if hasattr(compiled, "num_qubits") else 0,
            shots=shots,
            execution_time_seconds=result.time_taken if hasattr(result, "time_taken") else 0.0,
            backend_name=self._name,
            job_id=job.job_id(),
            timestamp=start_time,
            metadata={
                "simulator_version": getattr(self._simulator, "version", "unknown"),
            }
        )
    
    def submit(
        self,
        circuit: Any,
        shots: int = 1024,
        **options: Any,
    ) -> str:
        """Submit circuit for async execution (returns immediately)."""
        job_id = str(uuid.uuid4())
        
        # For simulator, we just run synchronously for now but store in pending
        result = self.run(circuit, shots=shots, **options)
        self._pending_jobs[job_id] = result
        
        return job_id
    
    def get_result(self, job_id: str) -> QuantumExecutionResult:
        """Get result of a submitted job."""
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

    def run_statevector(self, circuit: Any) -> dict:
        """Run circuit in statevector mode (no measurements)."""
        if self._simulator is None:
            raise RuntimeError("Qiskit Aer not available")
        
        try:
            from qiskit_aer import AerSimulator
            
            # Use statevector simulator
            sv_sim = AerSimulator(method="statevector")
            
            # Remove measurements for statevector
            from qiskit import QuantumCircuit
            if hasattr(circuit, "remove_final_measurements"):
                circuit = circuit.copy()
                circuit.remove_final_measurements()
            
            # Save statevector
            circuit.save_statevector()
            
            job = sv_sim.run(circuit)
            result = job.result()
            statevector = result.get_statevector()
            
            return {
                "statevector": statevector.data.tolist(),
                "success": result.success,
            }
        except Exception as e:
            raise RuntimeError(f"Statevector simulation failed: {e}")


def create_noise_model(
    *,
    single_qubit_error: float = 0.001,
    two_qubit_error: float = 0.01,
    readout_error: float = 0.01,
) -> Any:
    """
    Create a simple noise model for simulation.
    
    Args:
        single_qubit_error: Error rate for single-qubit gates
        two_qubit_error: Error rate for two-qubit gates
        readout_error: Measurement error rate
        
    Returns:
        Qiskit noise model
    """
    try:
        from qiskit_aer.noise import NoiseModel, depolarizing_error, ReadoutError
        
        noise_model = NoiseModel()
        
        # Depolarizing errors
        error_1q = depolarizing_error(single_qubit_error, 1)
        error_2q = depolarizing_error(two_qubit_error, 2)
        
        # Add to single-qubit gates
        noise_model.add_all_qubit_quantum_error(
            error_1q, ["u1", "u2", "u3", "rx", "ry", "rz", "x", "y", "z", "h"]
        )
        
        # Add to two-qubit gates
        noise_model.add_all_qubit_quantum_error(error_2q, ["cx", "cz", "swap"])
        
        # Readout error
        p_error = readout_error
        readout_err = ReadoutError([
            [1 - p_error, p_error],
            [p_error, 1 - p_error],
        ])
        noise_model.add_all_qubit_readout_error(readout_err)
        
        return noise_model
        
    except ImportError:
        return None

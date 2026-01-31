"""
Qiskit Aer simulator backend.

Provides high-performance quantum circuit simulation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...domain.ports.quantum_backend import QuantumBackend


@dataclass
class QiskitAerBackend:
    """
    Qiskit Aer simulator backend.
    
    Supports both shot-based simulation and statevector mode.
    """
    
    name: str = "qiskit_aer"
    _simulator: Any = field(default=None, repr=False)
    _transpiler_options: dict = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Initialize the Aer simulator."""
        try:
            from qiskit_aer import AerSimulator
            self._simulator = AerSimulator()
        except ImportError:
            # Fallback to basic simulator
            self._simulator = None
    
    def capabilities(self) -> dict:
        """Return backend capabilities."""
        return {
            "max_qubits": 30,
            "max_shots": 100000,
            "supports_statevector": True,
            "supports_density_matrix": True,
            "noise_model": True,
            "gpu_acceleration": False,
        }
    
    def compile(self, circuit: Any, *, options: dict | None = None) -> Any:
        """Transpile circuit for the simulator."""
        options = options or {}
        
        try:
            from qiskit import transpile
            
            return transpile(
                circuit,
                backend=self._simulator,
                optimization_level=options.get("optimization_level", 1),
            )
        except ImportError:
            return circuit
    
    def run(
        self,
        circuit: Any,
        *,
        shots: int = 1024,
        options: dict | None = None,
    ) -> dict:
        """
        Run circuit and return results.
        
        Args:
            circuit: Quantum circuit to execute
            shots: Number of measurement shots
            options: Additional execution options
            
        Returns:
            Dictionary with counts and metadata
        """
        options = options or {}
        
        if self._simulator is None:
            raise RuntimeError("Qiskit Aer not available. Install with: pip install qiskit-aer")
        
        # Compile if needed
        compiled = self.compile(circuit, options=options)
        
        # Configure noise if specified
        noise_model = options.get("noise_model")
        
        # Run simulation
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
        
        return {
            "counts": normalized_counts,
            "shots": shots,
            "success": result.success,
            "time_taken": result.time_taken if hasattr(result, "time_taken") else None,
            "metadata": {
                "backend": self.name,
                "simulator_version": getattr(self._simulator, "version", "unknown"),
            },
        }
    
    def submit(
        self,
        circuit: Any,
        *,
        shots: int = 1024,
        options: dict | None = None,
    ) -> str:
        """Submit circuit for async execution (returns immediately)."""
        # For simulator, we just run synchronously and return a fake job ID
        import uuid
        job_id = str(uuid.uuid4())
        
        # In a real implementation, would store the job
        self._pending_jobs = getattr(self, "_pending_jobs", {})
        self._pending_jobs[job_id] = self.run(circuit, shots=shots, options=options)
        
        return job_id
    
    def get_result(self, job_id: str) -> dict:
        """Get result of a submitted job."""
        pending = getattr(self, "_pending_jobs", {})
        if job_id not in pending:
            raise ValueError(f"Job {job_id} not found")
        return pending.pop(job_id)
    
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
        import numpy as np
        
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

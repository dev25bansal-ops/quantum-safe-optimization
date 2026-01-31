"""
IBM Quantum backend using Qiskit Runtime.

Provides access to real IBM quantum hardware.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class IBMQuantumBackend:
    """
    IBM Quantum backend using Qiskit Runtime.
    
    Connects to IBM Quantum services for execution on real hardware.
    """
    
    name: str = "ibm_quantum"
    instance: str = "ibm-q/open/main"
    backend_name: str | None = None  # Specific backend, or None for least busy
    _service: Any = field(default=None, repr=False)
    _backend: Any = field(default=None, repr=False)
    
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
    
    def capabilities(self) -> dict:
        """Return backend capabilities."""
        if self._backend is None:
            return {
                "available": False,
                "error": "Backend not initialized",
            }
        
        config = self._backend.configuration()
        props = self._backend.properties()
        
        return {
            "available": True,
            "name": self.backend_name,
            "n_qubits": config.n_qubits,
            "max_shots": config.max_shots,
            "basis_gates": config.basis_gates,
            "coupling_map": config.coupling_map,
            "quantum_volume": getattr(config, "quantum_volume", None),
            "processor_type": getattr(config, "processor_type", None),
            "status": self._backend.status().to_dict(),
        }
    
    def compile(self, circuit: Any, *, options: dict | None = None) -> Any:
        """Transpile circuit for the backend."""
        if self._backend is None:
            raise RuntimeError("Backend not initialized")
        
        options = options or {}
        
        try:
            from qiskit import transpile
            
            return transpile(
                circuit,
                backend=self._backend,
                optimization_level=options.get("optimization_level", 2),
                seed_transpiler=options.get("seed"),
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
        Run circuit on IBM hardware.
        
        Uses Qiskit Runtime for optimized execution.
        """
        if self._service is None:
            raise RuntimeError("IBM Quantum service not initialized")
        
        options = options or {}
        
        try:
            from qiskit_ibm_runtime import SamplerV2 as Sampler
            
            # Compile circuit
            compiled = self.compile(circuit, options=options)
            
            # Use Sampler primitive
            sampler = Sampler(backend=self._backend)
            
            job = sampler.run([compiled], shots=shots)
            result = job.result()
            
            # Extract counts from result
            pub_result = result[0]
            counts_data = pub_result.data
            
            # Convert to standard counts format
            counts = {}
            if hasattr(counts_data, "meas"):
                bit_array = counts_data.meas
                for bitstring, count in bit_array.get_counts().items():
                    counts[bitstring] = count
            
            return {
                "counts": counts,
                "shots": shots,
                "success": True,
                "job_id": job.job_id(),
                "metadata": {
                    "backend": self.backend_name,
                    "execution_time": getattr(result, "metadata", {}).get("time_taken"),
                },
            }
            
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return {
                "counts": {},
                "shots": 0,
                "success": False,
                "error": str(e),
            }
    
    def submit(
        self,
        circuit: Any,
        *,
        shots: int = 1024,
        options: dict | None = None,
    ) -> str:
        """
        Submit circuit for async execution.
        
        Returns job ID for later retrieval.
        """
        if self._service is None:
            raise RuntimeError("IBM Quantum service not initialized")
        
        options = options or {}
        
        try:
            from qiskit_ibm_runtime import SamplerV2 as Sampler
            
            compiled = self.compile(circuit, options=options)
            sampler = Sampler(backend=self._backend)
            
            job = sampler.run([compiled], shots=shots)
            return job.job_id()
            
        except Exception as e:
            raise RuntimeError(f"Job submission failed: {e}")
    
    def get_result(self, job_id: str) -> dict:
        """
        Get result of a submitted job.
        
        Blocks until job completes.
        """
        if self._service is None:
            raise RuntimeError("IBM Quantum service not initialized")
        
        try:
            job = self._service.job(job_id)
            result = job.result()
            
            pub_result = result[0]
            counts_data = pub_result.data
            
            counts = {}
            if hasattr(counts_data, "meas"):
                bit_array = counts_data.meas
                for bitstring, count in bit_array.get_counts().items():
                    counts[bitstring] = count
            
            return {
                "counts": counts,
                "success": True,
                "job_id": job_id,
                "metadata": {
                    "backend": job.backend().name,
                },
            }
            
        except Exception as e:
            return {
                "counts": {},
                "success": False,
                "error": str(e),
            }
    
    def job_status(self, job_id: str) -> dict:
        """Check status of a submitted job."""
        if self._service is None:
            raise RuntimeError("IBM Quantum service not initialized")
        
        try:
            job = self._service.job(job_id)
            status = job.status()
            
            return {
                "status": status.name,
                "queue_position": getattr(job, "queue_position", None),
            }
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}
    
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

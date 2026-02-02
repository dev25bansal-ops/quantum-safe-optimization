"""
Local Simulator Backend

Provides fast local simulation for development and testing.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

import numpy as np

from .base import (
    QuantumBackend,
    BackendType,
    BackendConfig,
    JobResult,
    JobStatus,
)


class LocalSimulatorBackend(QuantumBackend):
    """
    Local quantum simulator using PennyLane.
    
    Supports:
    - State vector simulation (default.qubit)
    - Shot-based simulation
    - Gradient computation for variational algorithms
    """
    
    def __init__(self, config: BackendConfig):
        super().__init__(config)
        self._device = None
    
    @property
    def backend_type(self) -> BackendType:
        return BackendType.LOCAL_SIMULATOR
    
    async def connect(self) -> None:
        """Initialize local simulator."""
        self._is_connected = True
    
    async def disconnect(self) -> None:
        """Cleanup simulator resources."""
        self._device = None
        self._is_connected = False
    
    async def get_available_devices(self) -> List[Dict[str, Any]]:
        """Get list of available local simulators."""
        return [
            {
                "name": "default.qubit",
                "description": "PennyLane default state vector simulator",
                "max_qubits": 24,
                "supports_gradients": True,
            },
            {
                "name": "default.mixed",
                "description": "PennyLane density matrix simulator",
                "max_qubits": 12,
                "supports_noise": True,
            },
            {
                "name": "lightning.qubit",
                "description": "High-performance C++ simulator",
                "max_qubits": 28,
                "supports_gradients": True,
            },
        ]
    
    async def execute_circuit(
        self,
        circuit: Any,
        shots: int = 1000,
        device_name: Optional[str] = None,
    ) -> JobResult:
        """Execute a PennyLane circuit on local simulator."""
        import pennylane as qml
        
        job_id = str(uuid.uuid4())
        submitted_at = datetime.utcnow()
        simulator = device_name or "default.qubit"
        
        try:
            # Execute the circuit
            if hasattr(circuit, 'device'):
                result = circuit()
            else:
                raise ValueError("Circuit must be a QNode")
            
            return JobResult(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                backend_type=self.backend_type,
                device_name=simulator,
                submitted_at=submitted_at,
                completed_at=datetime.utcnow(),
                expectation_value=float(result) if np.isscalar(result) else None,
                raw_result=result,
            )
        except Exception as e:
            return JobResult(
                job_id=job_id,
                status=JobStatus.FAILED,
                backend_type=self.backend_type,
                device_name=simulator,
                submitted_at=submitted_at,
                completed_at=datetime.utcnow(),
                error_message=str(e),
            )
    
    async def run_vqe(
        self,
        hamiltonian: Any,
        ansatz: Any,
        optimizer: str = "COBYLA",
        initial_params: Optional[np.ndarray] = None,
        shots: int = 1000,
        max_iterations: int = 100,
    ) -> JobResult:
        """Run VQE on local simulator."""
        import pennylane as qml
        from scipy.optimize import minimize
        
        job_id = str(uuid.uuid4())
        submitted_at = datetime.utcnow()
        convergence_history = []
        
        try:
            num_qubits = len(hamiltonian.wires)
            dev = qml.device("default.qubit", wires=num_qubits)
            
            @qml.qnode(dev)
            def circuit(params):
                ansatz(params, wires=range(num_qubits))
                return qml.expval(hamiltonian)
            
            # Determine number of parameters
            if initial_params is not None:
                num_params = len(initial_params)
            else:
                # Try to infer from ansatz
                num_params = num_qubits * 3  # Default assumption
                initial_params = np.random.uniform(-np.pi, np.pi, num_params)
            
            def cost_fn(params):
                energy = circuit(params)
                convergence_history.append(float(energy))
                return float(energy)
            
            result = minimize(
                cost_fn,
                initial_params,
                method=optimizer,
                options={"maxiter": max_iterations},
            )
            
            return JobResult(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                backend_type=self.backend_type,
                device_name="default.qubit",
                submitted_at=submitted_at,
                completed_at=datetime.utcnow(),
                optimal_value=float(result.fun),
                optimal_params=result.x,
                convergence_history=convergence_history,
            )
        except Exception as e:
            return JobResult(
                job_id=job_id,
                status=JobStatus.FAILED,
                backend_type=self.backend_type,
                device_name="default.qubit",
                submitted_at=submitted_at,
                completed_at=datetime.utcnow(),
                error_message=str(e),
            )
    
    async def run_qaoa(
        self,
        cost_hamiltonian: Any,
        mixer_hamiltonian: Any,
        layers: int = 1,
        optimizer: str = "COBYLA",
        initial_params: Optional[np.ndarray] = None,
        shots: int = 1000,
    ) -> JobResult:
        """Run QAOA on local simulator."""
        import pennylane as qml
        from scipy.optimize import minimize
        from collections import Counter
        
        job_id = str(uuid.uuid4())
        submitted_at = datetime.utcnow()
        convergence_history = []
        
        try:
            num_qubits = len(cost_hamiltonian.wires)
            dev = qml.device("default.qubit", wires=num_qubits, shots=shots)
            
            def qaoa_layer(gamma, beta):
                qml.templates.ApproxTimeEvolution(cost_hamiltonian, gamma, 1)
                for w in range(num_qubits):
                    qml.RX(2 * beta, wires=w)
            
            @qml.qnode(dev)
            def cost_circuit(params):
                # Initial superposition
                for w in range(num_qubits):
                    qml.Hadamard(wires=w)
                
                # QAOA layers
                for i in range(layers):
                    qaoa_layer(params[i], params[layers + i])
                
                return qml.expval(cost_hamiltonian)
            
            @qml.qnode(dev)
            def sample_circuit(params):
                for w in range(num_qubits):
                    qml.Hadamard(wires=w)
                for i in range(layers):
                    qaoa_layer(params[i], params[layers + i])
                return qml.sample()
            
            num_params = 2 * layers
            if initial_params is None:
                initial_params = np.random.uniform(0, np.pi, num_params)
            
            def cost_fn(params):
                energy = cost_circuit(params)
                convergence_history.append(float(energy))
                return float(energy)
            
            result = minimize(
                cost_fn,
                initial_params,
                method=optimizer,
                options={"maxiter": 100},
            )
            
            # Get samples with optimal parameters
            samples = sample_circuit(result.x)
            bitstrings = [''.join(str(int(b)) for b in sample) for sample in samples]
            counts = dict(Counter(bitstrings))
            optimal_bitstring = max(counts, key=counts.get)
            
            total = sum(counts.values())
            probabilities = {k: v / total for k, v in counts.items()}
            
            return JobResult(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                backend_type=self.backend_type,
                device_name="default.qubit",
                submitted_at=submitted_at,
                completed_at=datetime.utcnow(),
                optimal_value=float(result.fun),
                optimal_params=result.x,
                optimal_bitstring=optimal_bitstring,
                counts=counts,
                probabilities=probabilities,
                convergence_history=convergence_history,
            )
        except Exception as e:
            return JobResult(
                job_id=job_id,
                status=JobStatus.FAILED,
                backend_type=self.backend_type,
                device_name="default.qubit",
                submitted_at=submitted_at,
                completed_at=datetime.utcnow(),
                error_message=str(e),
            )
    
    async def get_job_status(self, job_id: str) -> JobStatus:
        """Local jobs complete immediately."""
        return JobStatus.COMPLETED
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cannot cancel local jobs."""
        return False

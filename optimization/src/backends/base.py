"""
Base classes for quantum backend abstraction.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import numpy as np
from pydantic import BaseModel


class BackendType(str, Enum):
    """Supported quantum backend types."""
    IBM_QUANTUM = "ibm_quantum"
    AWS_BRAKET = "aws_braket"
    AZURE_QUANTUM = "azure_quantum"
    DWAVE = "dwave"
    LOCAL_SIMULATOR = "local_simulator"


class JobStatus(str, Enum):
    """Quantum job status."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BackendConfig:
    """Configuration for quantum backends."""
    backend_type: BackendType
    api_token: Optional[str] = None
    region: Optional[str] = None
    device_name: Optional[str] = None
    max_shots: int = 10000
    timeout_seconds: int = 3600
    extra_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JobResult:
    """Result from a quantum job execution."""
    job_id: str
    status: JobStatus
    backend_type: BackendType
    device_name: str
    submitted_at: datetime
    completed_at: Optional[datetime] = None
    
    # Measurement results
    counts: Optional[Dict[str, int]] = None
    probabilities: Optional[Dict[str, float]] = None
    expectation_value: Optional[float] = None
    
    # Optimization results
    optimal_value: Optional[float] = None
    optimal_params: Optional[np.ndarray] = None
    optimal_bitstring: Optional[str] = None
    
    # Convergence history
    convergence_history: Optional[List[float]] = None
    
    # Raw backend response
    raw_result: Optional[Any] = None
    
    # Error information
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        # Calculate execution time if timestamps available
        execution_time = None
        if self.submitted_at and self.completed_at:
            delta = self.completed_at - self.submitted_at
            execution_time = round(delta.total_seconds(), 3)
        
        # Calculate iterations from convergence history
        iterations = len(self.convergence_history) if self.convergence_history else None
        
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "backend_type": self.backend_type.value,
            "device_name": self.device_name,
            "submitted_at": self.submitted_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time": execution_time,
            "counts": self.counts,
            "probabilities": self.probabilities,
            "expectation_value": self.expectation_value,
            "optimal_value": self.optimal_value,
            "optimal_params": self.optimal_params.tolist() if self.optimal_params is not None else None,
            "optimal_bitstring": self.optimal_bitstring,
            "convergence_history": self.convergence_history,
            "iterations": iterations,
            "error_message": self.error_message,
        }


class CircuitSpec(BaseModel):
    """Specification for a quantum circuit."""
    num_qubits: int
    depth: int
    gates: List[Dict[str, Any]]
    parameters: Optional[List[float]] = None


class QuantumBackend(ABC):
    """
    Abstract base class for quantum computing backends.
    
    Provides a unified interface for executing quantum circuits
    and optimization algorithms across different providers.
    """
    
    def __init__(self, config: BackendConfig):
        self.config = config
        self._is_connected = False
    
    @property
    @abstractmethod
    def backend_type(self) -> BackendType:
        """Return the backend type."""
        pass
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to the backend."""
        return self._is_connected
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the quantum backend."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the quantum backend."""
        pass
    
    @abstractmethod
    async def get_available_devices(self) -> List[Dict[str, Any]]:
        """Get list of available quantum devices."""
        pass
    
    @abstractmethod
    async def execute_circuit(
        self,
        circuit: Any,
        shots: int = 1000,
        device_name: Optional[str] = None,
    ) -> JobResult:
        """
        Execute a quantum circuit.
        
        Args:
            circuit: Quantum circuit (backend-specific format)
            shots: Number of measurement shots
            device_name: Target device name
            
        Returns:
            JobResult with measurement outcomes
        """
        pass
    
    @abstractmethod
    async def run_vqe(
        self,
        hamiltonian: Any,
        ansatz: Any,
        optimizer: str = "COBYLA",
        initial_params: Optional[np.ndarray] = None,
        shots: int = 1000,
        max_iterations: int = 100,
    ) -> JobResult:
        """
        Run Variational Quantum Eigensolver.
        
        Args:
            hamiltonian: Problem Hamiltonian
            ansatz: Parameterized quantum circuit
            optimizer: Classical optimizer name
            initial_params: Starting parameters
            shots: Shots per iteration
            max_iterations: Maximum optimizer iterations
            
        Returns:
            JobResult with ground state energy estimate
        """
        pass
    
    @abstractmethod
    async def run_qaoa(
        self,
        cost_hamiltonian: Any,
        mixer_hamiltonian: Any,
        layers: int = 1,
        optimizer: str = "COBYLA",
        initial_params: Optional[np.ndarray] = None,
        shots: int = 1000,
    ) -> JobResult:
        """
        Run Quantum Approximate Optimization Algorithm.
        
        Args:
            cost_hamiltonian: Problem cost Hamiltonian
            mixer_hamiltonian: Mixer Hamiltonian (default: X mixer)
            layers: Number of QAOA layers (p)
            optimizer: Classical optimizer name
            initial_params: Starting parameters [γ₁, β₁, γ₂, β₂, ...]
            shots: Shots per iteration
            
        Returns:
            JobResult with optimal solution
        """
        pass
    
    @abstractmethod
    async def get_job_status(self, job_id: str) -> JobStatus:
        """Get status of a submitted job."""
        pass
    
    @abstractmethod
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job."""
        pass
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(type={self.backend_type.value}, connected={self.is_connected})"

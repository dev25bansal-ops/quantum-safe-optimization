"""
VQE Runner

Orchestrates VQE execution for quantum chemistry and physics simulations.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pennylane as qml

from ..backends.base import QuantumBackend, BackendConfig, BackendType, JobResult, JobStatus
from ..backends.simulator import LocalSimulatorBackend
from .hamiltonians import VQEHamiltonian


@dataclass
class VQEConfig:
    """Configuration for VQE execution."""
    optimizer: str = "COBYLA"
    shots: int = 1000
    max_iterations: int = 200
    convergence_threshold: float = 1e-6
    initial_params: Optional[np.ndarray] = None
    ansatz_type: str = "UCCSD"
    ansatz_layers: int = 1


class AnsatzLibrary:
    """Library of parameterized quantum circuit ansätze."""
    
    @staticmethod
    def hardware_efficient(params: np.ndarray, wires: List[int], layers: int = 1):
        """
        Hardware-efficient ansatz with Ry-Rz rotations and CNOT entanglement.
        
        Args:
            params: Parameter array of shape (layers, num_qubits, 2)
            wires: Qubit indices
            layers: Number of ansatz layers
        """
        num_qubits = len(wires)
        params = params.reshape(layers, num_qubits, 2)
        
        for layer in range(layers):
            # Single-qubit rotations
            for i, w in enumerate(wires):
                qml.RY(params[layer, i, 0], wires=w)
                qml.RZ(params[layer, i, 1], wires=w)
            
            # Entangling layer (linear connectivity)
            for i in range(num_qubits - 1):
                qml.CNOT(wires=[wires[i], wires[i + 1]])
    
    @staticmethod
    def strongly_entangling(params: np.ndarray, wires: List[int], layers: int = 1):
        """
        Strongly entangling layers from PennyLane.
        
        Args:
            params: Parameter array
            wires: Qubit indices
            layers: Number of layers
        """
        qml.templates.StronglyEntanglingLayers(params, wires=wires)
    
    @staticmethod
    def uccsd(params: np.ndarray, wires: List[int], s_wires: List = None, d_wires: List = None):
        """
        UCCSD (Unitary Coupled Cluster Singles and Doubles) ansatz.
        
        Standard ansatz for quantum chemistry VQE.
        """
        # Simplified UCCSD-like ansatz
        num_qubits = len(wires)
        
        # Hartree-Fock initial state
        for i in range(num_qubits // 2):
            qml.PauliX(wires=wires[i])
        
        # Single excitations
        param_idx = 0
        for i in range(num_qubits // 2):
            for j in range(num_qubits // 2, num_qubits):
                if param_idx < len(params):
                    # Givens rotation for single excitation
                    qml.SingleExcitation(params[param_idx], wires=[wires[i], wires[j]])
                    param_idx += 1
        
        # Double excitations (simplified)
        for i in range(num_qubits // 2 - 1):
            for j in range(num_qubits // 2, num_qubits - 1):
                if param_idx < len(params):
                    qml.DoubleExcitation(
                        params[param_idx],
                        wires=[wires[i], wires[i + 1], wires[j], wires[j + 1]]
                    )
                    param_idx += 1
    
    @staticmethod
    def particle_conserving(params: np.ndarray, wires: List[int], init_state: List[int] = None):
        """
        Particle-conserving ansatz for fermionic systems.
        """
        num_qubits = len(wires)
        if init_state is None:
            init_state = [1] * (num_qubits // 2) + [0] * (num_qubits - num_qubits // 2)
        
        qml.templates.ParticleConservingU2(params, wires=wires, init_state=init_state)


class VQERunner:
    """
    VQE Runner for quantum chemistry and physics simulations.
    
    Supports molecular ground state energy calculations and
    quantum many-body physics simulations.
    """
    
    def __init__(
        self,
        backend: Optional[QuantumBackend] = None,
        config: Optional[VQEConfig] = None,
    ):
        """
        Initialize VQE runner.
        
        Args:
            backend: Quantum backend (default: local simulator)
            config: VQE configuration
        """
        self.backend = backend or LocalSimulatorBackend(
            BackendConfig(backend_type=BackendType.LOCAL_SIMULATOR)
        )
        self.config = config or VQEConfig()
        self._history: List[JobResult] = []
        self.ansatz_library = AnsatzLibrary()
    
    def get_ansatz(self, ansatz_type: str) -> Callable:
        """Get ansatz function by name."""
        ansatz_map = {
            "hardware_efficient": self.ansatz_library.hardware_efficient,
            "strongly_entangling": self.ansatz_library.strongly_entangling,
            "UCCSD": self.ansatz_library.uccsd,
            "particle_conserving": self.ansatz_library.particle_conserving,
        }
        return ansatz_map.get(ansatz_type, self.ansatz_library.hardware_efficient)
    
    async def solve(
        self,
        hamiltonian: VQEHamiltonian,
        config: Optional[VQEConfig] = None,
        ansatz: Optional[Callable] = None,
    ) -> JobResult:
        """
        Find ground state energy using VQE.
        
        Args:
            hamiltonian: VQE Hamiltonian instance
            config: Optional config override
            ansatz: Optional custom ansatz function
            
        Returns:
            JobResult with ground state energy estimate
        """
        from scipy.optimize import minimize
        from datetime import datetime
        import uuid
        
        cfg = config or self.config
        H = hamiltonian.hamiltonian()
        num_qubits = hamiltonian.num_qubits
        wires = hamiltonian.wires
        
        # Select ansatz
        if ansatz is None:
            ansatz_fn = self.get_ansatz(cfg.ansatz_type)
        else:
            ansatz_fn = ansatz
        
        # Determine number of parameters
        if cfg.ansatz_type == "hardware_efficient":
            num_params = cfg.ansatz_layers * num_qubits * 2
        elif cfg.ansatz_type == "strongly_entangling":
            num_params = cfg.ansatz_layers * num_qubits * 3
        elif cfg.ansatz_type == "UCCSD":
            # Singles + Doubles
            n_occ = num_qubits // 2
            n_virt = num_qubits - n_occ
            num_params = n_occ * n_virt + (n_occ - 1) * (n_virt - 1)
        else:
            num_params = cfg.ansatz_layers * num_qubits * 2
        
        # Initialize parameters
        if cfg.initial_params is not None:
            initial_params = cfg.initial_params
        else:
            initial_params = np.random.uniform(-0.1, 0.1, num_params)
        
        # Create quantum device
        dev = qml.device("default.qubit", wires=num_qubits)
        
        # Store config values for closure
        ansatz_layers = cfg.ansatz_layers
        ansatz_type = cfg.ansatz_type
        
        @qml.qnode(dev)
        def circuit(params):
            # Call ansatz based on type (different signatures)
            if ansatz_type == "UCCSD":
                ansatz_fn(params, wires)
            elif ansatz_type == "strongly_entangling":
                # StronglyEntanglingLayers expects specific shape
                reshaped = params.reshape(ansatz_layers, num_qubits, 3)
                ansatz_fn(reshaped, wires, ansatz_layers)
            else:
                # hardware_efficient and others
                ansatz_fn(params, wires, ansatz_layers)
            return qml.expval(H)
        
        # Optimization
        job_id = str(uuid.uuid4())
        submitted_at = datetime.utcnow()
        convergence_history = []
        
        def cost_fn(params):
            energy = float(circuit(params))
            convergence_history.append(energy)
            return energy
        
        try:
            # Map optimizer-specific options
            optimizer_options = {"maxiter": cfg.max_iterations}
            
            # Different optimizers use different convergence parameters
            # COBYLA uses rhobeg/rhoend, BFGS/L-BFGS-B use gtol, others use tol
            if cfg.optimizer.upper() in ["BFGS", "L-BFGS-B", "CG"]:
                optimizer_options["gtol"] = cfg.convergence_threshold
            elif cfg.optimizer.upper() == "COBYLA":
                optimizer_options["rhobeg"] = 0.5
                optimizer_options["tol"] = cfg.convergence_threshold
            elif cfg.optimizer.upper() in ["NELDER-MEAD", "POWELL"]:
                optimizer_options["xatol"] = cfg.convergence_threshold
                optimizer_options["fatol"] = cfg.convergence_threshold
            else:
                # Generic fallback for SLSQP and others
                optimizer_options["ftol"] = cfg.convergence_threshold
            
            result = minimize(
                cost_fn,
                initial_params,
                method=cfg.optimizer,
                options=optimizer_options,
            )
            
            job_result = JobResult(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                backend_type=self.backend.backend_type,
                device_name="default.qubit",
                submitted_at=submitted_at,
                completed_at=datetime.utcnow(),
                optimal_value=float(result.fun),
                optimal_params=result.x,
                convergence_history=convergence_history,
                raw_result={
                    "optimizer_result": {
                        "success": result.success,
                        "message": result.message,
                        "nfev": result.nfev,
                    },
                    "hamiltonian_type": type(hamiltonian).__name__,
                },
            )
        except Exception as e:
            job_result = JobResult(
                job_id=job_id,
                status=JobStatus.FAILED,
                backend_type=self.backend.backend_type,
                device_name="default.qubit",
                submitted_at=submitted_at,
                completed_at=datetime.utcnow(),
                error_message=str(e),
            )
        
        self._history.append(job_result)
        return job_result
    
    async def potential_energy_surface(
        self,
        molecule_builder: Callable[[float], VQEHamiltonian],
        bond_lengths: List[float],
        config: Optional[VQEConfig] = None,
    ) -> Dict[str, Any]:
        """
        Calculate potential energy surface by varying bond length.
        
        Args:
            molecule_builder: Function that creates Hamiltonian for given bond length
            bond_lengths: List of bond lengths to evaluate
            config: VQE configuration
            
        Returns:
            Dictionary with bond lengths and corresponding energies
        """
        energies = []
        params_history = []
        
        cfg = config or self.config
        prev_params = None
        
        for length in bond_lengths:
            # Build Hamiltonian for this geometry
            hamiltonian = molecule_builder(length)
            
            # Use previous parameters as initial guess (warm start)
            if prev_params is not None:
                cfg.initial_params = prev_params
            
            # Run VQE
            result = await self.solve(hamiltonian, cfg)
            
            energies.append(result.optimal_value)
            prev_params = result.optimal_params
            params_history.append(result.optimal_params)
        
        # Find equilibrium geometry
        min_idx = np.argmin(energies)
        
        return {
            "bond_lengths": bond_lengths,
            "energies": energies,
            "equilibrium_length": bond_lengths[min_idx],
            "equilibrium_energy": energies[min_idx],
            "params_history": params_history,
        }
    
    def get_history(self) -> List[JobResult]:
        """Get execution history."""
        return self._history
    
    def clear_history(self) -> None:
        """Clear execution history."""
        self._history = []

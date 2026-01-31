"""
Hybrid VQE optimizer.

Variational Quantum Eigensolver with classical optimization of ansatz parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.typing import NDArray

from ...domain.models.problem import OptimizationProblem
from ...domain.models.result import OptimizationResult, QuantumExecutionResult
from ...domain.ports.quantum_backend import QuantumBackend
from ..classical.base import OptimizationHistory

if TYPE_CHECKING:
    pass


class AnsatzType(str, Enum):
    """Variational ansatz types."""
    RY = "ry"  # Single-qubit RY rotations
    RY_RZ = "ry_rz"  # RY and RZ rotations
    HARDWARE_EFFICIENT = "hardware_efficient"
    UCCSD = "uccsd"  # Unitary Coupled Cluster
    QAOA = "qaoa"


class GradientMethod(str, Enum):
    """Gradient estimation methods."""
    PARAMETER_SHIFT = "parameter_shift"
    FINITE_DIFFERENCE = "finite_difference"
    SPSA = "spsa"  # Simultaneous Perturbation
    NATURAL_GRADIENT = "natural_gradient"


@dataclass
class HybridVQEConfig:
    """Configuration for Hybrid VQE."""
    ansatz_type: AnsatzType = AnsatzType.HARDWARE_EFFICIENT
    ansatz_layers: int = 2
    shots: int = 1024
    max_iterations: int = 100
    optimizer: str = "L-BFGS-B"
    gradient_method: GradientMethod = GradientMethod.PARAMETER_SHIFT
    learning_rate: float = 0.1
    convergence_threshold: float = 1e-6
    spsa_a: float = 0.1  # SPSA parameters
    spsa_c: float = 0.1


@dataclass
class HybridVQEOptimizer:
    """
    Hybrid Quantum-Classical VQE Optimizer.
    
    Uses variational quantum circuits to estimate ground state energy
    with classical optimization of circuit parameters.
    """
    
    name: str = "hybrid_vqe"
    config: HybridVQEConfig = field(default_factory=HybridVQEConfig)
    backend: QuantumBackend | None = None
    
    def supports(self, problem: OptimizationProblem) -> bool:
        """VQE works for Hamiltonian ground state problems."""
        return problem.metadata.get("type") in ["hamiltonian", "chemistry", "ising"]
    
    def optimize(
        self,
        problem: OptimizationProblem,
        *,
        context: dict | None = None,
    ) -> OptimizationResult:
        """Run hybrid VQE optimization."""
        from scipy.optimize import minimize
        
        context = context or {}
        
        if self.backend is None:
            raise ValueError("Quantum backend not configured")
        
        n_qubits = len(problem.variables)
        n_params = self._count_parameters(n_qubits)
        
        # Initialize parameters
        initial_params = np.random.uniform(-np.pi, np.pi, size=n_params)
        
        history = OptimizationHistory()
        quantum_results: list[QuantumExecutionResult] = []
        iteration = 0
        
        def energy_function(params: NDArray) -> float:
            """Compute energy expectation value."""
            nonlocal iteration
            
            circuit = self._build_ansatz(n_qubits, params)
            
            # Measure in computational basis
            result = self.backend.run(
                circuit,
                shots=self.config.shots,
                options=context.get("backend_options", {}),
            )
            
            # Compute expectation value of Hamiltonian
            energy = self._compute_energy(result, problem)
            
            quantum_results.append(QuantumExecutionResult(
                counts=result.get("counts", {}),
                shots=self.config.shots,
                metadata={"params": params.tolist(), "iteration": iteration},
            ))
            
            history.record(energy, params.tolist())
            iteration += 1
            
            return energy
        
        # Compute gradient if using gradient-based optimizer
        gradient_func = None
        if self.config.gradient_method == GradientMethod.PARAMETER_SHIFT:
            gradient_func = lambda p: self._parameter_shift_gradient(
                p, n_qubits, problem, context
            )
        elif self.config.gradient_method == GradientMethod.SPSA:
            gradient_func = lambda p: self._spsa_gradient(
                p, n_qubits, problem, context, iteration
            )
        
        # Run optimization
        if gradient_func and self.config.optimizer in ["L-BFGS-B", "BFGS", "CG"]:
            result = minimize(
                energy_function,
                initial_params,
                method=self.config.optimizer,
                jac=gradient_func,
                options={"maxiter": self.config.max_iterations},
            )
        else:
            result = minimize(
                energy_function,
                initial_params,
                method=self.config.optimizer,
                options={"maxiter": self.config.max_iterations},
            )
        
        return OptimizationResult(
            optimal_value=float(result.fun),
            optimal_parameters=result.x.tolist(),
            iterations=iteration,
            converged=result.success if hasattr(result, 'success') else True,
            history=history.to_dict(),
            metadata={
                "algorithm": self.name,
                "ansatz": self.config.ansatz_type.value,
                "layers": self.config.ansatz_layers,
                "n_qubits": n_qubits,
            },
        )
    
    def _count_parameters(self, n_qubits: int) -> int:
        """Count the number of variational parameters."""
        if self.config.ansatz_type == AnsatzType.RY:
            return n_qubits * self.config.ansatz_layers
        elif self.config.ansatz_type == AnsatzType.RY_RZ:
            return 2 * n_qubits * self.config.ansatz_layers
        elif self.config.ansatz_type == AnsatzType.HARDWARE_EFFICIENT:
            # RY + RZ per qubit per layer + entangling
            return 2 * n_qubits * self.config.ansatz_layers
        else:
            return n_qubits * self.config.ansatz_layers
    
    def _build_ansatz(self, n_qubits: int, params: NDArray) -> Any:
        """Build variational ansatz circuit."""
        try:
            from qiskit import QuantumCircuit
        except ImportError:
            raise ImportError("Qiskit required for VQE circuit construction")
        
        qc = QuantumCircuit(n_qubits)
        param_idx = 0
        
        for layer in range(self.config.ansatz_layers):
            # Single-qubit rotations
            for q in range(n_qubits):
                if self.config.ansatz_type in [AnsatzType.RY, AnsatzType.HARDWARE_EFFICIENT]:
                    qc.ry(params[param_idx], q)
                    param_idx += 1
                
                if self.config.ansatz_type in [AnsatzType.RY_RZ, AnsatzType.HARDWARE_EFFICIENT]:
                    if param_idx < len(params):
                        qc.rz(params[param_idx], q)
                        param_idx += 1
            
            # Entangling layer (linear connectivity)
            if self.config.ansatz_type == AnsatzType.HARDWARE_EFFICIENT:
                for q in range(n_qubits - 1):
                    qc.cx(q, q + 1)
        
        qc.measure_all()
        return qc
    
    def _compute_energy(self, result: dict, problem: OptimizationProblem) -> float:
        """Compute energy expectation from measurements."""
        counts = result.get("counts", {})
        total = sum(counts.values())
        
        energy = 0.0
        for bitstring, count in counts.items():
            # Interpret bitstring as configuration
            config = [int(b) for b in bitstring]
            # Use problem's objective function
            energy += problem.evaluate(config) * count / total
        
        return energy
    
    def _parameter_shift_gradient(
        self,
        params: NDArray,
        n_qubits: int,
        problem: OptimizationProblem,
        context: dict,
    ) -> NDArray:
        """Compute gradient using parameter shift rule."""
        gradient = np.zeros_like(params)
        shift = np.pi / 2
        
        for i in range(len(params)):
            # Forward shift
            params_plus = params.copy()
            params_plus[i] += shift
            circuit_plus = self._build_ansatz(n_qubits, params_plus)
            result_plus = self.backend.run(
                circuit_plus,
                shots=self.config.shots // 2,
                options=context.get("backend_options", {}),
            )
            energy_plus = self._compute_energy(result_plus, problem)
            
            # Backward shift
            params_minus = params.copy()
            params_minus[i] -= shift
            circuit_minus = self._build_ansatz(n_qubits, params_minus)
            result_minus = self.backend.run(
                circuit_minus,
                shots=self.config.shots // 2,
                options=context.get("backend_options", {}),
            )
            energy_minus = self._compute_energy(result_minus, problem)
            
            gradient[i] = (energy_plus - energy_minus) / 2
        
        return gradient
    
    def _spsa_gradient(
        self,
        params: NDArray,
        n_qubits: int,
        problem: OptimizationProblem,
        context: dict,
        iteration: int,
    ) -> NDArray:
        """Compute gradient using SPSA."""
        # Decay parameters
        a = self.config.spsa_a / ((iteration + 1) ** 0.602)
        c = self.config.spsa_c / ((iteration + 1) ** 0.101)
        
        # Random perturbation
        delta = np.random.choice([-1, 1], size=len(params))
        
        # Perturbed evaluations
        params_plus = params + c * delta
        circuit_plus = self._build_ansatz(n_qubits, params_plus)
        result_plus = self.backend.run(
            circuit_plus,
            shots=self.config.shots // 2,
            options=context.get("backend_options", {}),
        )
        energy_plus = self._compute_energy(result_plus, problem)
        
        params_minus = params - c * delta
        circuit_minus = self._build_ansatz(n_qubits, params_minus)
        result_minus = self.backend.run(
            circuit_minus,
            shots=self.config.shots // 2,
            options=context.get("backend_options", {}),
        )
        energy_minus = self._compute_energy(result_minus, problem)
        
        # SPSA gradient estimate
        gradient = (energy_plus - energy_minus) / (2 * c * delta)
        
        return gradient


class NoisyVQEOptimizer(HybridVQEOptimizer):
    """
    VQE optimizer with noise-aware strategies.
    
    Implements error mitigation and noise-resilient optimization.
    """
    
    name = "noisy_vqe"
    
    def __init__(
        self,
        config: HybridVQEConfig | None = None,
        backend: QuantumBackend | None = None,
        error_mitigation: str = "none",
    ):
        super().__init__()
        self.config = config or HybridVQEConfig()
        self.backend = backend
        self.error_mitigation = error_mitigation
    
    def _compute_energy(self, result: dict, problem: OptimizationProblem) -> float:
        """Compute energy with error mitigation."""
        energy = super()._compute_energy(result, problem)
        
        if self.error_mitigation == "zero_noise_extrapolation":
            energy = self._zero_noise_extrapolation(energy)
        elif self.error_mitigation == "measurement_error_mitigation":
            energy = self._measurement_error_mitigation(energy, result)
        
        return energy
    
    def _zero_noise_extrapolation(self, energy: float) -> float:
        """Apply zero-noise extrapolation (simplified)."""
        # In practice, would run at multiple noise levels
        return energy
    
    def _measurement_error_mitigation(
        self,
        energy: float,
        result: dict,
    ) -> float:
        """Apply measurement error mitigation."""
        # Simplified - would use calibration matrix
        return energy

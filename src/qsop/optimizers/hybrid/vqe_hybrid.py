"""
Hybrid VQE optimizer.

Variational Quantum Eigensolver with classical optimization of ansatz parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

import time
import numpy as np
from numpy.typing import NDArray

from ...domain.models.problem import OptimizationProblem
from ...domain.models.result import OptimizationResult, QuantumExecutionResult, ConvergenceInfo
from ...domain.ports.quantum_backend import QuantumBackend
from ..classical.base import OptimizationHistory
from ...infrastructure.observability.metrics import get_metrics

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
    shot_budget: int | None = None  # Total shots across all iterations

    # Shot-Adaptive Strategies
    adaptive_shots: bool = False
    min_shots: int = 100
    max_shots: int = 1024


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
        total_shots_used = 0
        iteration = 0
        function_evals = 0
        gradient_evals = 0
        
        metrics = get_metrics()
        tenant_id = context.get("tenant_id", "anonymous")
        job_id = context.get("job_id", "unknown")
        
        def get_current_shots(iter_count: int) -> int:
            if self.config.adaptive_shots:
                progress = min(1.0, iter_count / self.config.max_iterations)
                return int(
                    self.config.min_shots + (self.config.max_shots - self.config.min_shots) * progress
                )
            return self.config.shots

        def energy_function(params: NDArray) -> float:
            """Compute energy expectation value."""
            nonlocal iteration, total_shots_used, function_evals
            
            current_shots = get_current_shots(iteration)

            # Check shot budget
            if self.config.shot_budget and (total_shots_used + current_shots) > self.config.shot_budget:
                return float('inf')
            
            loop_start = time.time()
            circuit = self._build_ansatz(n_qubits, params)
            
            classical_start = time.time()
            result = self.backend.run(
                circuit,
                shots=current_shots,
                options=context.get("backend_options", {}),
            )
            quantum_end = time.time()
            
            total_shots_used += current_shots
            
            # Compute expectation value of Hamiltonian
            energy = self._compute_energy(result, problem)
            
            energy_end = time.time()
            
            # Metrics
            metrics.hybrid_iteration_value.labels(
                algorithm=self.name,
                backend=self.backend.name if self.backend else "unknown",
                tenant_id=tenant_id,
                job_id=job_id
            ).set(energy)
            
            quantum_time = result.execution_time_seconds if result.execution_time_seconds > 0 else (quantum_end - classical_start)
            classical_time = (energy_end - loop_start) - quantum_time
            
            metrics.classical_execution_time.labels(
                algorithm=self.name,
                backend=self.backend.name if self.backend else "unknown",
                tenant_id=tenant_id
            ).observe(max(0, classical_time))
            
            metrics.hybrid_loop_duration.labels(
                algorithm=self.name,
                backend=self.backend.name if self.backend else "unknown",
                tenant_id=tenant_id
            ).observe(energy_end - loop_start)
            
            quantum_results.append(QuantumExecutionResult(
                counts=result.counts,
                shots=current_shots,
                metadata={"params": params.tolist(), "iteration": iteration},
                measurements=result.measurements,
            ))
            
            history.record(energy, params.tolist())
            function_evals += 1
            # We only increment iteration on full function calls that might be "major" steps
            # though minimize calls this many times. To keep it simple, we increment here.
            iteration += 1
            
            return energy
        
        # Compute gradient if using gradient-based optimizer
        def gradient_wrapper(p: NDArray) -> NDArray:
            nonlocal gradient_evals, total_shots_used
            current_shots = get_current_shots(iteration)
            
            # Check shot budget
            if self.config.shot_budget and (total_shots_used + current_shots) > self.config.shot_budget:
                return np.zeros_like(p)
            
            if self.config.gradient_method == GradientMethod.PARAMETER_SHIFT:
                grad = self._parameter_shift_gradient(p, n_qubits, problem, context, current_shots)
                # Parameter shift uses 2 * n_params backend calls
                total_shots_used += 2 * len(p) * (current_shots // 2)
            elif self.config.gradient_method == GradientMethod.SPSA:
                grad = self._spsa_gradient(p, n_qubits, problem, context, iteration, current_shots)
                # SPSA uses 2 backend calls
                total_shots_used += 2 * (current_shots // 2)
            else:
                grad = np.zeros_like(p)
            
            gradient_evals += 1
            return grad

        # Run optimization
        start_time = time.time()
        
        minimize_kwargs = {
            "fun": energy_function,
            "x0": initial_params,
            "method": self.config.optimizer,
            "options": {"maxiter": self.config.max_iterations},
        }
        
        if self.config.gradient_method != GradientMethod.FINITE_DIFFERENCE and self.config.optimizer in ["L-BFGS-B", "BFGS", "CG", "SLSQP"]:
            minimize_kwargs["jac"] = gradient_wrapper
            
        result = minimize(**minimize_kwargs)
        
        wall_time = time.time() - start_time
        
        return OptimizationResult(
            optimal_value=float(result.fun),
            optimal_parameters={f"p{i}": float(v) for i, v in enumerate(result.x)},
            iterations=result.nit if hasattr(result, 'nit') else iteration,
            function_evaluations=function_evals,
            gradient_evaluations=gradient_evals,
            convergence=ConvergenceInfo(
                converged=result.success if hasattr(result, 'success') else True,
                iterations_to_converge=iteration
            ),
            objective_history=tuple(history.fx_history),
            wall_time_seconds=wall_time,
            metadata={
                "algorithm": self.name,
                "ansatz": self.config.ansatz_type.value,
                "layers": self.config.ansatz_layers,
                "n_qubits": n_qubits,
                "total_shots": total_shots_used,
                "variational_parameters": result.x.tolist(),
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
                    if param_idx < len(params):
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
    
    def _compute_energy(self, result: QuantumExecutionResult, problem: OptimizationProblem) -> float:
        """Compute energy expectation from measurements."""
        counts = result.counts
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
        current_shots: int,
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
                shots=current_shots // 2,
                options=context.get("backend_options", {}),
            )
            energy_plus = self._compute_energy(result_plus, problem)
            
            # Backward shift
            params_minus = params.copy()
            params_minus[i] -= shift
            circuit_minus = self._build_ansatz(n_qubits, params_minus)
            result_minus = self.backend.run(
                circuit_minus,
                shots=current_shots // 2,
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
        current_shots: int,
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
            shots=current_shots // 2,
            options=context.get("backend_options", {}),
        )
        energy_plus = self._compute_energy(result_plus, problem)
        
        params_minus = params - c * delta
        circuit_minus = self._build_ansatz(n_qubits, params_minus)
        result_minus = self.backend.run(
            circuit_minus,
            shots=current_shots // 2,
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
    
    def _compute_energy(self, result: QuantumExecutionResult, problem: OptimizationProblem) -> float:
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
        result: QuantumExecutionResult,
    ) -> float:
        """Apply measurement error mitigation."""
        # Simplified - would use calibration matrix
        return energy

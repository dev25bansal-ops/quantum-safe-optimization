"""
Hybrid QAOA optimizer.

Combines quantum circuit evaluation with classical parameter optimization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

import time
import numpy as np
from numpy.typing import NDArray

from ...domain.models.problem import OptimizationProblem
from ...domain.models.result import OptimizationResult, QuantumExecutionResult
from ...domain.ports.optimizer import Optimizer
from ...domain.ports.quantum_backend import QuantumBackend
from ..classical.base import OptimizationHistory
from ...infrastructure.observability.metrics import get_metrics

if TYPE_CHECKING:
    from ..quantum.qaoa import QAOACircuitBuilder


@dataclass
class HybridQAOAConfig:
    """Configuration for Hybrid QAOA."""
    p_layers: int = 2
    shots: int = 1024
    max_iterations: int = 100
    optimizer: str = "COBYLA"  # Classical optimizer for parameters
    initial_params: list[float] | None = None
    shot_budget: int | None = None  # Total shots across all iterations
    param_bounds: tuple[float, float] = (0.0, 2 * np.pi)


@dataclass
class HybridQAOAOptimizer:
    """
    Hybrid Quantum-Classical QAOA Optimizer.
    
    Uses a quantum circuit to evaluate the cost function and a classical
    optimizer to update the variational parameters.
    """
    
    name: str = "hybrid_qaoa"
    config: HybridQAOAConfig = field(default_factory=HybridQAOAConfig)
    backend: QuantumBackend | None = None
    circuit_builder: Any = None  # QAOACircuitBuilder
    
    def supports(self, problem: OptimizationProblem) -> bool:
        """QAOA works for combinatorial optimization problems."""
        return problem.metadata.get("type") in ["maxcut", "qubo", "combinatorial"]
    
    def optimize(
        self,
        problem: OptimizationProblem,
        *,
        context: dict | None = None,
    ) -> OptimizationResult:
        """
        Run hybrid QAOA optimization.
        
        The outer loop uses classical optimization to find optimal
        variational parameters, while the inner loop evaluates the
        cost function using quantum circuit execution.
        """
        from scipy.optimize import minimize
        
        context = context or {}
        
        if self.backend is None:
            raise ValueError("Quantum backend not configured")
        
        # Build problem Hamiltonian and QAOA circuit
        n_qubits = len(problem.variables)
        n_params = 2 * self.config.p_layers  # gamma and beta for each layer
        
        # Initialize parameters
        if self.config.initial_params:
            initial_params = np.array(self.config.initial_params)
        else:
            initial_params = np.random.uniform(
                self.config.param_bounds[0],
                self.config.param_bounds[1],
                size=n_params,
            )
        
        history = OptimizationHistory()
        quantum_results: list[QuantumExecutionResult] = []
        total_shots_used = 0
        iteration = 0
        
        metrics = get_metrics()
        tenant_id = context.get("tenant_id", "anonymous")
        job_id = context.get("job_id", "unknown")
        
        def cost_function(params: NDArray) -> float:
            """Evaluate cost using quantum circuit."""
            nonlocal total_shots_used, iteration
            
            # Check shot budget
            if self.config.shot_budget and total_shots_used >= self.config.shot_budget:
                return float('inf')
            
            loop_start = time.time()
            # Build and run circuit
            circuit = self._build_circuit(problem, params)
            
            classical_start = time.time()
            result = self.backend.run(
                circuit,
                shots=self.config.shots,
                options=context.get("backend_options", {}),
            )
            quantum_end = time.time()
            
            total_shots_used += self.config.shots
            
            # Compute expectation value
            expectation = self._compute_expectation(result, problem)
            
            cost_end = time.time()
            
            # Metrics
            metrics.hybrid_iteration_value.labels(
                algorithm=self.name,
                backend=self.backend.name if self.backend else "unknown",
                tenant_id=tenant_id,
                job_id=job_id
            ).set(expectation)
            
            quantum_time = result.get("metadata", {}).get("execution_time", quantum_end - classical_start)
            classical_time = (cost_end - loop_start) - quantum_time
            
            metrics.classical_execution_time.labels(
                algorithm=self.name,
                backend=self.backend.name if self.backend else "unknown",
                tenant_id=tenant_id
            ).observe(max(0, classical_time))
            
            metrics.hybrid_loop_duration.labels(
                algorithm=self.name,
                backend=self.backend.name if self.backend else "unknown",
                tenant_id=tenant_id
            ).observe(cost_end - loop_start)
            
            quantum_results.append(QuantumExecutionResult(
                counts=result.get("counts", {}),
                shots=self.config.shots,
                metadata={"params": params.tolist(), "iteration": iteration},
            ))
            
            history.record(expectation, params.tolist())
            iteration += 1
            
            return expectation
        
        # Run classical optimization
        bounds = [(self.config.param_bounds[0], self.config.param_bounds[1])] * n_params
        
        result = minimize(
            cost_function,
            initial_params,
            method=self.config.optimizer,
            options={"maxiter": self.config.max_iterations},
        )
        
        # Extract best solution from measurement results
        best_solution = self._extract_best_solution(quantum_results, problem)
        
        return OptimizationResult(
            optimal_value=float(result.fun),
            optimal_parameters=result.x.tolist(),
            iterations=result.nit if hasattr(result, 'nit') else iteration,
            converged=result.success if hasattr(result, 'success') else True,
            history=history.to_dict(),
            metadata={
                "algorithm": self.name,
                "p_layers": self.config.p_layers,
                "total_shots": total_shots_used,
                "best_bitstring": best_solution,
                "quantum_results_count": len(quantum_results),
            },
        )
    
    def _build_circuit(self, problem: OptimizationProblem, params: NDArray) -> Any:
        """Build QAOA circuit with given parameters."""
        if self.circuit_builder is None:
            # Use default circuit builder
            from ..quantum.qaoa import build_qaoa_circuit
            return build_qaoa_circuit(problem, params, self.config.p_layers)
        return self.circuit_builder.build(problem, params)
    
    def _compute_expectation(
        self,
        result: dict,
        problem: OptimizationProblem,
    ) -> float:
        """Compute expectation value from measurement results."""
        counts = result.get("counts", {})
        total = sum(counts.values())
        
        expectation = 0.0
        for bitstring, count in counts.items():
            # Convert bitstring to solution
            solution = [int(b) for b in bitstring]
            # Evaluate problem objective
            cost = problem.evaluate(solution)
            expectation += cost * count / total
        
        return expectation
    
    def _extract_best_solution(
        self,
        quantum_results: list[QuantumExecutionResult],
        problem: OptimizationProblem,
    ) -> str:
        """Extract the best solution from all quantum measurements."""
        best_bitstring = ""
        best_cost = float('inf')
        
        for qr in quantum_results:
            for bitstring, count in qr.counts.items():
                solution = [int(b) for b in bitstring]
                cost = problem.evaluate(solution)
                if cost < best_cost:
                    best_cost = cost
                    best_bitstring = bitstring
        
        return best_bitstring


@dataclass
class AdaptiveQAOAConfig:
    """Configuration for Adaptive QAOA."""
    initial_p: int = 1
    max_p: int = 10
    shots: int = 1024
    convergence_threshold: float = 1e-4
    optimizer: str = "COBYLA"


class AdaptiveQAOAOptimizer:
    """
    Adaptive QAOA that increases circuit depth based on convergence.
    
    Starts with shallow circuits and increases depth (p) when
    optimization plateaus.
    """
    
    name = "adaptive_qaoa"
    
    def __init__(
        self,
        config: AdaptiveQAOAConfig | None = None,
        backend: QuantumBackend | None = None,
    ):
        self.config = config or AdaptiveQAOAConfig()
        self.backend = backend
    
    def optimize(
        self,
        problem: OptimizationProblem,
        *,
        context: dict | None = None,
    ) -> OptimizationResult:
        """Run adaptive QAOA with increasing depth."""
        context = context or {}
        
        current_p = self.config.initial_p
        best_params = None
        best_value = float('inf')
        all_history = []
        
        while current_p <= self.config.max_p:
            # Create hybrid optimizer for current depth
            hybrid_config = HybridQAOAConfig(
                p_layers=current_p,
                shots=self.config.shots,
                optimizer=self.config.optimizer,
            )
            
            # Initialize from previous solution if available
            if best_params is not None:
                # Extend parameters for new layer
                extended_params = list(best_params) + [0.1, 0.1]
                hybrid_config.initial_params = extended_params
            
            optimizer = HybridQAOAOptimizer(
                config=hybrid_config,
                backend=self.backend,
            )
            
            result = optimizer.optimize(problem, context=context)
            
            all_history.append({
                "p": current_p,
                "value": result.optimal_value,
                "params": result.optimal_parameters,
            })
            
            # Check improvement
            improvement = best_value - result.optimal_value
            
            if result.optimal_value < best_value:
                best_value = result.optimal_value
                best_params = result.optimal_parameters
            
            # Check convergence
            if improvement < self.config.convergence_threshold:
                break
            
            current_p += 1
        
        return OptimizationResult(
            optimal_value=best_value,
            optimal_parameters=best_params,
            iterations=current_p,
            converged=True,
            history={"adaptive_history": all_history},
            metadata={
                "algorithm": self.name,
                "final_p": current_p,
            },
        )

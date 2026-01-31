"""
QAOA workflow for combinatorial optimization.

Specializes the hybrid loop for QAOA problems like MaxCut.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from ...domain.models.problem import OptimizationProblem
from ...domain.models.result import (
    OptimizationResult,
    ConvergenceInfo,
    QuantumExecutionResult,
)
from ...domain.ports.quantum_backend import QuantumBackend
from ...domain.ports.transpilation import TranspilationService
from ...backends.mitigation import ReadoutMitigatedBackend, ZNEMitigatedBackend
from .hybrid_loop import HybridOptimizationLoop, HybridLoopConfig


@dataclass
class MaxCutProblem:
    """MaxCut problem definition."""
    n_nodes: int
    edges: list[tuple[int, int, float]]  # (node1, node2, weight)
    
    def to_optimization_problem(self) -> OptimizationProblem:
        """Convert to generic optimization problem."""
        from ...domain.models.problem import Variable, VariableType
        
        variables = [
            Variable(name=f"x_{i}", var_type=VariableType.BINARY)
            for i in range(self.n_nodes)
        ]
        
        def objective(x: dict[str, float]) -> float:
            """MaxCut objective (negative for minimization)."""
            cut_value = 0.0
            for i, j, w in self.edges:
                if x[f"x_{i}"] != x[f"x_{j}"]:
                    cut_value += w
            return -cut_value  # Minimize negative = maximize
        
        return OptimizationProblem(
            variables=variables,
            objective=objective,
            metadata={"type": "maxcut", "edges": self.edges},
        )


@dataclass
class QAOAWorkflowConfig:
    """Configuration for QAOA workflow."""
    p_layers: int = 2
    shots: int = 1024
    optimizer: str = "COBYLA"
    max_iterations: int = 100
    initial_gamma: float | None = None
    initial_beta: float | None = None
    enable_readout_mitigation: bool = False
    enable_zne: bool = False
    optimization_level: int = 1


class QAOAWorkflow:
    """
    QAOA workflow for combinatorial optimization.
    
    Implements the complete QAOA pipeline including:
    - Problem Hamiltonian construction
    - Mixer Hamiltonian
    - Parameterized circuit generation
    - Hybrid optimization loop
    """
    
    def __init__(
        self,
        config: QAOAWorkflowConfig | None = None,
        backend: QuantumBackend | None = None,
        transpiler: TranspilationService | None = None,
    ):
        self.config = config or QAOAWorkflowConfig()
        self.backend = self._apply_mitigation(backend) if backend else None
        self.transpiler = transpiler

    def _apply_mitigation(self, backend: QuantumBackend) -> QuantumBackend:
        """Apply configured error mitigation to the backend."""
        mitigated = backend
        if self.config.enable_readout_mitigation:
            mitigated = ReadoutMitigatedBackend(mitigated)
        if self.config.enable_zne:
            mitigated = ZNEMitigatedBackend(mitigated)
        return mitigated

    def run(self, problem: OptimizationProblem) -> OptimizationResult:
        """Execute QAOA workflow."""
        from scipy.optimize import minimize
        
        n_qubits = len(problem.variables)
        n_params = 2 * self.config.p_layers
        
        # Initialize parameters
        initial_params = self._initialize_params()
        
        history = []
        self._last_result = None
        
        def cost_function(params: NDArray) -> float:
            """Evaluate QAOA cost."""
            circuit = self._build_qaoa_circuit(problem, params, n_qubits)
            
            # Hardware-aware transpilation
            if self.transpiler and self.backend:
                circuit = self.transpiler.optimize_qaoa_layout(
                    circuit, 
                    self.backend.capabilities,
                    optimization_level=self.config.optimization_level
                )
                
            result = self.backend.run(circuit, shots=self.config.shots)
            self._last_result = result
            
            cost = self._compute_expectation(result, problem)
            history.append({'params': params.tolist(), 'cost': cost})
            
            return cost
        
        # Optimize
        result = minimize(
            cost_function,
            initial_params,
            method=self.config.optimizer,
            options={'maxiter': self.config.max_iterations},
        )
        
        # Extract best solution
        best_bitstring = self._extract_best(problem)
        
        return OptimizationResult(
            optimal_value=float(result.fun),
            optimal_parameters=self._format_params(result.x),
            iterations=result.nit if hasattr(result, "nit") else len(history),
            function_evaluations=result.nfev if hasattr(result, "nfev") else 0,
            convergence=ConvergenceInfo(
                converged=result.success if hasattr(result, "success") else True,
                reason=result.message if hasattr(result, "message") else "",
            ),
            objective_history=tuple(h["cost"] for h in history),
            metadata={
                'algorithm': 'qaoa',
                'p_layers': self.config.p_layers,
                'best_bitstring': best_bitstring,
            },
        )
    
    def _format_params(self, params: NDArray) -> dict[str, float]:
        """Format QAOA parameters into a dictionary."""
        formatted = {}
        for p in range(self.config.p_layers):
            formatted[f"γ_{p}"] = float(params[2 * p])
            formatted[f"β_{p}"] = float(params[2 * p + 1])
        return formatted
    
    def _initialize_params(self) -> NDArray:
        """Initialize QAOA parameters."""
        params = np.zeros(2 * self.config.p_layers)
        
        for p in range(self.config.p_layers):
            # gamma (cost layer parameter)
            if self.config.initial_gamma is not None:
                params[2*p] = self.config.initial_gamma
            else:
                params[2*p] = np.random.uniform(0, np.pi)
            
            # beta (mixer layer parameter)
            if self.config.initial_beta is not None:
                params[2*p + 1] = self.config.initial_beta
            else:
                params[2*p + 1] = np.random.uniform(0, np.pi/2)
        
        return params
    
    def _build_qaoa_circuit(
        self,
        problem: OptimizationProblem,
        params: NDArray,
        n_qubits: int,
    ) -> Any:
        """Build QAOA circuit."""
        try:
            from qiskit import QuantumCircuit
        except ImportError:
            raise ImportError("Qiskit required for QAOA circuits")
        
        qc = QuantumCircuit(n_qubits)
        
        # Initial superposition
        qc.h(range(n_qubits))
        
        # QAOA layers
        for p in range(self.config.p_layers):
            gamma = params[2*p]
            beta = params[2*p + 1]
            
            # Cost layer
            self._apply_cost_layer(qc, problem, gamma)
            
            # Mixer layer
            self._apply_mixer_layer(qc, beta, n_qubits)
        
        qc.measure_all()
        return qc
    
    def _apply_cost_layer(
        self,
        qc: Any,
        problem: OptimizationProblem,
        gamma: float,
    ) -> None:
        """Apply cost unitary exp(-i * gamma * C)."""
        edges = problem.metadata.get('edges', [])
        
        for i, j, w in edges:
            # ZZ interaction: exp(-i * gamma * w * Z_i Z_j)
            qc.cx(i, j)
            qc.rz(2 * gamma * w, j)
            qc.cx(i, j)
    
    def _apply_mixer_layer(
        self,
        qc: Any,
        beta: float,
        n_qubits: int,
    ) -> None:
        """Apply mixer unitary exp(-i * beta * B)."""
        # Standard X mixer
        for i in range(n_qubits):
            qc.rx(2 * beta, i)
    
    def _compute_expectation(
        self,
        result: QuantumExecutionResult,
        problem: OptimizationProblem,
    ) -> float:
        """Compute cost expectation from measurements."""
        counts = result.counts
        total = result.total_counts
        
        expectation = 0.0
        for bitstring, count in counts.items():
            # Qiskit uses little-endian for bitstrings
            solution = [int(b) for b in bitstring[::-1]]
            cost = problem.evaluate(solution)
            expectation += cost * count / total
        
        return expectation
    
    def _extract_best(self, problem: OptimizationProblem) -> str:
        """Extract best solution found."""
        if self._last_result is None:
            return ""
        
        best_bitstring = ""
        min_cost = float('inf')
        
        for bitstring, count in self._last_result.counts.items():
            # Qiskit uses little-endian for bitstrings
            solution = [int(b) for b in bitstring[::-1]]
            cost = problem.evaluate(solution)
            if cost < min_cost:
                min_cost = cost
                best_bitstring = bitstring
        
        return best_bitstring


def solve_maxcut(
    edges: list[tuple[int, int, float]],
    p_layers: int = 2,
    shots: int = 1024,
    backend: QuantumBackend | None = None,
) -> OptimizationResult:
    """
    Convenience function to solve MaxCut using QAOA.
    
    Args:
        edges: List of (node1, node2, weight) tuples
        p_layers: Number of QAOA layers
        shots: Measurement shots
        backend: Quantum backend
        
    Returns:
        Optimization result with best cut found
    """
    n_nodes = max(max(i, j) for i, j, _ in edges) + 1
    
    maxcut = MaxCutProblem(n_nodes=n_nodes, edges=edges)
    problem = maxcut.to_optimization_problem()
    
    config = QAOAWorkflowConfig(p_layers=p_layers, shots=shots)
    workflow = QAOAWorkflow(config=config, backend=backend)
    
    return workflow.run(problem)

"""
QAOA Runner

Orchestrates QAOA execution across different quantum backends.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

from ..backends.base import BackendConfig, BackendType, JobResult, QuantumBackend
from ..backends.simulator import LocalSimulatorBackend
from .problems import MaxCutProblem, QAOAProblem


@dataclass
class QAOAConfig:
    """Configuration for QAOA execution."""

    layers: int = 1
    optimizer: str = "COBYLA"
    shots: int = 1000
    max_iterations: int = 100
    initial_params: Optional[np.ndarray] = None
    use_warm_start: bool = False
    error_mitigation: bool = False


class QAOARunner:
    """
    QAOA Runner for solving combinatorial optimization problems.

    Supports multiple quantum backends and problem types.
    """

    def __init__(
        self,
        backend: Optional[QuantumBackend] = None,
        config: Optional[QAOAConfig] = None,
    ):
        """
        Initialize QAOA runner.

        Args:
            backend: Quantum backend (default: local simulator)
            config: QAOA configuration
        """
        self.backend = backend or LocalSimulatorBackend(
            BackendConfig(backend_type=BackendType.LOCAL_SIMULATOR)
        )
        self.config = config or QAOAConfig()
        self._history: List[JobResult] = []

    async def solve(
        self,
        problem: QAOAProblem,
        config: Optional[QAOAConfig] = None,
    ) -> JobResult:
        """
        Solve a QAOA problem.

        Args:
            problem: Problem instance (MaxCut, Portfolio, TSP, etc.)
            config: Optional config override

        Returns:
            JobResult with optimal solution
        """
        cfg = config or self.config

        # Ensure backend is connected
        if not self.backend.is_connected:
            await self.backend.connect()

        # Get Hamiltonians
        cost_h = problem.cost_hamiltonian()
        mixer_h = problem.mixer_hamiltonian()

        # Set initial parameters
        initial_params = cfg.initial_params
        if initial_params is None:
            if cfg.use_warm_start and len(self._history) > 0:
                # Use parameters from previous run
                last_result = self._history[-1]
                if last_result.optimal_params is not None:
                    initial_params = last_result.optimal_params
            else:
                # Random initialization
                initial_params = np.random.uniform(0, np.pi, 2 * cfg.layers)

        # Run QAOA
        result = await self.backend.run_qaoa(
            cost_hamiltonian=cost_h,
            mixer_hamiltonian=mixer_h,
            layers=cfg.layers,
            optimizer=cfg.optimizer,
            initial_params=initial_params,
            shots=cfg.shots,
        )

        # Store in history
        self._history.append(result)

        # Decode solution
        if result.optimal_bitstring:
            solution = problem.decode_solution(result.optimal_bitstring)
            result.raw_result = {
                "decoded_solution": solution,
                "problem_type": type(problem).__name__,
            }

        return result

    async def solve_maxcut(
        self,
        edges: List[tuple],
        weights: Optional[List[float]] = None,
        **kwargs,
    ) -> JobResult:
        """
        Convenience method for MaxCut problems.

        Args:
            edges: List of edges [(i, j), ...]
            weights: Optional edge weights
            **kwargs: Additional config parameters

        Returns:
            JobResult with cut solution
        """
        problem = MaxCutProblem(edges, weights)

        config = QAOAConfig(
            layers=kwargs.get("layers", self.config.layers),
            optimizer=kwargs.get("optimizer", self.config.optimizer),
            shots=kwargs.get("shots", self.config.shots),
        )

        return await self.solve(problem, config)

    async def parameter_sweep(
        self,
        problem: QAOAProblem,
        gamma_range: tuple = (0, np.pi),
        beta_range: tuple = (0, np.pi),
        resolution: int = 20,
    ) -> Dict[str, Any]:
        """
        Perform parameter sweep for single-layer QAOA.

        Useful for understanding the optimization landscape.

        Args:
            problem: Problem instance
            gamma_range: (min, max) for gamma
            beta_range: (min, max) for beta
            resolution: Number of points per dimension

        Returns:
            Dictionary with parameter grid and expectation values
        """
        import pennylane as qml

        gammas = np.linspace(gamma_range[0], gamma_range[1], resolution)
        betas = np.linspace(beta_range[0], beta_range[1], resolution)

        cost_h = problem.cost_hamiltonian()
        num_qubits = problem.num_qubits

        dev = qml.device("default.qubit", wires=num_qubits)

        @qml.qnode(dev)
        def circuit(gamma, beta):
            for w in range(num_qubits):
                qml.Hadamard(wires=w)

            qml.templates.ApproxTimeEvolution(cost_h, gamma, 1)

            for w in range(num_qubits):
                qml.RX(2 * beta, wires=w)

            return qml.expval(cost_h)

        # Evaluate on grid
        expectations = np.zeros((resolution, resolution))
        for i, gamma in enumerate(gammas):
            for j, beta in enumerate(betas):
                expectations[i, j] = circuit(gamma, beta)

        # Find optimal
        min_idx = np.unravel_index(np.argmin(expectations), expectations.shape)
        optimal_gamma = gammas[min_idx[0]]
        optimal_beta = betas[min_idx[1]]

        return {
            "gammas": gammas,
            "betas": betas,
            "expectations": expectations,
            "optimal_gamma": optimal_gamma,
            "optimal_beta": optimal_beta,
            "optimal_expectation": expectations[min_idx],
        }

    def get_history(self) -> List[JobResult]:
        """Get execution history."""
        return self._history

    def clear_history(self) -> None:
        """Clear execution history."""
        self._history = []

    async def benchmark(
        self,
        problem: QAOAProblem,
        layer_range: range = range(1, 6),
        num_trials: int = 5,
    ) -> Dict[str, Any]:
        """
        Benchmark QAOA performance across different layer counts.

        Args:
            problem: Problem instance
            layer_range: Range of layer counts to test
            num_trials: Number of trials per layer count

        Returns:
            Benchmark results
        """
        results = {}

        for layers in layer_range:
            layer_results = []

            for _ in range(num_trials):
                config = QAOAConfig(
                    layers=layers,
                    optimizer="COBYLA",
                    shots=1000,
                )
                result = await self.solve(problem, config)

                if result.optimal_value is not None:
                    layer_results.append(
                        {
                            "optimal_value": result.optimal_value,
                            "convergence_steps": len(result.convergence_history or []),
                        }
                    )

            if layer_results:
                values = [r["optimal_value"] for r in layer_results]
                results[layers] = {
                    "mean_value": np.mean(values),
                    "std_value": np.std(values),
                    "best_value": np.min(values),
                    "trials": layer_results,
                }

        return results

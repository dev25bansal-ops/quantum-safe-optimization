"""
Quantum Annealing Runner

Orchestrates quantum annealing execution on D-Wave systems.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

from ..backends.base import BackendConfig, BackendType, JobResult
from ..backends.dwave import DWaveBackend
from .problems import AnnealingProblem, QUBOProblem


@dataclass
class AnnealingConfig:
    """Configuration for quantum annealing."""

    num_reads: int = 1000
    annealing_time: Optional[int] = None  # microseconds
    use_hybrid: bool = True
    time_limit: int = 60  # seconds for hybrid
    chain_strength: Optional[float] = None
    auto_scale: bool = True


class AnnealingRunner:
    """
    Quantum Annealing Runner for D-Wave systems.

    Supports QUBO, Ising, and constrained optimization problems.
    """

    def __init__(
        self,
        backend: Optional[DWaveBackend] = None,
        config: Optional[AnnealingConfig] = None,
    ):
        """
        Initialize annealing runner.

        Args:
            backend: D-Wave backend (creates new one if not provided)
            config: Annealing configuration
        """
        self.backend = backend
        self.config = config or AnnealingConfig()
        self._history: List[JobResult] = []

    async def _ensure_backend(self):
        """Ensure D-Wave backend is connected."""
        if self.backend is None:
            self.backend = DWaveBackend(BackendConfig(backend_type=BackendType.DWAVE))

        if not self.backend.is_connected:
            await self.backend.connect()

    async def solve(
        self,
        problem: AnnealingProblem,
        config: Optional[AnnealingConfig] = None,
    ) -> JobResult:
        """
        Solve an annealing problem.

        Args:
            problem: Problem instance (QUBO, Ising, or Constrained)
            config: Optional config override

        Returns:
            JobResult with optimal solution
        """
        await self._ensure_backend()
        cfg = config or self.config

        # Convert to QUBO
        qubo = problem.to_qubo()

        # Run on D-Wave
        result = await self.backend.run_qubo(
            qubo_matrix=qubo,
            num_reads=cfg.num_reads,
            annealing_time=cfg.annealing_time,
            use_hybrid=cfg.use_hybrid,
        )

        # Decode solution
        if result.optimal_bitstring:
            solution_dict = {i: int(b) for i, b in enumerate(result.optimal_bitstring)}
            decoded = problem.decode_solution(solution_dict)
            result.raw_result = {
                "decoded_solution": decoded,
                "problem_type": type(problem).__name__,
            }

        self._history.append(result)
        return result

    async def solve_qubo(
        self,
        qubo: Dict[tuple, float],
        **kwargs,
    ) -> JobResult:
        """
        Convenience method for QUBO problems.

        Args:
            qubo: QUBO dictionary {(i,j): coefficient}
            **kwargs: Additional config parameters

        Returns:
            JobResult with solution
        """
        problem = QUBOProblem(qubo)

        config = AnnealingConfig(
            num_reads=kwargs.get("num_reads", self.config.num_reads),
            annealing_time=kwargs.get("annealing_time", self.config.annealing_time),
            use_hybrid=kwargs.get("use_hybrid", self.config.use_hybrid),
        )

        return await self.solve(problem, config)

    async def solve_maxcut(
        self,
        edges: List[tuple],
        weights: Optional[List[float]] = None,
        **kwargs,
    ) -> JobResult:
        """
        Solve MaxCut problem.

        Args:
            edges: List of edges
            weights: Optional edge weights

        Returns:
            JobResult with cut solution
        """
        problem = QUBOProblem.max_cut(edges, weights)
        return await self.solve(problem)

    async def solve_knapsack(
        self,
        values: List[float],
        weights: List[float],
        capacity: int,
        penalty: float = 100.0,
        **kwargs,
    ) -> JobResult:
        """
        Solve 0-1 knapsack problem.

        Args:
            values: Item values
            weights: Item weights
            capacity: Knapsack capacity
            penalty: Constraint penalty weight

        Returns:
            JobResult with selected items
        """
        problem = QUBOProblem.knapsack(values, weights, capacity, penalty)
        result = await self.solve(problem)

        # Add knapsack-specific decoding
        if result.optimal_bitstring:
            selected = [i for i, b in enumerate(result.optimal_bitstring) if b == "1"]
            total_value = sum(values[i] for i in selected)
            total_weight = sum(weights[i] for i in selected)

            result.raw_result["knapsack_solution"] = {
                "selected_items": selected,
                "total_value": total_value,
                "total_weight": total_weight,
                "capacity": capacity,
                "feasible": total_weight <= capacity,
            }

        return result

    def simulated_annealing(
        self,
        problem: AnnealingProblem,
        num_reads: int = 1000,
        num_sweeps: int = 1000,
        beta_range: tuple = (0.1, 10.0),
    ) -> Dict[str, Any]:
        """
        Classical simulated annealing for testing/comparison.

        Args:
            problem: Problem instance
            num_reads: Number of independent runs
            num_sweeps: Number of Monte Carlo sweeps per run
            beta_range: (initial, final) inverse temperature

        Returns:
            Dictionary with solutions and statistics
        """
        qubo = problem.to_qubo()
        n = problem.num_variables

        # Extract linear and quadratic terms
        linear = {}
        quadratic = {}
        for (i, j), coef in qubo.items():
            if i == j:
                linear[i] = coef
            else:
                quadratic[(min(i, j), max(i, j))] = coef

        beta_schedule = np.linspace(beta_range[0], beta_range[1], num_sweeps)

        best_solution = None
        best_energy = float("inf")
        all_solutions = []

        for _ in range(num_reads):
            # Random initial state
            state = np.random.randint(0, 2, n)

            # Calculate initial energy
            energy = sum(linear.get(i, 0) * state[i] for i in range(n))
            for (i, j), coef in quadratic.items():
                energy += coef * state[i] * state[j]

            for beta in beta_schedule:
                # Random single spin flip
                i = np.random.randint(n)

                # Calculate energy change
                delta_e = -2 * state[i] * linear.get(i, 0) + linear.get(i, 0)
                for (a, b), coef in quadratic.items():
                    if a == i:
                        delta_e += coef * (1 - 2 * state[i]) * state[b]
                    elif b == i:
                        delta_e += coef * state[a] * (1 - 2 * state[i])

                # Metropolis acceptance
                if delta_e < 0 or np.random.random() < np.exp(-beta * delta_e):
                    state[i] = 1 - state[i]
                    energy += delta_e

            solution_dict = {i: int(state[i]) for i in range(n)}
            all_solutions.append((solution_dict, energy))

            if energy < best_energy:
                best_energy = energy
                best_solution = solution_dict.copy()

        # Decode best solution
        decoded = problem.decode_solution(best_solution)

        return {
            "best_solution": best_solution,
            "best_energy": best_energy,
            "decoded": decoded,
            "num_reads": num_reads,
            "all_energies": [e for _, e in all_solutions],
        }

    def get_history(self) -> List[JobResult]:
        """Get execution history."""
        return self._history

    def clear_history(self) -> None:
        """Clear execution history."""
        self._history = []

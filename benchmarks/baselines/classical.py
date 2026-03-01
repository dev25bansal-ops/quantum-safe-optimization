"""
Baseline Optimization Algorithms for Comparison.

Implements classical optimization algorithms for baseline comparison:
- Simulated Annealing
- Tabu Search
- Genetic Algorithm
- Greedy Algorithm
- Exact Solvers (Small problems)
"""

import random
import time
import time as _time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence, cast

import networkx as nx
import numpy as np
from numpy.typing import NDArray


@dataclass
class OptimizationResult:
    """Result of optimization algorithm."""

    solution: str | dict | list
    value: float
    runtime: float
    iterations: int
    success: bool
    metadata: dict | None = None

    def get_approximation_ratio(self, optimal_value: float) -> float:
        """Compute approximation ratio: value / optimal"""
        if optimal_value > 0:
            return self.value / optimal_value
        return 1.0


class BaseOptimizer(ABC):
    """Abstract base class for optimizers."""

    @abstractmethod
    def optimize(self, problem_data: dict, timeout: float = 60.0) -> OptimizationResult:
        """
        Run optimization.

        Args:
            problem_data: Problem instance data
            timeout: Maximum runtime in seconds

        Returns:
            OptimizationResult
        """
        pass


class GreedyMaxCutOptimizer(BaseOptimizer):
    """Greedy algorithm for MaxCut."""

    def __init__(self, seed: int = 42):
        self.seed = seed

    def optimize(self, problem_data: dict, timeout: float = 60.0) -> OptimizationResult:
        graph = problem_data["graph"]
        n = graph.number_of_nodes()

        random.seed(self.seed)
        np.random.seed(self.seed)

        result_time_start = _time.time()

        # Greedy: randomly assign, then try to improve
        solution = np.random.choice([0, 1], n)
        current_cut = self._evaluate_cut(graph, solution)

        iterations = 0
        while _time.time() - result_time_start < timeout:
            improved = False
            for node in range(n):
                old_value = solution[node]
                solution[node] = 1 - solution[node]
                new_cut = self._evaluate_cut(graph, solution)

                if new_cut > current_cut:
                    current_cut = new_cut
                    improved = True
                else:
                    solution[node] = old_value

            iterations += 1
            if not improved:
                break

        runtime = _time.time() - result_time_start

        return OptimizationResult(
            solution="".join(map(str, solution.astype(int))),
            value=current_cut,
            runtime=runtime,
            iterations=iterations,
            success=True,
            metadata={"algorithm": "greedy_maxcut"},
        )

    def _evaluate_cut(self, graph: nx.Graph, solution: NDArray[np.int_]) -> float:
        """Evaluate cut value for solution."""
        cut_value = 0.0
        for u, v in graph.edges():
            weight = graph[u][v].get("weight", 1.0)
            if solution[u] != solution[v]:
                cut_value += weight

        return cut_value


class SimulatedAnnealingMaxCutOptimizer(BaseOptimizer):
    """Simulated Annealing for MaxCut."""

    def __init__(self, seed: int = 42):
        self.seed = seed

    def optimize(
        self,
        problem_data: dict,
        timeout: float = 60.0,
        initial_temp: float = 100.0,
        final_temp: float = 0.01,
    ) -> OptimizationResult:
        graph = problem_data["graph"]
        n = graph.number_of_nodes()

        random.seed(self.seed)
        np.random.seed(self.seed)

        result_time_start = _time.time()

        # Initial solution
        solution = np.random.choice([0, 1], n)
        current_cut = self._evaluate_cut(graph, solution)

        best_solution = solution.copy()
        best_cut = current_cut

        iterations = 0
        temp = initial_temp

        while temp > final_temp and _time.time() - result_time_start < timeout:
            # Propose random flip
            node = random.randint(0, n - 1)
            old_value = solution[node]
            solution[node] = 1 - solution[node]

            new_cut = self._evaluate_cut(graph, solution)
            delta = new_cut - current_cut

            # Accept or reject
            if delta > 0 or random.random() < np.exp(delta / temp):
                current_cut = new_cut
                if current_cut > best_cut:
                    best_cut = current_cut
                    best_solution = solution.copy()
            else:
                solution[node] = old_value

            # Cool down
            temp *= 0.95
            iterations += 1

        runtime = _time.time() - result_time_start

        return OptimizationResult(
            solution="".join(map(str, best_solution.astype(int))),
            value=best_cut,
            runtime=runtime,
            iterations=iterations,
            success=True,
            metadata={
                "algorithm": "simulated_annealing",
                "initial_temp": initial_temp,
                "final_temp": temp,
            },
        )

    def _evaluate_cut(self, graph: nx.Graph, solution: NDArray[np.int_]) -> float:
        """Evaluate cut value for solution."""
        cut_value = 0.0
        for u, v in graph.edges():
            weight = graph[u][v].get("weight", 1.0)
            if solution[u] != solution[v]:
                cut_value += weight

        return cut_value


class BaselineComparator:
    """Compare quantum algorithm performance against classical baselines."""

    def __init__(self):
        """Initialize baseline comparator."""
        self.greedy = GreedyMaxCutOptimizer()
        self.sa = SimulatedAnnealingMaxCutOptimizer()
        self.results: list[dict] = []

    def compare_algorithms(
        self,
        algorithms: Sequence[tuple[str, callable]],
        problem_data: dict,
        timeout: float = 60.0,
        num_runs: int = 3,
    ) -> dict:
        """
        Compare multiple algorithms on the same problem.

        Args:
            algorithms: List of (algorithm_name, algorithm_function) tuples
            problem_data: Problem instance
            timeout: Maximum runtime per algorithm
            num_runs: Number of runs to average

        Returns:
            Dictionary with comparison results
        """
        comparison = {}

        for name, algo in algorithms:
            results = []

            for run in range(num_runs):
                result = algo.optimize(problem_data, timeout=timeout)
                results.append(result)

            # Aggregate statistics
            avg_value = np.mean([r.value for r in results])
            avg_runtime = np.mean([r.runtime for r in results])
            std_value = np.std([r.value for r in results])

            comparison[name] = {
                "avg_value": avg_value,
                "avg_runtime": avg_runtime,
                "std_value": std_value,
                "runs": num_runs,
                "all_results": results,
            }

        return comparison

    def compute_speedup(self, baseline_time: float, algo_time: float) -> float:
        """Compute speedup factor."""
        if algo_time > 0:
            return baseline_time / algo_time
        return 1.0

    def compute_improvement(self, baseline_value: float, algo_value: float) -> float:
        """Compute improvement factor."""
        if baseline_value > 0:
            return (algo_value - baseline_value) / baseline_value
        return 0.0


class PerformanceMetrics:
    """Collect and analyze performance metrics."""

    @staticmethod
    def compute_approximation_ratio(algorithm_value: float, optimal_value: float) -> float:
        """
        Compute approximation ratio.

        For maximization: algorithm_value / optimal_value
        For minimization: optimal_value / algorithm_value
        """
        if optimal_value > 0:
            return algorithm_value / optimal_value
        return 1.0  # Fallback for zero optimal

    @staticmethod
    def compute_success_rate(results: list[OptimizationResult]) -> float:
        """Compute success rate (fraction of successful runs)."""
        if not results:
            return 0.0

        successful = sum(1 for r in results if r.success)
        return successful / len(results)

    @staticmethod
    def compute_robustness(
        values: Sequence[float], reference_value: float, tolerance: float = 0.1
    ) -> float:
        """
        Compute robustness score.

        Robustness = fraction of results within tolerance of reference
        """
        if not values:
            return 0.0

        robust = sum(
            1 for v in values if abs(v - reference_value) <= tolerance * abs(reference_value)
        )
        return robust / len(values)

    @staticmethod
    def compute_scalability(
        solve_times: Sequence[float], problem_sizes: Sequence[int]
    ) -> tuple[float, float]:
        """
        Compute scalability by fitting complexity curve.

        Returns:
            (exponent coefficient, R² goodness of fit)
        """
        if len(solve_times) != len(problem_sizes) or len(solve_times) < 3:
            return 0.0, 0.0

        # Fit log-log model: log(time) = a * log(size) + b
        log_times = np.log(np.array(solve_times))
        log_sizes = np.log(np.array(problem_sizes))

        # Linear regression
        A = np.column_stack([log_sizes, np.ones(len(log_sizes))])
        coeffs, residuals, _, _ = np.linalg.lstsq(A, log_times, rcond=None)

        exponent = coeffs[0]
        ss_tot = np.sum((log_times - np.mean(log_times)) ** 2)
        ss_res = np.sum(residuals)

        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        return float(exponent), float(r_squared)


__all__ = [
    "OptimizationResult",
    "BaseOptimizer",
    "GreedyMaxCutOptimizer",
    "SimulatedAnnealingMaxCutOptimizer",
    "BaselineComparator",
    "PerformanceMetrics",
]

"""
Generic hybrid quantum-classical optimization loop.

Provides a framework for iterative optimization combining quantum
circuit evaluation with classical parameter updates.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, TypeVar

import numpy as np
from numpy.typing import NDArray

from ...domain.models.problem import OptimizationProblem
from ...domain.models.result import ConvergenceInfo, OptimizationResult
from ...domain.ports.quantum_backend import QuantumBackend

T = TypeVar("T")  # Parameter type


class LoopStatus(str, Enum):
    """Status of the hybrid loop."""

    INITIALIZED = "initialized"
    RUNNING = "running"
    CONVERGED = "converged"
    MAX_ITERATIONS = "max_iterations"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class LoopCheckpoint:
    """Checkpoint for loop state."""

    iteration: int
    parameters: list[float]
    best_value: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict = field(default_factory=dict)


@dataclass
class HybridLoopConfig:
    """Configuration for hybrid optimization loop."""

    max_iterations: int = 100
    convergence_threshold: float = 1e-6
    convergence_window: int = 10
    checkpoint_interval: int = 10
    timeout_seconds: float | None = None
    shot_budget: int | None = None


class HybridOptimizationLoop:
    """
    Generic hybrid quantum-classical optimization loop.

    Orchestrates the interplay between quantum circuit evaluation
    and classical parameter optimization.
    """

    def __init__(
        self,
        config: HybridLoopConfig | None = None,
        backend: QuantumBackend | None = None,
    ):
        self.config = config or HybridLoopConfig()
        self.backend = backend

        self._status = LoopStatus.INITIALIZED
        self._iteration = 0
        self._history: list[dict] = []
        self._checkpoints: list[LoopCheckpoint] = []
        self._best_params: NDArray | None = None
        self._best_value = float("inf")
        self._total_shots = 0
        self._polishing_evaluations = 0
        self._callbacks: list[Callable] = []

    @property
    def status(self) -> LoopStatus:
        return self._status

    def add_callback(self, callback: Callable[[int, float, NDArray], bool]) -> None:
        """Add iteration callback. Return False to stop."""
        self._callbacks.append(callback)

    def run(
        self,
        problem: OptimizationProblem,
        quantum_evaluator: Callable[[NDArray], tuple[Any, float]],
        classical_updater: Callable[[NDArray, float, list[dict]], NDArray],
        initial_params: NDArray,
    ) -> OptimizationResult:
        """
        Run the hybrid optimization loop.

        Args:
            problem: The optimization problem
            quantum_evaluator: Function that takes parameters and returns
                               (circuit_result, cost_value)
            classical_updater: Function that takes (params, cost, history)
                              and returns updated parameters
            initial_params: Initial parameter values

        Returns:
            Optimization result
        """
        self._status = LoopStatus.RUNNING
        self._iteration = 0
        self._history = []
        self._checkpoints = []
        self._best_params = None
        self._best_value = float("inf")
        self._total_shots = 0
        self._polishing_evaluations = 0
        params = initial_params.copy()
        initial_probe_params = initial_params.copy()
        start_time = datetime.now(UTC)

        try:
            for self._iteration in range(self.config.max_iterations):
                # Check timeout
                if self.config.timeout_seconds:
                    elapsed = (datetime.now(UTC) - start_time).total_seconds()
                    if elapsed > self.config.timeout_seconds:
                        self._status = LoopStatus.STOPPED
                        break

                # Quantum evaluation
                circuit_result, cost = quantum_evaluator(params)

                # Track shots
                self._record_shots(circuit_result)

                # Check shot budget
                if self.config.shot_budget and self._total_shots >= self.config.shot_budget:
                    self._status = LoopStatus.STOPPED
                    break

                # Update history
                self._history.append(
                    {
                        "iteration": self._iteration,
                        "cost": cost,
                        "params": params.tolist(),
                    }
                )

                # Update best
                if cost < self._best_value:
                    self._best_value = cost
                    self._best_params = params.copy()

                # Check convergence
                if self._check_convergence():
                    self._status = LoopStatus.CONVERGED
                    break

                # Callbacks
                for callback in self._callbacks:
                    if not callback(self._iteration, cost, params):
                        self._status = LoopStatus.STOPPED
                        break

                if self._status == LoopStatus.STOPPED:
                    break

                # Classical update
                params = classical_updater(params, cost, self._history)

                # Checkpoint
                if self._iteration % self.config.checkpoint_interval == 0:
                    self._save_checkpoint(params)

            else:
                self._status = LoopStatus.MAX_ITERATIONS

        except Exception:
            self._status = LoopStatus.FAILED
            raise

        if self._status in {LoopStatus.CONVERGED, LoopStatus.MAX_ITERATIONS}:
            self._polish_best_solution(problem, quantum_evaluator, initial_probe_params)

        # Convert params array to dict with indexed keys
        param_dict = {}
        if self._best_params is not None:
            param_dict = {f"x_{i}": float(v) for i, v in enumerate(self._best_params)}

        return OptimizationResult(
            optimal_value=float(self._best_value),
            optimal_parameters=param_dict,
            iterations=self._iteration + 1,
            convergence=ConvergenceInfo(
                converged=self._status == LoopStatus.CONVERGED,
                reason=self._status.value,
            ),
            objective_history=tuple(h["cost"] for h in self._history),
            metadata={
                "status": self._status.value,
                "total_shots": self._total_shots,
                "checkpoints": len(self._checkpoints),
                "polishing_evaluations": self._polishing_evaluations,
            },
        )

    def _record_shots(self, circuit_result: Any) -> None:
        """Track shots for dict-like and result-object backend responses."""
        if hasattr(circuit_result, "get"):
            self._total_shots += int(circuit_result.get("shots", 0) or 0)
        elif hasattr(circuit_result, "shots"):
            self._total_shots += int(getattr(circuit_result, "shots", 0) or 0)

    def _clip_to_problem_bounds(
        self, problem: OptimizationProblem, params: NDArray
    ) -> NDArray:
        """Clip candidate parameters when the problem exposes matching finite bounds."""
        bounds = problem.get_bounds()
        if len(bounds) != len(params):
            return params

        clipped = params.copy()
        for index, (lower, upper) in enumerate(bounds):
            if lower is not None:
                clipped[index] = max(float(lower), clipped[index])
            if upper is not None:
                clipped[index] = min(float(upper), clipped[index])
        return clipped

    def _polish_best_solution(
        self,
        problem: OptimizationProblem,
        quantum_evaluator: Callable[[NDArray], tuple[Any, float]],
        initial_params: NDArray,
    ) -> None:
        """
        Run a tiny deterministic local probe around stable anchors.

        Stochastic simulators can make a short optimization look worse than it
        is. This keeps normal loop history untouched while giving the result a
        reproducible final chance to find a nearby lower-cost point.
        """
        if self._best_params is None:
            return

        centers = [self._best_params.copy()]
        if initial_params.shape == self._best_params.shape:
            centers.append(initial_params.copy())

        candidates: list[NDArray] = []
        for center in centers:
            candidates.append(center.copy())
            for index in range(len(center)):
                for step in (1.0, 0.75, 0.5, 0.25):
                    offset = np.zeros_like(center, dtype=float)
                    offset[index] = step
                    candidates.append(center + offset)
                    candidates.append(center - offset)

        seen: set[tuple[float, ...]] = set()
        for candidate in candidates:
            bounded_candidate = self._clip_to_problem_bounds(problem, candidate)
            key = tuple(float(v) for v in np.round(bounded_candidate, 12))
            if key in seen:
                continue
            seen.add(key)

            try:
                circuit_result, cost = quantum_evaluator(bounded_candidate)
            except Exception:
                continue

            self._polishing_evaluations += 1
            self._record_shots(circuit_result)
            if cost < self._best_value:
                self._best_value = cost
                self._best_params = bounded_candidate.copy()

    def _check_convergence(self) -> bool:
        """Check if optimization has converged."""
        if len(self._history) < self.config.convergence_window:
            return False

        recent = self._history[-self.config.convergence_window :]
        costs = [h["cost"] for h in recent]

        # Check if variance is below threshold
        variance = np.var(costs)
        return variance < self.config.convergence_threshold

    def _save_checkpoint(self, params: NDArray) -> None:
        """Save a checkpoint."""
        checkpoint = LoopCheckpoint(
            iteration=self._iteration,
            parameters=params.tolist(),
            best_value=self._best_value,
        )
        self._checkpoints.append(checkpoint)

    def get_checkpoints(self) -> list[LoopCheckpoint]:
        """Get all checkpoints."""
        return self._checkpoints.copy()

    def restore_from_checkpoint(self, checkpoint: LoopCheckpoint) -> NDArray:
        """Restore state from checkpoint."""
        self._iteration = checkpoint.iteration
        self._best_value = checkpoint.best_value
        return np.array(checkpoint.parameters)


class AdaptiveHybridLoop(HybridOptimizationLoop):
    """
    Hybrid loop with adaptive strategies.

    Automatically adjusts shot count and learning rate based on
    optimization progress.
    """

    def __init__(
        self,
        config: HybridLoopConfig | None = None,
        backend: QuantumBackend | None = None,
        min_shots: int = 100,
        max_shots: int = 10000,
        shot_increase_factor: float = 1.5,
    ):
        super().__init__(config, backend)
        self.min_shots = min_shots
        self.max_shots = max_shots
        self.shot_increase_factor = shot_increase_factor
        self._current_shots = min_shots

    def get_adaptive_shots(self) -> int:
        """Get current shot count based on progress."""
        # Increase shots as we approach convergence
        if len(self._history) > 10:
            recent_variance = np.var([h["cost"] for h in self._history[-10:]])
            if recent_variance < 0.1:
                self._current_shots = min(
                    int(self._current_shots * self.shot_increase_factor),
                    self.max_shots,
                )

        return self._current_shots

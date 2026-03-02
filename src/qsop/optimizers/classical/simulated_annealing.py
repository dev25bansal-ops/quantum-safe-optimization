"""
Simulated Annealing optimizer.

A probabilistic optimization technique inspired by metallurgical annealing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy.typing import NDArray

from ...domain.models.problem import OptimizationProblem
from ...domain.models.result import ConvergenceInfo, OptimizationResult
from .base import BaseClassicalOptimizer, OptimizationHistory


class CoolingSchedule(str, Enum):
    """Temperature cooling schedules."""

    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    LOGARITHMIC = "logarithmic"
    ADAPTIVE = "adaptive"
    BOLTZMANN = "boltzmann"
    CAUCHY = "cauchy"


@dataclass
class SimulatedAnnealingConfig:
    """Configuration for Simulated Annealing."""

    initial_temperature: float = 100.0
    final_temperature: float = 1e-8
    max_iterations: int = 10000
    cooling_schedule: CoolingSchedule = CoolingSchedule.EXPONENTIAL
    cooling_rate: float = 0.995  # For exponential
    iterations_per_temperature: int = 10
    neighborhood_scale: float = 0.1  # Step size as fraction of range
    reheating_enabled: bool = False
    reheating_threshold: int = 500  # Iterations without improvement
    reheating_factor: float = 2.0
    random_seed: int | None = None


class SimulatedAnnealing(BaseClassicalOptimizer):
    """
    Simulated Annealing optimizer.

    Uses probabilistic acceptance of worse solutions to escape local minima,
    with the probability decreasing as temperature decreases.
    """

    name = "simulated_annealing"

    def __init__(self, config: SimulatedAnnealingConfig | None = None):
        self.config = config or SimulatedAnnealingConfig()
        self._rng = np.random.default_rng(self.config.random_seed)

    def supports(self, problem: OptimizationProblem) -> bool:
        return True

    def optimize(
        self,
        problem: OptimizationProblem,
        *,
        context: dict | None = None,
    ) -> OptimizationResult:
        context = context or {}
        bounds = problem.get_bounds_array()
        len(problem.variables)
        lower, upper = bounds[:, 0], bounds[:, 1]

        # Initialize
        current = self._rng.uniform(lower, upper)
        current_energy = problem.evaluate(current)

        best = current.copy()
        best_energy = current_energy

        temperature = self.config.initial_temperature
        step_sizes = self.config.neighborhood_scale * (upper - lower)

        history = OptimizationHistory()
        history.record(best_energy, best.tolist())

        iterations_without_improvement = 0
        total_iterations = 0

        while (
            temperature > self.config.final_temperature
            and total_iterations < self.config.max_iterations
        ):
            for _ in range(self.config.iterations_per_temperature):
                # Generate neighbor
                neighbor = self._generate_neighbor(current, step_sizes, lower, upper)
                neighbor_energy = problem.evaluate(neighbor)

                # Metropolis criterion
                delta_energy = neighbor_energy - current_energy

                if delta_energy < 0 or self._rng.random() < np.exp(-delta_energy / temperature):
                    current = neighbor
                    current_energy = neighbor_energy

                    if current_energy < best_energy:
                        best = current.copy()
                        best_energy = current_energy
                        iterations_without_improvement = 0
                    else:
                        iterations_without_improvement += 1
                else:
                    iterations_without_improvement += 1

                total_iterations += 1

                if total_iterations >= self.config.max_iterations:
                    break

            # Cool down
            temperature = self._cool(temperature, total_iterations)

            # Reheating
            if (
                self.config.reheating_enabled
                and iterations_without_improvement > self.config.reheating_threshold
            ):
                temperature *= self.config.reheating_factor
                iterations_without_improvement = 0

            history.record(best_energy, best.tolist())

            if context.get("callback"):
                if not context["callback"](total_iterations, best_energy, best):
                    break

        param_dict = {problem.variables[i].name: float(best[i]) for i in range(len(best))}
        return OptimizationResult(
            optimal_value=float(best_energy),
            optimal_parameters=param_dict,
            iterations=total_iterations,
            convergence=ConvergenceInfo(
                converged=temperature <= self.config.final_temperature,
                reason="completed"
                if temperature <= self.config.final_temperature
                else "max_iterations",
            ),
            metadata={
                "algorithm": self.name,
                "final_temperature": temperature,
            },
        )

    def _generate_neighbor(
        self,
        current: NDArray,
        step_sizes: NDArray,
        lower: NDArray,
        upper: NDArray,
    ) -> NDArray:
        """Generate a neighboring solution."""
        perturbation = self._rng.normal(0, step_sizes)
        neighbor = current + perturbation
        return np.clip(neighbor, lower, upper)

    def _cool(self, temperature: float, iteration: int) -> float:
        """Apply cooling schedule."""
        schedule = self.config.cooling_schedule

        if schedule == CoolingSchedule.EXPONENTIAL:
            return temperature * self.config.cooling_rate

        elif schedule == CoolingSchedule.LINEAR:
            total = self.config.max_iterations / self.config.iterations_per_temperature
            delta = (self.config.initial_temperature - self.config.final_temperature) / total
            return max(temperature - delta, self.config.final_temperature)

        elif schedule == CoolingSchedule.LOGARITHMIC:
            return self.config.initial_temperature / (1 + np.log(1 + iteration))

        elif schedule == CoolingSchedule.BOLTZMANN:
            return self.config.initial_temperature / (1 + iteration)

        elif schedule == CoolingSchedule.CAUCHY:
            return self.config.initial_temperature / (1 + iteration)

        elif schedule == CoolingSchedule.ADAPTIVE:
            # Simple adaptive: slower cooling when improving
            return temperature * self.config.cooling_rate

        return temperature * self.config.cooling_rate


@dataclass
class AdaptiveSimulatedAnnealingConfig:
    """Configuration for Adaptive Simulated Annealing."""

    initial_temperature: float = 100.0
    final_temperature: float = 1e-8
    max_iterations: int = 10000
    acceptance_rate_target: float = 0.5
    temperature_adjustment_rate: float = 0.1
    random_seed: int | None = None


class AdaptiveSimulatedAnnealing(BaseClassicalOptimizer):
    """
    Adaptive Simulated Annealing.

    Automatically adjusts temperature and step sizes based on
    acceptance rate to maintain exploration/exploitation balance.
    """

    name = "adaptive_simulated_annealing"

    def __init__(self, config: AdaptiveSimulatedAnnealingConfig | None = None):
        self.config = config or AdaptiveSimulatedAnnealingConfig()
        self._rng = np.random.default_rng(self.config.random_seed)

    def supports(self, problem: OptimizationProblem) -> bool:
        return True

    def optimize(
        self,
        problem: OptimizationProblem,
        *,
        context: dict | None = None,
    ) -> OptimizationResult:
        context = context or {}
        bounds = problem.get_bounds_array()
        len(problem.variables)
        lower, upper = bounds[:, 0], bounds[:, 1]

        # Initialize
        current = self._rng.uniform(lower, upper)
        current_energy = problem.evaluate(current)

        best = current.copy()
        best_energy = current_energy

        temperature = self.config.initial_temperature
        step_sizes = 0.1 * (upper - lower)

        history = OptimizationHistory()
        history.record(best_energy, best.tolist())

        # Tracking for adaptation
        window_size = 100
        accepts = 0
        attempts = 0

        for iteration in range(self.config.max_iterations):
            if temperature < self.config.final_temperature:
                break

            # Generate neighbor
            perturbation = self._rng.normal(0, step_sizes)
            neighbor = np.clip(current + perturbation, lower, upper)
            neighbor_energy = problem.evaluate(neighbor)

            delta = neighbor_energy - current_energy
            attempts += 1

            # Acceptance
            if delta < 0 or self._rng.random() < np.exp(-delta / temperature):
                current = neighbor
                current_energy = neighbor_energy
                accepts += 1

                if current_energy < best_energy:
                    best = current.copy()
                    best_energy = current_energy

            # Adapt temperature and step sizes
            if attempts >= window_size:
                acceptance_rate = accepts / attempts

                # Adjust temperature
                if acceptance_rate > self.config.acceptance_rate_target:
                    temperature *= 1 - self.config.temperature_adjustment_rate
                else:
                    temperature *= 1 + self.config.temperature_adjustment_rate

                # Adjust step sizes
                if acceptance_rate > 0.6:
                    step_sizes *= 1.1
                elif acceptance_rate < 0.4:
                    step_sizes *= 0.9

                step_sizes = np.clip(step_sizes, 0.001 * (upper - lower), 0.5 * (upper - lower))

                accepts = 0
                attempts = 0

            if iteration % 100 == 0:
                history.record(best_energy, best.tolist())

            if context.get("callback"):
                if not context["callback"](iteration, best_energy, best):
                    break

        param_dict = {problem.variables[i].name: float(best[i]) for i in range(len(best))}
        return OptimizationResult(
            optimal_value=float(best_energy),
            optimal_parameters=param_dict,
            iterations=iteration + 1,
            convergence=ConvergenceInfo(
                converged=temperature <= self.config.final_temperature,
                reason="completed"
                if temperature <= self.config.final_temperature
                else "max_iterations",
            ),
            metadata={"algorithm": self.name},
        )

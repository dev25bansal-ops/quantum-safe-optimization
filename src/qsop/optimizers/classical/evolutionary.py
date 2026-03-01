"""
Evolutionary optimization algorithms.

Includes Genetic Algorithm, Differential Evolution, and Particle Swarm Optimization.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy.typing import NDArray

from ...domain.models.problem import OptimizationProblem
from ...domain.models.result import ConvergenceInfo, OptimizationResult
from .base import BaseClassicalOptimizer, OptimizationHistory


class SelectionMethod(str, Enum):
    """Selection methods for genetic algorithms."""

    TOURNAMENT = "tournament"
    ROULETTE = "roulette"
    RANK = "rank"
    ELITIST = "elitist"


class CrossoverMethod(str, Enum):
    """Crossover methods for genetic algorithms."""

    SINGLE_POINT = "single_point"
    TWO_POINT = "two_point"
    UNIFORM = "uniform"
    BLEND = "blend"
    SBX = "sbx"  # Simulated Binary Crossover


class MutationMethod(str, Enum):
    """Mutation methods for genetic algorithms."""

    GAUSSIAN = "gaussian"
    UNIFORM = "uniform"
    POLYNOMIAL = "polynomial"
    BOUNDARY = "boundary"


@dataclass
class GeneticAlgorithmConfig:
    """Configuration for Genetic Algorithm."""

    population_size: int = 100
    generations: int = 200
    selection_method: SelectionMethod = SelectionMethod.TOURNAMENT
    tournament_size: int = 3
    crossover_method: CrossoverMethod = CrossoverMethod.SBX
    crossover_probability: float = 0.9
    mutation_method: MutationMethod = MutationMethod.POLYNOMIAL
    mutation_probability: float = 0.1
    elitism_count: int = 2
    eta_c: float = 20.0  # SBX distribution index
    eta_m: float = 20.0  # Polynomial mutation index


class GeneticAlgorithm(BaseClassicalOptimizer):
    """
    Genetic Algorithm optimizer.

    Uses evolutionary principles: selection, crossover, and mutation
    to evolve a population toward optimal solutions.
    """

    name = "genetic_algorithm"

    def __init__(self, config: GeneticAlgorithmConfig | None = None):
        self.config = config or GeneticAlgorithmConfig()
        self._rng = np.random.default_rng()

    def supports(self, problem: OptimizationProblem) -> bool:
        return True  # GA works for most problems

    def optimize(
        self,
        problem: OptimizationProblem,
        *,
        context: dict | None = None,
    ) -> OptimizationResult:
        context = context or {}
        bounds = problem.get_bounds_array()
        n_vars = len(problem.variables)

        # Initialize population
        population = self._initialize_population(bounds, n_vars)
        fitness = np.array([problem.evaluate(ind) for ind in population])

        history = OptimizationHistory()
        best_idx = np.argmin(fitness)
        best_solution = population[best_idx].copy()
        best_fitness = fitness[best_idx]

        history.record(best_fitness, best_solution.tolist())

        for gen in range(self.config.generations):
            # Selection
            parents = self._select(population, fitness)

            # Crossover
            offspring = self._crossover(parents, bounds)

            # Mutation
            offspring = self._mutate(offspring, bounds)

            # Evaluate offspring
            offspring_fitness = np.array([problem.evaluate(ind) for ind in offspring])

            # Elitism: keep best individuals
            elite_indices = np.argsort(fitness)[: self.config.elitism_count]
            elite = population[elite_indices]
            elite_fitness = fitness[elite_indices]

            # Combine and select next generation
            combined_pop = np.vstack([elite, offspring])
            combined_fitness = np.concatenate([elite_fitness, offspring_fitness])

            # Select best for next generation
            best_indices = np.argsort(combined_fitness)[: self.config.population_size]
            population = combined_pop[best_indices]
            fitness = combined_fitness[best_indices]

            # Update best
            if fitness[0] < best_fitness:
                best_fitness = fitness[0]
                best_solution = population[0].copy()

            history.record(best_fitness, best_solution.tolist())

            # Check convergence via callback
            if context.get("callback"):
                if not context["callback"](gen, best_fitness, best_solution):
                    break

        param_dict = {
            problem.variables[i].name: float(best_solution[i]) for i in range(len(best_solution))
        }
        return OptimizationResult(
            optimal_value=float(best_fitness),
            optimal_parameters=param_dict,
            iterations=gen + 1,
            convergence=ConvergenceInfo(converged=True, reason="completed"),
            metadata={"algorithm": self.name},
        )

    def _initialize_population(
        self,
        bounds: NDArray,
        n_vars: int,
    ) -> NDArray:
        """Initialize random population within bounds."""
        lower = bounds[:, 0]
        upper = bounds[:, 1]
        return self._rng.uniform(
            lower,
            upper,
            size=(self.config.population_size, n_vars),
        )

    def _select(
        self,
        population: NDArray,
        fitness: NDArray,
    ) -> NDArray:
        """Select parents for reproduction."""
        n_parents = self.config.population_size

        if self.config.selection_method == SelectionMethod.TOURNAMENT:
            return self._tournament_selection(population, fitness, n_parents)
        elif self.config.selection_method == SelectionMethod.ROULETTE:
            return self._roulette_selection(population, fitness, n_parents)
        else:
            return self._tournament_selection(population, fitness, n_parents)

    def _tournament_selection(
        self,
        population: NDArray,
        fitness: NDArray,
        n_select: int,
    ) -> NDArray:
        """Tournament selection."""
        selected = []
        for _ in range(n_select):
            candidates = self._rng.choice(
                len(population),
                size=self.config.tournament_size,
                replace=False,
            )
            winner = candidates[np.argmin(fitness[candidates])]
            selected.append(population[winner])
        return np.array(selected)

    def _roulette_selection(
        self,
        population: NDArray,
        fitness: NDArray,
        n_select: int,
    ) -> NDArray:
        """Roulette wheel selection (for minimization)."""
        # Transform fitness for minimization
        max_fit = np.max(fitness)
        adjusted = max_fit - fitness + 1e-10
        probs = adjusted / adjusted.sum()

        indices = self._rng.choice(len(population), size=n_select, p=probs)
        return population[indices]

    def _crossover(self, parents: NDArray, bounds: NDArray) -> NDArray:
        """Apply crossover to create offspring."""
        offspring = []
        n_pairs = len(parents) // 2

        for i in range(n_pairs):
            p1, p2 = parents[2 * i], parents[2 * i + 1]

            if self._rng.random() < self.config.crossover_probability:
                if self.config.crossover_method == CrossoverMethod.SBX:
                    c1, c2 = self._sbx_crossover(p1, p2, bounds)
                elif self.config.crossover_method == CrossoverMethod.UNIFORM:
                    c1, c2 = self._uniform_crossover(p1, p2)
                else:
                    c1, c2 = self._sbx_crossover(p1, p2, bounds)
            else:
                c1, c2 = p1.copy(), p2.copy()

            offspring.extend([c1, c2])

        return np.array(offspring)

    def _sbx_crossover(
        self,
        p1: NDArray,
        p2: NDArray,
        bounds: NDArray,
    ) -> tuple[NDArray, NDArray]:
        """Simulated Binary Crossover."""
        c1, c2 = p1.copy(), p2.copy()
        eta = self.config.eta_c

        for i in range(len(p1)):
            if self._rng.random() < 0.5:
                if abs(p1[i] - p2[i]) > 1e-14:
                    x1 = min(p1[i], p2[i])
                    x2 = max(p1[i], p2[i])
                    xl, xu = bounds[i]

                    rand = self._rng.random()
                    beta = 1.0 + (2.0 * (x1 - xl) / (x2 - x1))
                    alpha = 2.0 - beta ** (-(eta + 1))

                    if rand <= 1.0 / alpha:
                        betaq = (rand * alpha) ** (1.0 / (eta + 1))
                    else:
                        betaq = (1.0 / (2.0 - rand * alpha)) ** (1.0 / (eta + 1))

                    c1[i] = 0.5 * ((x1 + x2) - betaq * (x2 - x1))
                    c2[i] = 0.5 * ((x1 + x2) + betaq * (x2 - x1))

                    c1[i] = np.clip(c1[i], xl, xu)
                    c2[i] = np.clip(c2[i], xl, xu)

        return c1, c2

    def _uniform_crossover(
        self,
        p1: NDArray,
        p2: NDArray,
    ) -> tuple[NDArray, NDArray]:
        """Uniform crossover."""
        mask = self._rng.random(len(p1)) < 0.5
        c1 = np.where(mask, p1, p2)
        c2 = np.where(mask, p2, p1)
        return c1, c2

    def _mutate(self, offspring: NDArray, bounds: NDArray) -> NDArray:
        """Apply mutation to offspring."""
        for i in range(len(offspring)):
            if self._rng.random() < self.config.mutation_probability:
                if self.config.mutation_method == MutationMethod.POLYNOMIAL:
                    offspring[i] = self._polynomial_mutation(offspring[i], bounds)
                elif self.config.mutation_method == MutationMethod.GAUSSIAN:
                    offspring[i] = self._gaussian_mutation(offspring[i], bounds)
                else:
                    offspring[i] = self._polynomial_mutation(offspring[i], bounds)
        return offspring

    def _polynomial_mutation(self, x: NDArray, bounds: NDArray) -> NDArray:
        """Polynomial mutation."""
        eta = self.config.eta_m
        mutated = x.copy()

        for i in range(len(x)):
            if self._rng.random() < 1.0 / len(x):
                xl, xu = bounds[i]
                delta1 = (x[i] - xl) / (xu - xl)
                delta2 = (xu - x[i]) / (xu - xl)

                rand = self._rng.random()
                if rand < 0.5:
                    xy = 1.0 - delta1
                    val = 2.0 * rand + (1.0 - 2.0 * rand) * (xy ** (eta + 1))
                    deltaq = val ** (1.0 / (eta + 1)) - 1.0
                else:
                    xy = 1.0 - delta2
                    val = 2.0 * (1.0 - rand) + 2.0 * (rand - 0.5) * (xy ** (eta + 1))
                    deltaq = 1.0 - val ** (1.0 / (eta + 1))

                mutated[i] = x[i] + deltaq * (xu - xl)
                mutated[i] = np.clip(mutated[i], xl, xu)

        return mutated

    def _gaussian_mutation(self, x: NDArray, bounds: NDArray) -> NDArray:
        """Gaussian mutation."""
        mutated = x.copy()
        sigma = 0.1 * (bounds[:, 1] - bounds[:, 0])

        for i in range(len(x)):
            if self._rng.random() < 1.0 / len(x):
                mutated[i] += self._rng.normal(0, sigma[i])
                mutated[i] = np.clip(mutated[i], bounds[i, 0], bounds[i, 1])

        return mutated


@dataclass
class DifferentialEvolutionConfig:
    """Configuration for Differential Evolution."""

    population_size: int = 50
    generations: int = 200
    mutation_factor: float = 0.8  # F
    crossover_probability: float = 0.9  # CR
    strategy: str = "best1bin"  # DE strategy


class DifferentialEvolution(BaseClassicalOptimizer):
    """
    Differential Evolution optimizer.

    Uses vector differences for mutation, making it effective
    for continuous optimization problems.
    """

    name = "differential_evolution"

    def __init__(self, config: DifferentialEvolutionConfig | None = None):
        self.config = config or DifferentialEvolutionConfig()
        self._rng = np.random.default_rng()

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
        n_vars = len(problem.variables)

        # Initialize population
        lower, upper = bounds[:, 0], bounds[:, 1]
        population = self._rng.uniform(
            lower,
            upper,
            size=(self.config.population_size, n_vars),
        )
        fitness = np.array([problem.evaluate(ind) for ind in population])

        history = OptimizationHistory()
        best_idx = np.argmin(fitness)
        best = population[best_idx].copy()
        best_fitness = fitness[best_idx]

        history.record(best_fitness, best.tolist())

        for gen in range(self.config.generations):
            for i in range(self.config.population_size):
                # Mutation: DE/best/1
                candidates = [j for j in range(self.config.population_size) if j != i]
                r1, r2 = self._rng.choice(candidates, 2, replace=False)

                mutant = best + self.config.mutation_factor * (population[r1] - population[r2])
                mutant = np.clip(mutant, lower, upper)

                # Crossover (binomial)
                trial = population[i].copy()
                j_rand = self._rng.integers(n_vars)
                for j in range(n_vars):
                    if self._rng.random() < self.config.crossover_probability or j == j_rand:
                        trial[j] = mutant[j]

                # Selection
                trial_fitness = problem.evaluate(trial)
                if trial_fitness < fitness[i]:
                    population[i] = trial
                    fitness[i] = trial_fitness

                    if trial_fitness < best_fitness:
                        best = trial.copy()
                        best_fitness = trial_fitness

            history.record(best_fitness, best.tolist())

            if context.get("callback"):
                if not context["callback"](gen, best_fitness, best):
                    break

        param_dict = {problem.variables[i].name: float(best[i]) for i in range(len(best))}
        return OptimizationResult(
            optimal_value=float(best_fitness),
            optimal_parameters=param_dict,
            iterations=gen + 1,
            convergence=ConvergenceInfo(converged=True, reason="completed"),
            metadata={"algorithm": self.name},
        )


@dataclass
class ParticleSwarmConfig:
    """Configuration for Particle Swarm Optimization."""

    swarm_size: int = 50
    iterations: int = 200
    w: float = 0.7298  # Inertia weight
    c1: float = 1.49618  # Cognitive coefficient
    c2: float = 1.49618  # Social coefficient
    v_max_fraction: float = 0.2  # Max velocity as fraction of range


class ParticleSwarmOptimization(BaseClassicalOptimizer):
    """
    Particle Swarm Optimization.

    Simulates a swarm of particles moving through the search space,
    influenced by their own best position and the swarm's best position.
    """

    name = "particle_swarm"

    def __init__(self, config: ParticleSwarmConfig | None = None):
        self.config = config or ParticleSwarmConfig()
        self._rng = np.random.default_rng()

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
        n_vars = len(problem.variables)
        lower, upper = bounds[:, 0], bounds[:, 1]

        # Velocity limits
        v_max = self.config.v_max_fraction * (upper - lower)

        # Initialize swarm
        positions = self._rng.uniform(
            lower,
            upper,
            size=(self.config.swarm_size, n_vars),
        )
        velocities = self._rng.uniform(
            -v_max,
            v_max,
            size=(self.config.swarm_size, n_vars),
        )

        # Evaluate initial positions
        fitness = np.array([problem.evaluate(p) for p in positions])

        # Personal best
        p_best = positions.copy()
        p_best_fitness = fitness.copy()

        # Global best
        g_best_idx = np.argmin(fitness)
        g_best = positions[g_best_idx].copy()
        g_best_fitness = fitness[g_best_idx]

        history = OptimizationHistory()
        history.record(g_best_fitness, g_best.tolist())

        for it in range(self.config.iterations):
            r1 = self._rng.random((self.config.swarm_size, n_vars))
            r2 = self._rng.random((self.config.swarm_size, n_vars))

            # Update velocities
            cognitive = self.config.c1 * r1 * (p_best - positions)
            social = self.config.c2 * r2 * (g_best - positions)
            velocities = self.config.w * velocities + cognitive + social

            # Clamp velocities
            velocities = np.clip(velocities, -v_max, v_max)

            # Update positions
            positions = positions + velocities
            positions = np.clip(positions, lower, upper)

            # Evaluate
            fitness = np.array([problem.evaluate(p) for p in positions])

            # Update personal bests
            improved = fitness < p_best_fitness
            p_best[improved] = positions[improved]
            p_best_fitness[improved] = fitness[improved]

            # Update global best
            best_idx = np.argmin(p_best_fitness)
            if p_best_fitness[best_idx] < g_best_fitness:
                g_best = p_best[best_idx].copy()
                g_best_fitness = p_best_fitness[best_idx]

            history.record(g_best_fitness, g_best.tolist())

            if context.get("callback"):
                if not context["callback"](it, g_best_fitness, g_best):
                    break

        param_dict = {problem.variables[i].name: float(g_best[i]) for i in range(len(g_best))}
        return OptimizationResult(
            optimal_value=float(g_best_fitness),
            optimal_parameters=param_dict,
            iterations=it + 1,
            convergence=ConvergenceInfo(converged=True, reason="completed"),
            metadata={"algorithm": self.name},
        )

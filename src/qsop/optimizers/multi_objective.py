"""
Multi-Objective Optimization Framework.

Provides algorithms for optimizing multiple conflicting objectives simultaneously,
including Pareto front analysis and various MOEA (Multi-Objective Evolutionary Algorithm)
approaches integrated with quantum and classical optimization techniques.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
from numpy.typing import NDArray


class DominanceRelation(Enum):
    """Types of dominance relations."""

    DOMINATES = "dominates"
    IS_DOMINATED = "is_dominated"
    NON_DOMINATED = "non_dominated"
    EQUAL = "equal"


@dataclass(frozen=True, order=True)
class Point:
    """A point in objective space."""

    values: NDArray[np.float64]

    def __post_init__(self):
        object.__setattr__(self, "values", np.array(self.values, dtype=np.float64))

    def __len__(self) -> int:
        return len(self.values)

    def dominates(self, other: Point) -> bool:
        """Check if this point dominates another (Pareto dominance)."""
        better = np.all(self.values <= other.values)
        strictly_better = np.any(self.values < other.values)
        return better and strictly_better

    def distance_to(self, other: Point) -> float:
        """Euclidean distance to another point."""
        return np.linalg.norm(self.values - other.values)

    def add(self, values: NDArray[np.float64]) -> Point:
        """Add values to this point and return new Point."""
        new_values = self.values + values
        return Point(new_values)

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary with indexed keys."""
        return {f"objective_{i}": float(v) for i, v in enumerate(self.values)}


@dataclass(frozen=True)
class Individual:
    """An individual in multi-objective optimization population."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    genes: NDArray[np.float64] = field(default_factory=lambda: np.array([]))
    objectives: Point = field(default_factory=lambda: Point(np.array([])))
    rank: int = 0  # Pareto rank (0 is best)
    crowding_distance: float = 0.0
    constraints: NDArray[np.float64] = field(default_factory=lambda: np.array([]))
    constraint_violation: float = 0.0

    def dominates(self, other: Individual) -> bool:
        """Check if this individual dominates another."""
        # Feasible dominates infeasible
        if self.constraint_violation == 0 and other.constraint_violation > 0:
            return True
        if self.constraint_violation > 0 and other.constraint_violation == 0:
            return False
        # Both infeasible: compare by constraint violation
        if self.constraint_violation > 0 and other.constraint_violation > 0:
            return self.constraint_violation < other.constraint_violation

        return self.objectives.dominates(other.objectives)


@dataclass
class ParetoFront:
    """Represents a Pareto front with non-dominated solutions."""

    individuals: list[Individual] = field(default_factory=list)
    hyper_volume: float = 0.0
    spacing: float = 0.0
    spread: float = 0.0

    def add(self, individual: Individual) -> bool:
        """Add individual if non-dominated."""
        dominated = []
        for existing in self.individuals:
            if individual.dominates(existing):
                dominated.append(existing)
            elif existing.dominates(individual):
                return False

        for d in dominated:
            self.individuals.remove(d)

        self.individuals.append(individual)
        return True

    def get_objective_values(self) -> NDArray[np.float64]:
        """Get all objective values as array."""
        return np.array([ind.objectives.values for ind in self.individuals])

    def get_genes(self) -> NDArray[np.float64]:
        """Get all gene values as array."""
        return np.array([ind.genes for ind in self.individuals])

    def calculate_hypervolume(
        self,
        reference_point: NDArray[np.float64] | None = None,
    ) -> float:
        """Calculate hypervolume indicator."""
        if not self.individuals:
            self.hyper_volume = 0.0
            return 0.0

        obj_values = self.get_objective_values()

        if reference_point is None:
            reference_point = np.max(obj_values, axis=0) * 1.1

        # Simple Monte Carlo hypervolume estimation
        n_samples = 100000
        random_points = np.random.random((n_samples, len(obj_values[0])))
        random_points = random_points * reference_point

        dominated = 0
        for point in random_points:
            for ind_obj in obj_values:
                if np.all(ind_obj <= point):
                    dominated += 1
                    break

        self.hyper_volume = (dominated / n_samples) * np.prod(reference_point)
        return self.hyper_volume

    def calculate_spacing(self) -> float:
        """Calculate spacing metric (uniformity of distribution)."""
        if len(self.individuals) < 2:
            self.spacing = 0.0
            return 0.0

        obj_values = self.get_objective_values()
        n = len(obj_values)

        # Calculate distance to nearest neighbor for each point
        distances = []
        for i in range(n):
            min_dist = float("inf")
            for j in range(n):
                if i != j:
                    dist = np.linalg.norm(obj_values[i] - obj_values[j])
                    min_dist = min(min_dist, dist)
            distances.append(min_dist)

        distances = np.array(distances)
        mean_dist = np.mean(distances)

        self.spacing = np.sqrt(np.sum((distances - mean_dist) ** 2) / n)
        return self.spacing


class MultiObjectiveProblem(ABC):
    """Base class for multi-objective optimization problems."""

    @abstractmethod
    def evaluate(self, genes: NDArray[np.float64]) -> Point:
        """Evaluate objectives for given genes."""
        pass

    @abstractmethod
    def evaluate_constraints(
        self,
        genes: NDArray[np.float64],
    ) -> tuple[NDArray[np.float64], float]:
        """Evaluate constraints and return (constraint_values, violation)."""
        pass

    @property
    @abstractmethod
    def num_objectives(self) -> int:
        """Number of objectives."""
        pass

    @property
    @abstractmethod
    def num_genes(self) -> int:
        """Number of genes (decision variables)."""
        pass

    @property
    @abstractmethod
    def bounds(self) -> list[tuple[float, float]]:
        """Bounds for each gene."""
        pass


class NSGA2Optimizer:
    """
    Non-dominated Sorting Genetic Algorithm II (NSGA-II).

    A well-established multi-objective evolutionary algorithm that uses:
    - Fast non-dominated sorting
    - Crowding distance for diversity preservation
    - Elitist selection
    """

    def __init__(
        self,
        problem: MultiObjectiveProblem,
        population_size: int = 100,
        num_generations: int = 250,
        crossover_prob: float = 0.9,
        mutation_prob: float = 0.1,
        eta_c: float = 20.0,  # Crossover distribution index
        eta_m: float = 20.0,  # Mutation distribution index
        seed: int | None = None,
    ):
        """
        Initialize NSGA-II optimizer.

        Args:
            problem: Multi-objective problem to optimize
            population_size: Size of population
            num_generations: Number of generations
            crossover_prob: Probability of crossover
            mutation_prob: Probability of mutation
            eta_c: Crossover distribution index (larger = more children near parents)
            eta_m: Mutation distribution index
            seed: Random seed
        """
        self.problem = problem
        self.population_size = population_size
        self.num_generations = num_generations
        self.crossover_prob = crossover_prob
        self.mutation_prob = mutation_prob
        self.eta_c = eta_c
        self.eta_m = eta_m

        self.rng = np.random.default_rng(seed)
        self._population: list[Individual] = []
        self._history: list[ParetoFront] = []

    def initialize_population(self) -> list[Individual]:
        """Initialize random population within bounds."""
        population = []

        for _ in range(self.population_size):
            genes = self.rng.random(self.problem.num_genes)
            bounds = self.problem.bounds
            for i, (lb, ub) in enumerate(bounds):
                genes[i] = lb + genes[i] * (ub - lb)

            objectives = self.problem.evaluate(genes)
            constraints, violation = self.problem.evaluate_constraints(genes)

            individual = Individual(
                genes=genes,
                objectives=objectives,
                constraints=constraints,
                constraint_violation=violation,
            )
            population.append(individual)

        self._population = population
        return population

    def non_dominated_sort(self, population: list[Individual]) -> list[list[Individual]]:
        """Fast non-dominated sorting algorithm."""
        fronts = []

        for i, p in enumerate(population):
            p.domination_count = 0  # Number of individuals dominating p
            p.dominated_solutions = []  # Individuals dominated by p

            for j, q in enumerate(population):
                if i == j:
                    continue

                if p.dominates(q):
                    p.dominated_solutions.append(q)
                elif q.dominates(p):
                    p.domination_count += 1

            if p.domination_count == 0:
                p.rank = 0
                if len(fronts) == 0:
                    fronts.append([])
                fronts[0].append(p)

        i = 0
        while len(fronts) > i:
            next_front = []

            for p in fronts[i]:
                for q in p.dominated_solutions:
                    q.domination_count -= 1

                    if q.domination_count == 0:
                        q.rank = i + 1
                        next_front.append(q)

            if next_front:
                fronts.append(next_front)

            i += 1

        return fronts

    def calculate_crowding_distance(self, front: list[Individual]) -> None:
        """Calculate crowding distance for a front."""
        num_individuals = len(front)
        num_objectives = self.problem.num_objectives

        for ind in front:
            ind.crowding_distance = 0.0

        for m in range(num_objectives):
            front.sort(key=lambda ind: ind.objectives.values[m])

            # Boundary individuals have infinite distance
            front[0].crowding_distance = float("inf")
            front[-1].crowding_distance = float("inf")

            obj_min = front[0].objectives.values[m]
            obj_max = front[-1].objectives.values[m]

            if obj_max - obj_min == 0:
                continue

            for i in range(1, num_individuals - 1):
                dist = front[i + 1].objectives.values[m] - front[i - 1].objectives.values[m]
                front[i].crowding_distance += dist / (obj_max - obj_min)

    def tournament_selection(
        self,
        population: list[Individual],
        tournament_size: int = 2,
    ) -> Individual:
        """Binary tournament selection based on rank and crowding distance."""
        individuals = self.rng.choice(population, tournament_size, replace=False)

        best = None
        for ind in individuals:
            if best is None or ind.dominates(best):
                best = ind
            elif not best.dominates(ind):
                # Same rank, prefer higher crowding distance
                if ind.rank == best.rank and ind.crowding_distance > best.crowding_distance:
                    best = ind

        return best

    def sbx_crossover(
        self,
        parent1: Individual,
        parent2: Individual,
    ) -> tuple[Individual, Individual]:
        """Simulated binary crossover."""
        child1_genes = parent1.genes.copy()
        child2_genes = parent2.genes.copy()

        bounds = self.problem.bounds

        if self.rng.random() < self.crossover_prob:
            for i in range(self.problem.num_genes):
                if self.rng.random() < 0.5:
                    continue

                y1, y2 = child1_genes[i], child2_genes[i]

                if abs(y1 - y2) < 1e-14:
                    continue

                lb, ub = bounds[i]

                beta = 1.0 + (2.0 * min(y1 - lb, ub - y2) / (y2 - y1))
                alpha = 2.0 - beta ** (-(self.eta_c + 1.0))

                if self.rng.random() <= 1.0 / alpha:
                    beta_q = (alpha * self.rng.random()) ** (1.0 / (self.eta_c + 1.0))
                else:
                    beta_q = (1.0 / (2.0 - alpha * self.rng.random())) ** (1.0 / (self.eta_c + 1.0))

                c1 = 0.5 * ((y1 + y2) - beta_q * abs(y2 - y1))
                c2 = 0.5 * ((y1 + y2) + beta_q * abs(y2 - y1))

                c1 = np.clip(c1, lb, ub)
                c2 = np.clip(c2, lb, ub)

                child1_genes[i] = c1 if self.rng.random() < 0.5 else c2
                child2_genes[i] = c2 if self.rng.random() < 0.5 else c1

        child1 = self._evaluate_individual(child1_genes)
        child2 = self._evaluate_individual(child2_genes)

        return child1, child2

    def polynomial_mutation(self, individual: Individual) -> Individual:
        """Polynomial mutation."""
        genes = individual.genes.copy()
        bounds = self.problem.bounds

        for i in range(self.problem.num_genes):
            if self.rng.random() > self.mutation_prob:
                continue

            y = genes[i]
            lb, ub = bounds[i]
            delta1 = (y - lb) / (ub - lb)
            delta2 = (ub - y) / (ub - lb)

            rnd = self.rng.random()
            mut_pow = 1.0 / (self.eta_m + 1.0)

            if rnd <= 0.5:
                xy = 1.0 - delta1
                val = 2.0 * rnd + (1.0 - 2.0 * rnd) * xy ** (self.eta_m + 1.0)
                delta_q = val**mut_pow - 1.0
            else:
                xy = 1.0 - delta2
                val = 2.0 * (1.0 - rnd) + 2.0 * (rnd - 0.5) * xy ** (self.eta_m + 1.0)
                delta_q = 1.0 - val**mut_pow

            y = y + delta_q * (ub - lb)
            y = np.clip(y, lb, ub)
            genes[i] = y

        return self._evaluate_individual(genes)

    def _evaluate_individual(self, genes: NDArray[np.float64]) -> Individual:
        """Evaluate a new individual."""
        objectives = self.problem.evaluate(genes)
        constraints, violation = self.problem.evaluate_constraints(genes)

        return Individual(
            genes=genes,
            objectives=objectives,
            constraints=constraints,
            constraint_violation=violation,
        )

    def evolve(self) -> list[Individual]:
        """Evolve population for specified generations."""
        self.initialize_population()

        for _generation in range(self.num_generations):
            # Create offspring population
            offspring = []

            while len(offspring) < self.population_size:
                parent1 = self.tournament_selection(self._population)
                parent2 = self.tournament_selection(self._population)

                child1, child2 = self.sbx_crossover(parent1, parent2)
                child1 = self.polynomial_mutation(child1)
                child2 = self.polynomial_mutation(child2)

                offspring.extend([child1, child2])

            # Combine parent and offspring populations
            combined = self._population + offspring[: self.population_size]

            # Non-dominated sorting
            fronts = self.non_dominated_sort(combined)

            # Select next generation
            next_population = []

            for front in fronts:
                if len(next_population) + len(front) <= self.population_size:
                    next_population.extend(front)
                else:
                    # Select individuals from front based on crowding distance
                    self.calculate_crowding_distance(front)
                    front.sort(key=lambda ind: -ind.crowding_distance)

                    remaining = self.population_size - len(next_population)
                    next_population.extend(front[:remaining])
                    break

            self._population = next_population

            # Store Pareto front for this generation
            pareto_front = ParetoFront()
            for ind in fronts[0]:
                pareto_front.add(ind)
            pareto_front.calculate_hypervolume()
            pareto_front.calculate_spacing()

            self._history.append(pareto_front)

        return self._population

    def get_pareto_front(self) -> ParetoFront:
        """Get final Pareto front."""
        fronts = self.non_dominated_sort(self._population)
        pareto_front = ParetoFront()

        for ind in fronts[0]:
            pareto_front.add(ind)

        pareto_front.calculate_hypervolume()
        pareto_front.calculate_spacing()

        return pareto_front

    def get_convergence_history(self) -> list[float]:
        """Get hypervolume history across generations."""
        return [front.hyper_volume for front in self._history]


class QuantumEnhancedMOO:
    """
    Quantum-Enhanced Multi-Objective Optimization.

    Integrates quantum optimization techniques with classical MOEA,
    using quantum circuits for:
    - Better initialization using quantum-inspired sampling
    - Hybrid quantum-classical evolution
    - Parallel objective evaluation
    """

    def __init__(
        self,
        problem: MultiObjectiveProblem,
        nsga2: NSGA2Optimizer,
        quantum_circuit_factory: Callable | None = None,
    ):
        """
        Initialize quantum-enhanced MOO.

        Args:
            problem: Multi-objective problem
            nsga2: NSGA-II optimizer as base
            quantum_circuit_factory: Factory for creating quantum circuits
        """
        self.problem = problem
        self.nsga2 = nsga2
        self.quantum_circuit_factory = quantum_circuit_factory

    def quantum_initialized_population(self) -> list[Individual]:
        """Initialize population using quantum-inspired sampling."""
        population = []

        if self.quantum_circuit_factory is not None:
            # Use quantum circuit for better sampling
            for _ in range(self.nsga2.population_size):
                genes = self._quantum_sample_genes()
                objectives = self.problem.evaluate(genes)
                constraints, violation = self.problem.evaluate_constraints(genes)

                individual = Individual(
                    genes=genes,
                    objectives=objectives,
                    constraints=constraints,
                    constraint_violation=violation,
                )
                population.append(individual)
        else:
            # Use quantum-inspired amplitude-based sampling
            for _ in range(self.nsga2.population_size):
                genes = self._amplitude_sample_genes()
                objectives = self.problem.evaluate(genes)
                constraints, violation = self.problem.evaluate_constraints(genes)

                individual = Individual(
                    genes=genes,
                    objectives=objectives,
                    constraints=constraints,
                    constraint_violation=violation,
                )
                population.append(individual)

        return population

    def _quantum_sample_genes(self) -> NDArray[np.float64]:
        """Sample genes using quantum circuit."""
        bounds = self.problem.bounds
        num_genes = self.problem.num_genes

        # Placeholder: In real implementation, would run quantum circuit
        # and measure to get probability distribution
        genes = self.nsga2.rng.random(num_genes)
        for i, (lb, ub) in enumerate(bounds):
            genes[i] = lb + genes[i] * (ub - lb)

        return genes

    def _amplitude_sample_genes(self) -> NDArray[np.float64]:
        """Quantum-inspired sampling using amplitude-like distribution."""
        bounds = self.problem.bounds

        # Use quantum-inspired probability distribution
        # (biased towards center of search space like wave function)
        genes = []
        for lb, ub in bounds:
            # Use probability density inspired by quantum wavefunction
            uniform = self.nsga2.rng.random()

            if uniform < 0.5:
                # Sample from Gaussian-like distribution
                center = (lb + ub) / 2
                width = (ub - lb) / 4
                gene = center + np.random.randn() * width
            else:
                # Uniform sampling as fallback
                uniform = self.nsga2.rng.random()
                gene = lb + uniform * (ub - lb)

            genes.append(np.clip(gene, lb, ub))

        return np.array(genes)

    def optimize(self) -> ParetoFront:
        """Run quantum-enhanced optimization."""
        self.nsga2._population = self.quantum_initialized_population()
        self.nsga2.evolve()
        return self.nsga2.get_pareto_front()


__all__ = [
    "DominanceRelation",
    "Point",
    "Individual",
    "ParetoFront",
    "MultiObjectiveProblem",
    "NSGA2Optimizer",
    "QuantumEnhancedMOO",
]

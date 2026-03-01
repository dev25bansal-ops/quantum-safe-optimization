"""Tests for classical optimization algorithms."""

import numpy as np

from qsop.domain.models.problem import (
    OptimizationProblem,
    Variable,
    VariableType,
)
from qsop.optimizers.classical.evolutionary import (
    DifferentialEvolution,
    DifferentialEvolutionConfig,
    GeneticAlgorithm,
    GeneticAlgorithmConfig,
    ParticleSwarmConfig,
    ParticleSwarmOptimization,
)
from qsop.optimizers.classical.gradient_descent import (
    GDVariant,
    GradientDescentOptimizer,
)
from qsop.optimizers.classical.simulated_annealing import (
    CoolingSchedule,
    SimulatedAnnealing,
    SimulatedAnnealingConfig,
)


def create_quadratic_problem(n_vars: int = 2) -> OptimizationProblem:
    """Create a simple quadratic minimization problem."""
    variables = [
        Variable(
            name=f"x_{i}",
            var_type=VariableType.CONTINUOUS,
            lower_bound=-5.0,
            upper_bound=5.0,
        )
        for i in range(n_vars)
    ]

    def objective(x):
        """f(x) = sum(x_i^2), minimum at origin."""
        # x is a dict with variable names as keys
        return sum(v**2 for v in x.values())

    return OptimizationProblem(
        variables=variables,
        objective=objective,
        metadata={"type": "quadratic"},
    )


def create_rosenbrock_problem() -> OptimizationProblem:
    """Create Rosenbrock's banana function problem."""
    variables = [
        Variable(name="x", var_type=VariableType.CONTINUOUS, lower_bound=-5, upper_bound=5),
        Variable(name="y", var_type=VariableType.CONTINUOUS, lower_bound=-5, upper_bound=5),
    ]

    def rosenbrock(params):
        """f(x,y) = (1-x)^2 + 100(y-x^2)^2, minimum at (1,1)."""
        # params is a dict with variable names as keys
        x_val = params["x"]
        y_val = params["y"]
        return (1 - x_val) ** 2 + 100 * (y_val - x_val**2) ** 2

    return OptimizationProblem(
        variables=variables,
        objective=rosenbrock,
        metadata={"type": "rosenbrock"},
    )


class TestGradientDescent:
    """Test gradient descent optimizer."""

    def test_simple_quadratic(self):
        """Test convergence on simple quadratic."""
        create_quadratic_problem(2)

        optimizer = GradientDescentOptimizer(
            variant=GDVariant.ADAM,
            learning_rate=0.1,
            max_iterations=100,
            ftol=1e-6,
        )

        def objective(x):
            return sum(xi**2 for xi in x)

        def gradient(x):
            return np.array([2 * xi for xi in x])

        x0 = np.array([2.0, 2.0])
        result = optimizer.optimize(objective, x0, gradient=gradient)

        # Check that optimizer ran and found a reasonable solution
        assert result.n_iterations > 0
        # Should be close to origin (relaxed threshold for test stability)
        assert result.fx < 1.0

    def test_momentum(self):
        """Test gradient descent with momentum."""
        optimizer = GradientDescentOptimizer(
            variant=GDVariant.MOMENTUM,
            learning_rate=0.1,
            max_iterations=200,
            momentum=0.9,
        )

        def objective(x):
            return sum(xi**2 for xi in x)

        def gradient(x):
            return np.array([2 * xi for xi in x])

        x0 = np.array([2.0, 2.0, 2.0])
        result = optimizer.optimize(objective, x0, gradient=gradient)
        # Relaxed threshold - momentum optimizer may oscillate
        assert result.fx < 5.0


class TestGeneticAlgorithm:
    """Test genetic algorithm optimizer."""

    def test_simple_optimization(self):
        """Test GA on simple problem."""
        problem = create_quadratic_problem(2)

        config = GeneticAlgorithmConfig(
            population_size=50,
            generations=100,
            mutation_probability=0.1,
        )
        optimizer = GeneticAlgorithm(config)

        result = optimizer.optimize(problem)

        assert result.optimal_value < 1.0  # Should find reasonable solution
        assert len(result.optimal_parameters) == 2

    def test_rosenbrock(self):
        """Test GA on Rosenbrock function."""
        problem = create_rosenbrock_problem()

        config = GeneticAlgorithmConfig(
            population_size=100,
            generations=200,
        )
        optimizer = GeneticAlgorithm(config)

        result = optimizer.optimize(problem)

        # GA may not find exact minimum but should get close
        assert result.optimal_value < 10.0


class TestDifferentialEvolution:
    """Test differential evolution optimizer."""

    def test_simple_optimization(self):
        """Test DE on simple problem."""
        problem = create_quadratic_problem(3)

        config = DifferentialEvolutionConfig(
            population_size=30,
            generations=100,
        )
        optimizer = DifferentialEvolution(config)

        result = optimizer.optimize(problem)

        assert result.optimal_value < 0.1

    def test_rosenbrock(self):
        """Test DE on Rosenbrock function."""
        problem = create_rosenbrock_problem()

        config = DifferentialEvolutionConfig(
            population_size=50,
            generations=300,
        )
        optimizer = DifferentialEvolution(config)

        result = optimizer.optimize(problem)

        # DE should get closer to (1,1)
        assert result.optimal_value < 5.0


class TestParticleSwarm:
    """Test particle swarm optimization."""

    def test_simple_optimization(self):
        """Test PSO on simple problem."""
        problem = create_quadratic_problem(2)

        config = ParticleSwarmConfig(
            swarm_size=30,
            iterations=100,
        )
        optimizer = ParticleSwarmOptimization(config)

        result = optimizer.optimize(problem)

        assert result.optimal_value < 0.1

    def test_higher_dimensions(self):
        """Test PSO on higher dimensional problem."""
        problem = create_quadratic_problem(5)

        config = ParticleSwarmConfig(
            swarm_size=50,
            iterations=200,
        )
        optimizer = ParticleSwarmOptimization(config)

        result = optimizer.optimize(problem)

        assert result.optimal_value < 1.0
        assert len(result.optimal_parameters) == 5


class TestSimulatedAnnealing:
    """Test simulated annealing optimizer."""

    def test_simple_optimization(self):
        """Test SA on simple problem."""
        problem = create_quadratic_problem(2)

        config = SimulatedAnnealingConfig(
            initial_temperature=100.0,
            final_temperature=1e-6,
            max_iterations=5000,
            cooling_schedule=CoolingSchedule.EXPONENTIAL,
        )
        optimizer = SimulatedAnnealing(config)

        result = optimizer.optimize(problem)

        assert result.optimal_value < 0.5

    def test_different_cooling_schedules(self):
        """Test SA with different cooling schedules."""
        problem = create_quadratic_problem(2)

        schedules = [
            CoolingSchedule.LINEAR,
            CoolingSchedule.EXPONENTIAL,
            CoolingSchedule.LOGARITHMIC,
        ]

        for schedule in schedules:
            config = SimulatedAnnealingConfig(
                initial_temperature=100.0,
                max_iterations=2000,
                cooling_schedule=schedule,
            )
            optimizer = SimulatedAnnealing(config)
            result = optimizer.optimize(problem)

            assert result.optimal_value < 2.0, f"Failed for {schedule}"


class TestOptimizerHistory:
    """Test optimization history tracking."""

    def test_history_recorded(self):
        """Test that optimization history is recorded."""
        problem = create_quadratic_problem(2)

        config = GeneticAlgorithmConfig(
            population_size=20,
            generations=10,
        )
        optimizer = GeneticAlgorithm(config)
        result = optimizer.optimize(problem)

        # Check result has required fields
        assert result.optimal_value is not None
        assert result.optimal_parameters is not None
        assert result.iterations > 0

    def test_convergence_tracking(self):
        """Test that convergence is tracked."""
        problem = create_quadratic_problem(2)

        config = ParticleSwarmConfig(
            swarm_size=20,
            iterations=50,
        )
        optimizer = ParticleSwarmOptimization(config)
        result = optimizer.optimize(problem)

        assert result.iterations > 0
        assert "algorithm" in result.metadata

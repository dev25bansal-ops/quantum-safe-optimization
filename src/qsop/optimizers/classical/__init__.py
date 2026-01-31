"""Classical optimization algorithms."""

from .base import BaseClassicalOptimizer, ConvergenceChecker, OptimizationHistory
from .gradient_descent import (
    GradientDescentOptimizer,
    GDVariant,
    LRScheduleType,
    LRScheduleConfig,
)
from .evolutionary import (
    GeneticAlgorithm,
    GeneticAlgorithmConfig,
    DifferentialEvolution,
    DifferentialEvolutionConfig,
    ParticleSwarmOptimization,
    ParticleSwarmConfig,
)
from .simulated_annealing import (
    SimulatedAnnealing,
    SimulatedAnnealingConfig,
    CoolingSchedule,
)

__all__ = [
    "BaseClassicalOptimizer",
    "ConvergenceChecker",
    "OptimizationHistory",
    "GradientDescentOptimizer",
    "LRScheduleConfig",
    "GDVariant",
    "LRScheduleType",
    "GeneticAlgorithm",
    "GeneticAlgorithmConfig",
    "DifferentialEvolution",
    "DifferentialEvolutionConfig",
    "ParticleSwarmOptimization",
    "ParticleSwarmConfig",
    "SimulatedAnnealing",
    "SimulatedAnnealingConfig",
    "CoolingSchedule",
]

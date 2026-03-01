"""Classical optimization algorithms."""

from .base import BaseClassicalOptimizer, ConvergenceChecker, OptimizationHistory
from .evolutionary import (
    DifferentialEvolution,
    DifferentialEvolutionConfig,
    GeneticAlgorithm,
    GeneticAlgorithmConfig,
    ParticleSwarmConfig,
    ParticleSwarmOptimization,
)
from .gradient_descent import (
    GDVariant,
    GradientDescentOptimizer,
    LRScheduleConfig,
    LRScheduleType,
)
from .simulated_annealing import (
    CoolingSchedule,
    SimulatedAnnealing,
    SimulatedAnnealingConfig,
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

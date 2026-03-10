"""Quantum Optimization Module

Provides quantum optimization algorithms (QAOA, VQE, Quantum Annealing)
with a unified backend abstraction layer.
"""

from .annealing import AnnealingRunner, QUBOProblem
from .backends import BackendType, QuantumBackend
from .qaoa import MaxCutProblem, PortfolioProblem, QAOARunner
from .vqe import MolecularHamiltonian, VQERunner

__version__ = "0.1.0"

__all__ = [
    "QuantumBackend",
    "BackendType",
    "QAOARunner",
    "MaxCutProblem",
    "PortfolioProblem",
    "VQERunner",
    "MolecularHamiltonian",
    "AnnealingRunner",
    "QUBOProblem",
]

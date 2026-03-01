"""
Quantum Optimization Module

Provides quantum optimization algorithms (QAOA, VQE, Quantum Annealing)
with a unified backend abstraction layer.
"""

from src.annealing import AnnealingRunner, QUBOProblem
from src.backends import BackendType, QuantumBackend
from src.qaoa import MaxCutProblem, PortfolioProblem, QAOARunner
from src.vqe import MolecularHamiltonian, VQERunner

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

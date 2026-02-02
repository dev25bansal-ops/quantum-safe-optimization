"""
Quantum Optimization Module

Provides quantum optimization algorithms (QAOA, VQE, Quantum Annealing)
with a unified backend abstraction layer.
"""

from src.backends import QuantumBackend, BackendType
from src.qaoa import QAOARunner, MaxCutProblem, PortfolioProblem
from src.vqe import VQERunner, MolecularHamiltonian
from src.annealing import AnnealingRunner, QUBOProblem

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

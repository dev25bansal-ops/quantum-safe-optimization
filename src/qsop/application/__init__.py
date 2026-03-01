"""
QSOP Application Layer.

This module provides the application services and workflows for the
Quantum-Safe Optimization Platform.
"""

from qsop.application.services.crypto_service import CryptoService
from qsop.application.services.job_service import JobService
from qsop.application.services.policy_service import PolicyService
from qsop.application.services.registry_service import BackendRegistry, OptimizerRegistry
from qsop.application.services.workflow_service import WorkflowService
from qsop.application.workflows.hybrid_loop import HybridOptimizationLoop
from qsop.application.workflows.qaoa import QAOAWorkflow
from qsop.application.workflows.vqe import VQEWorkflow

__all__ = [
    # Services
    "JobService",
    "WorkflowService",
    "OptimizerRegistry",
    "BackendRegistry",
    "CryptoService",
    "PolicyService",
    # Workflows
    "HybridOptimizationLoop",
    "VQEWorkflow",
    "QAOAWorkflow",
]

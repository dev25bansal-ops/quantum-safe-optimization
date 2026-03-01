"""
Workflow Registry for QSOP.

Maps algorithm names to their corresponding WorkflowDefinitions and Executors.
"""

from ..services.workflow_service import (
    WorkflowDefinition,
    WorkflowExecutor,
    WorkflowStep,
)
from .adapters import QAOAExecutorAdapter, VQEExecutorAdapter


class WorkflowRegistry:
    """
    Registry for managing workflow definitions and executors.
    """

    def __init__(self):
        self._registry: dict[str, tuple[WorkflowDefinition, type[WorkflowExecutor]]] = {}
        self._initialize_defaults()

    def _initialize_defaults(self):
        """Register default workflows."""
        # VQE Workflow
        vqe_def = WorkflowDefinition(
            id="vqe",
            name="Variational Quantum Eigensolver",
            steps=[
                WorkflowStep(id="setup", name="Circuit Setup"),
                WorkflowStep(id="optimization", name="Classical Optimization"),
                WorkflowStep(id="finalize", name="Result Finalization"),
            ],
        )
        self.register("vqe", vqe_def, VQEExecutorAdapter)

        # QAOA Workflow
        qaoa_def = WorkflowDefinition(
            id="qaoa",
            name="Quantum Approximate Optimization Algorithm",
            steps=[
                WorkflowStep(id="setup", name="Problem Mapping"),
                WorkflowStep(id="optimization", name="Variational Loop"),
                WorkflowStep(id="finalize", name="Result Extraction"),
            ],
        )
        self.register("qaoa", qaoa_def, QAOAExecutorAdapter)

    def register(
        self,
        algorithm_name: str,
        definition: WorkflowDefinition,
        executor_cls: type[WorkflowExecutor],
    ):
        """Register a new workflow."""
        self._registry[algorithm_name.lower()] = (definition, executor_cls)

    def get(self, algorithm_name: str) -> tuple[WorkflowDefinition, type[WorkflowExecutor]] | None:
        """Retrieve workflow components for an algorithm."""
        return self._registry.get(algorithm_name.lower())

    def list_algorithms(self) -> list[str]:
        """List all registered algorithms."""
        return list(self._registry.keys())

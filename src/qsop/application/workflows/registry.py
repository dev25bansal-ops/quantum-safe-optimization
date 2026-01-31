"""
Workflow Registry for QSOP.

Maps algorithm names to their corresponding WorkflowDefinitions and Executors.
"""

from typing import Dict, Optional, Tuple, Type

from .adapters import VQEExecutorAdapter, QAOAExecutorAdapter
from ..services.workflow_service import WorkflowDefinition, WorkflowExecutor, WorkflowStep, StepStatus


class WorkflowRegistry:
    """
    Registry for managing workflow definitions and executors.
    """
    
    def __init__(self):
        self._registry: Dict[str, Tuple[WorkflowDefinition, Type[WorkflowExecutor]]] = {}
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
            ]
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
            ]
        )
        self.register("qaoa", qaoa_def, QAOAExecutorAdapter)
    
    def register(
        self, 
        algorithm_name: str, 
        definition: WorkflowDefinition, 
        executor_cls: Type[WorkflowExecutor]
    ):
        """Register a new workflow."""
        self._registry[algorithm_name.lower()] = (definition, executor_cls)
    
    def get(self, algorithm_name: str) -> Optional[Tuple[WorkflowDefinition, Type[WorkflowExecutor]]]:
        """Retrieve workflow components for an algorithm."""
        return self._registry.get(algorithm_name.lower())
    
    def list_algorithms(self) -> list[str]:
        """List all registered algorithms."""
        return list(self._registry.keys())

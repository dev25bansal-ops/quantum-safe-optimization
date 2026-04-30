"""
Strategy Pattern for Quantum Optimization Job Processing.

Replaces giant if/elif chain with pluggable processor strategy.
Makes it easy to add new problem types without modifying core logic.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class JobResult:
    """Represents the result of a quantum optimization job."""
    
    def __init__(
        self,
        success: bool,
        data: dict[str, Any] | None = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.success = success
        self.data = data or {}
        self.error = error
        self.metadata = metadata or {}
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }


class ProblemProcessor(ABC):
    """Abstract base class for problem processors."""
    
    @abstractmethod
    async def solve(self, config: dict, parameters: dict) -> JobResult:
        """
        Solve a quantum optimization problem.
        
        Args:
            config: Problem-specific configuration (graph, hamiltonian, etc.)
            parameters: Algorithm parameters (layers, optimizer, shots, etc.)
            
        Returns:
            JobResult with success status and data/error
        """
        pass
    
    @abstractmethod
    def get_problem_type(self) -> str:
        """Return the problem type this processor handles."""
        pass
    
    async def validate_config(self, config: dict) -> tuple[bool, str | None]:
        """
        Validate problem configuration.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        return True, None


class QAOAProcessor(ProblemProcessor):
    """Quantum Approximate Optimization Algorithm processor."""
    
    def get_problem_type(self) -> str:
        return "QAOA"
    
    async def validate_config(self, config: dict) -> tuple[bool, str | None]:
        problem_type = config.get("type")
        if problem_type not in ["maxcut", "portfolio", "tsp", "graph_coloring"]:
            return False, f"Unsupported QAOA problem type: {problem_type}"
        
        if problem_type == "maxcut" and "edges" not in config:
            return False, "MaxCut problem requires 'edges' in config"
        
        return True, None
    
    async def solve(self, config: dict, parameters: dict) -> JobResult:
        """Solve using QAOA."""
        try:
            # Import optimization modules
            from optimization.src.qaoa.runner import QAOARunner
            from optimization.src.backends.factory import create_backend
            
            # Validate
            is_valid, error = await self.validate_config(config)
            if not is_valid:
                return JobResult(success=False, error=error)
            
            # Create backend
            backend = create_backend(
                backend_type=parameters.get("backend", "aer_simulator"),
                **parameters.get("backend_config", {})
            )
            
            # Initialize QAOA runner
            runner = QAOARunner(
                backend=backend,
                layers=parameters.get("layers", 3),
                optimizer=parameters.get("optimizer", "COBYLA"),
                shots=parameters.get("shots", 1000),
            )
            
            # Solve based on problem type
            problem_type = config.get("type")
            
            if problem_type == "maxcut":
                result = await runner.solve_maxcut(
                    edges=config["edges"],
                    weights=config.get("weights", [1] * len(config["edges"])),
                )
            elif problem_type == "portfolio":
                result = await runner.solve_portfolio(
                    returns=config["returns"],
                    covariance=config["covariance"],
                    risk_aversion=config.get("risk_aversion", 0.5),
                )
            elif problem_type == "tsp":
                result = await runner.solve_tsp(
                    distance_matrix=config["distance_matrix"],
                )
            elif problem_type == "graph_coloring":
                result = await runner.solve_graph_coloring(
                    edges=config["edges"],
                    num_colors=config["num_colors"],
                )
            else:
                return JobResult(
                    success=False,
                    error=f"Unsupported QAOA problem type: {problem_type}"
                )
            
            return JobResult(
                success=True,
                data=result,
                metadata={
                    "algorithm": "QAOA",
                    "problem_type": problem_type,
                    "layers": parameters.get("layers", 3),
                    "optimizer": parameters.get("optimizer", "COBYLA"),
                }
            )
            
        except Exception as e:
            logger.exception("qaoa_solve_failed", error=str(e))
            return JobResult(
                success=False,
                error=f"QAOA solving failed: {str(e)}",
            )


class VQEProcessor(ProblemProcessor):
    """Variational Quantum Eigensolver processor."""
    
    def get_problem_type(self) -> str:
        return "VQE"
    
    async def validate_config(self, config: dict) -> tuple[bool, str | None]:
        if "molecule" not in config and "hamiltonian" not in config:
            return False, "VQE requires either 'molecule' or 'hamiltonian' in config"
        
        return True, None
    
    async def solve(self, config: dict, parameters: dict) -> JobResult:
        """Solve using VQE."""
        try:
            from optimization.src.vqe.runner import VQERunner
            from optimization.src.backends.factory import create_backend
            
            # Validate
            is_valid, error = await self.validate_config(config)
            if not is_valid:
                return JobResult(success=False, error=error)
            
            # Create backend
            backend = create_backend(
                backend_type=parameters.get("backend", "aer_simulator"),
                **parameters.get("backend_config", {})
            )
            
            # Initialize VQE runner
            runner = VQERunner(
                backend=backend,
                ansatz=parameters.get("ansatz", "UCCSD"),
                optimizer=parameters.get("optimizer", "SLSQP"),
                shots=parameters.get("shots", 1000),
            )
            
            # Solve
            if "molecule" in config:
                result = await runner.solve_molecule(
                    molecule=config["molecule"],
                    basis=config.get("basis", "sto3g"),
                    distance=config.get("distance"),
                )
            elif "hamiltonian" in config:
                result = await runner.solve_hamiltonian(
                    hamiltonian=config["hamiltonian"],
                )
            else:
                return JobResult(
                    success=False,
                    error="Invalid VQE configuration"
                )
            
            return JobResult(
                success=True,
                data=result,
                metadata={
                    "algorithm": "VQE",
                    "ansatz": parameters.get("ansatz", "UCCSD"),
                    "optimizer": parameters.get("optimizer", "SLSQP"),
                }
            )
            
        except Exception as e:
            logger.exception("vqe_solve_failed", error=str(e))
            return JobResult(
                success=False,
                error=f"VQE solving failed: {str(e)}",
            )


class AnnealingProcessor(ProblemProcessor):
    """Quantum Annealing processor (D-Wave)."""
    
    def get_problem_type(self) -> str:
        return "ANNEALING"
    
    async def validate_config(self, config: dict) -> tuple[bool, str | None]:
        if "qubo" not in config and "ising" not in config:
            return False, "Annealing requires either 'qubo' or 'ising' in config"
        
        return True, None
    
    async def solve(self, config: dict, parameters: dict) -> JobResult:
        """Solve using Quantum Annealing."""
        try:
            from optimization.src.annealing.runner import AnnealingRunner
            from optimization.src.backends.factory import create_backend
            
            # Validate
            is_valid, error = await self.validate_config(config)
            if not is_valid:
                return JobResult(success=False, error=error)
            
            # Create backend
            backend = create_backend(
                backend_type=parameters.get("backend", "dwave_simulator"),
                **parameters.get("backend_config", {})
            )
            
            # Initialize annealing runner
            runner = AnnealingRunner(
                backend=backend,
                num_reads=parameters.get("num_reads", 1000),
                annealing_time=parameters.get("annealing_time", 20),
            )
            
            # Solve
            if "qubo" in config:
                result = await runner.solve_qubo(
                    qubo=config["qubo"],
                )
            elif "ising" in config:
                result = await runner.solve_ising(
                    h=config["ising"]["h"],
                    j=config["ising"]["j"],
                )
            else:
                return JobResult(
                    success=False,
                    error="Invalid annealing configuration"
                )
            
            return JobResult(
                success=True,
                data=result,
                metadata={
                    "algorithm": "Quantum Annealing",
                    "num_reads": parameters.get("num_reads", 1000),
                }
            )
            
        except Exception as e:
            logger.exception("annealing_solve_failed", error=str(e))
            return JobResult(
                success=False,
                error=f"Annealing solving failed: {str(e)}",
            )


class ProcessorRegistry:
    """
    Registry of problem processors.
    
    Provides:
    - Automatic processor discovery
    - Problem type routing
    - Validation across all processors
    """
    
    def __init__(self):
        self._processors: dict[str, ProblemProcessor] = {}
        self._register_default_processors()
    
    def _register_default_processors(self):
        """Register default problem processors."""
        processors = [
            QAOAProcessor(),
            VQEProcessor(),
            AnnealingProcessor(),
        ]
        
        for processor in processors:
            self.register(processor)
    
    def register(self, processor: ProblemProcessor):
        """Register a problem processor."""
        problem_type = processor.get_problem_type()
        self._processors[problem_type] = processor
        logger.info("processor_registered", problem_type=problem_type)
    
    def get_processor(self, problem_type: str) -> ProblemProcessor | None:
        """Get processor for a problem type."""
        return self._processors.get(problem_type)
    
    def get_supported_problem_types(self) -> list[str]:
        """Get list of supported problem types."""
        return list(self._processors.keys())
    
    async def validate_problem_config(
        self,
        problem_type: str,
        config: dict
    ) -> tuple[bool, str | None]:
        """
        Validate a problem configuration.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        processor = self.get_processor(problem_type)
        if not processor:
            return False, f"Unsupported problem type: {problem_type}"
        
        return await processor.validate_config(config)
    
    async def solve_problem(
        self,
        problem_type: str,
        config: dict,
        parameters: dict
    ) -> JobResult:
        """
        Solve a quantum optimization problem.
        
        Args:
            problem_type: Type of problem (QAOA, VQE, ANNEALING)
            config: Problem configuration
            parameters: Algorithm parameters
            
        Returns:
            JobResult with success status and data/error
        """
        processor = self.get_processor(problem_type)
        if not processor:
            return JobResult(
                success=False,
                error=f"Unsupported problem type: {problem_type}. "
                      f"Supported: {self.get_supported_problem_types()}"
            )
        
        logger.info(
            "solving_problem",
            problem_type=problem_type,
            processor=processor.__class__.__name__,
        )
        
        return await processor.solve(config, parameters)
    
    def get_processor_info(self, problem_type: str) -> dict | None:
        """Get information about a processor."""
        processor = self.get_processor(problem_type)
        if not processor:
            return None
        
        return {
            "problem_type": problem_type,
            "processor_class": processor.__class__.__name__,
            "supports_validation": True,
        }


# Global registry instance
registry = ProcessorRegistry()


# Convenience functions
async def solve_problem(
    problem_type: str,
    config: dict,
    parameters: dict
) -> JobResult:
    """
    Solve a quantum optimization problem using the global registry.
    
    Args:
        problem_type: Type of problem (QAOA, VQE, ANNEALING)
        config: Problem configuration
        parameters: Algorithm parameters
        
    Returns:
        JobResult with success status and data/error
    """
    return await registry.solve_problem(problem_type, config, parameters)


def get_supported_problem_types() -> list[str]:
    """Get list of supported problem types."""
    return registry.get_supported_problem_types()

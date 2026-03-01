"""
Optimizer port definition.

Defines the protocol for optimization algorithms including classical,
quantum, and hybrid approaches.
"""

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from qsop.domain.models.problem import OptimizationProblem
from qsop.domain.models.result import OptimizationResult


@runtime_checkable
class Optimizer(Protocol):
    """
    Protocol for optimization algorithms.

    Implementations can be classical optimizers (COBYLA, SLSQP),
    quantum optimizers (VQE, QAOA), or hybrid algorithms.
    """

    @property
    def name(self) -> str:
        """Return the name of the optimizer."""
        ...

    @property
    def supports_constraints(self) -> bool:
        """Check if the optimizer supports constrained optimization."""
        ...

    @property
    def supports_gradients(self) -> bool:
        """Check if the optimizer can use gradient information."""
        ...

    @property
    def is_quantum(self) -> bool:
        """Check if this is a quantum or hybrid optimizer."""
        ...

    def optimize(
        self,
        problem: OptimizationProblem,
        callback: Callable[[int, dict[str, float], float], None] | None = None,
        **options: Any,
    ) -> OptimizationResult:
        """
        Run optimization on the given problem.

        Args:
            problem: The optimization problem to solve.
            callback: Optional callback called each iteration with
                      (iteration, parameters, objective_value).
            **options: Additional optimizer-specific options.

        Returns:
            The optimization result.

        Raises:
            OptimizationError: If optimization fails.
            ValidationError: If problem is invalid for this optimizer.
        """
        ...

    def get_default_options(self) -> dict[str, Any]:
        """
        Get default options for this optimizer.

        Returns:
            Dictionary of default option names to values.
        """
        ...

    def validate_problem(self, problem: OptimizationProblem) -> list[str]:
        """
        Validate that a problem is suitable for this optimizer.

        Args:
            problem: The optimization problem to validate.

        Returns:
            List of validation error messages (empty if valid).
        """
        ...

"""
Base classes and utilities for classical optimization algorithms.

This module provides the abstract base class for all classical optimizers,
along with common utilities for convergence checking, history tracking,
and callback management.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import (
    Any,
    Protocol,
    TypeVar,
    runtime_checkable,
)

import numpy as np
from numpy.typing import NDArray


class ConvergenceStatus(Enum):
    """Status of optimization convergence."""

    NOT_CONVERGED = auto()
    CONVERGED_FTOL = auto()
    CONVERGED_XTOL = auto()
    CONVERGED_GTOL = auto()
    MAX_ITERATIONS = auto()
    EARLY_STOPPED = auto()
    FAILED = auto()


@dataclass
class OptimizationState:
    """Current state of an optimization run."""

    iteration: int
    x: NDArray[np.float64]
    fx: float
    gradient: NDArray[np.float64] | None = None
    step_size: float | None = None
    constraint_violation: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationHistory:
    """Complete history of an optimization run."""

    x_history: list[NDArray[np.float64]] = field(default_factory=list)
    fx_history: list[float] = field(default_factory=list)
    gradient_history: list[NDArray[np.float64] | None] = field(default_factory=list)
    step_sizes: list[float] = field(default_factory=list)
    constraint_violations: list[float] = field(default_factory=list)
    timestamps: list[float] = field(default_factory=list)

    def append(self, state: OptimizationState, timestamp: float | None = None) -> None:
        """Append a state to the history."""
        self.x_history.append(state.x.copy())
        self.fx_history.append(state.fx)
        self.gradient_history.append(state.gradient.copy() if state.gradient is not None else None)
        if state.step_size is not None:
            self.step_sizes.append(state.step_size)
        self.constraint_violations.append(state.constraint_violation)
        if timestamp is not None:
            self.timestamps.append(timestamp)

    def record(self, fx: float, x: list[float] | NDArray[np.float64] | None = None) -> None:
        """Record a function value and optionally the parameters."""
        self.fx_history.append(fx)
        if x is not None:
            arr = np.array(x) if not isinstance(x, np.ndarray) else x
            self.x_history.append(arr)

    def to_dict(self) -> dict:
        """Convert history to dictionary."""
        return {
            "x_history": [x.tolist() for x in self.x_history],
            "fx_history": self.fx_history,
            "step_sizes": self.step_sizes,
        }

    @property
    def best_x(self) -> NDArray[np.float64] | None:
        """Return the best solution found."""
        if not self.fx_history:
            return None
        idx = int(np.argmin(self.fx_history))
        return self.x_history[idx]

    @property
    def best_fx(self) -> float | None:
        """Return the best objective value found."""
        if not self.fx_history:
            return None
        return min(self.fx_history)


@dataclass
class ClassicalOptimizationResult:
    """Result of a classical optimization run."""

    x: NDArray[np.float64]
    fx: float
    success: bool
    status: ConvergenceStatus
    message: str
    n_iterations: int
    n_function_evals: int
    n_gradient_evals: int
    history: OptimizationHistory
    constraint_violation: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ObjectiveFunction(Protocol):
    """Protocol for objective functions."""

    def __call__(self, x: NDArray[np.float64]) -> float:
        """Evaluate the objective function at x."""
        ...


@runtime_checkable
class GradientFunction(Protocol):
    """Protocol for gradient functions."""

    def __call__(self, x: NDArray[np.float64]) -> NDArray[np.float64]:
        """Evaluate the gradient at x."""
        ...


@runtime_checkable
class ConstraintFunction(Protocol):
    """Protocol for constraint functions (returns violation, 0 = satisfied)."""

    def __call__(self, x: NDArray[np.float64]) -> float:
        """Evaluate constraint violation at x."""
        ...


@dataclass
class Bounds:
    """Variable bounds for optimization."""

    lower: NDArray[np.float64] | None = None
    upper: NDArray[np.float64] | None = None

    def clip(self, x: NDArray[np.float64]) -> NDArray[np.float64]:
        """Clip x to be within bounds."""
        result = x.copy()
        if self.lower is not None:
            result = np.maximum(result, self.lower)
        if self.upper is not None:
            result = np.minimum(result, self.upper)
        return result

    def is_feasible(self, x: NDArray[np.float64]) -> bool:
        """Check if x is within bounds."""
        if self.lower is not None and np.any(x < self.lower):
            return False
        if self.upper is not None and np.any(x > self.upper):
            return False
        return True


@dataclass
class ConvergenceConfig:
    """Configuration for convergence checking."""

    ftol: float = 1e-8
    xtol: float = 1e-8
    gtol: float = 1e-5
    max_iterations: int = 1000
    min_iterations: int = 0
    patience: int = 10
    relative_tolerance: bool = True


class ConvergenceChecker:
    """Utility class for checking optimization convergence."""

    def __init__(self, config: ConvergenceConfig):
        self.config = config
        self._no_improvement_count = 0
        self._best_fx = float("inf")
        self._prev_x: NDArray[np.float64] | None = None
        self._prev_fx: float | None = None

    def reset(self) -> None:
        """Reset the convergence checker state."""
        self._no_improvement_count = 0
        self._best_fx = float("inf")
        self._prev_x = None
        self._prev_fx = None

    def check(
        self,
        iteration: int,
        x: NDArray[np.float64],
        fx: float,
        gradient: NDArray[np.float64] | None = None,
    ) -> ConvergenceStatus:
        """Check convergence based on current state."""
        if iteration < self.config.min_iterations:
            self._update_state(x, fx)
            return ConvergenceStatus.NOT_CONVERGED

        if iteration >= self.config.max_iterations:
            return ConvergenceStatus.MAX_ITERATIONS

        if gradient is not None:
            gnorm = np.linalg.norm(gradient)
            if gnorm < self.config.gtol:
                return ConvergenceStatus.CONVERGED_GTOL

        if self._prev_fx is not None:
            if self.config.relative_tolerance:
                fx_diff = abs(fx - self._prev_fx) / max(abs(self._prev_fx), 1e-10)
            else:
                fx_diff = abs(fx - self._prev_fx)
            if fx_diff < self.config.ftol:
                return ConvergenceStatus.CONVERGED_FTOL

        if self._prev_x is not None:
            if self.config.relative_tolerance:
                x_diff = np.linalg.norm(x - self._prev_x) / max(np.linalg.norm(self._prev_x), 1e-10)
            else:
                x_diff = np.linalg.norm(x - self._prev_x)
            if x_diff < self.config.xtol:
                return ConvergenceStatus.CONVERGED_XTOL

        if fx < self._best_fx - self.config.ftol:
            self._best_fx = fx
            self._no_improvement_count = 0
        else:
            self._no_improvement_count += 1

        if self._no_improvement_count >= self.config.patience:
            return ConvergenceStatus.EARLY_STOPPED

        self._update_state(x, fx)
        return ConvergenceStatus.NOT_CONVERGED

    def _update_state(self, x: NDArray[np.float64], fx: float) -> None:
        """Update internal state."""
        self._prev_x = x.copy()
        self._prev_fx = fx


CallbackT = TypeVar("CallbackT", bound=Callable[..., Any])


@runtime_checkable
class OptimizationCallback(Protocol):
    """Protocol for optimization callbacks."""

    def __call__(self, state: OptimizationState) -> bool | None:
        """
        Called at each iteration.

        Returns:
            True to stop optimization early, False or None to continue.
        """
        ...


class CallbackManager:
    """Manages callbacks during optimization."""

    def __init__(self, callbacks: list[OptimizationCallback] | None = None):
        self.callbacks = callbacks or []

    def add(self, callback: OptimizationCallback) -> None:
        """Add a callback."""
        self.callbacks.append(callback)

    def notify(self, state: OptimizationState) -> bool:
        """
        Notify all callbacks of current state.

        Returns:
            True if any callback requested early stopping.
        """
        for callback in self.callbacks:
            result = callback(state)
            if result is True:
                return True
        return False


class BaseClassicalOptimizer(ABC):
    """
    Abstract base class for classical optimization algorithms.

    All classical optimizers should inherit from this class and implement
    the optimize() method. This class provides common functionality for
    history tracking, convergence checking, and callback management.

    Example:
        >>> class MyOptimizer(BaseClassicalOptimizer):
        ...     def optimize(self, objective, x0, gradient=None, **kwargs):
        ...         # Implementation here
        ...         pass
        >>>
        >>> optimizer = MyOptimizer(max_iterations=100)
        >>> result = optimizer.optimize(lambda x: x @ x, np.zeros(3))
    """

    def __init__(
        self,
        max_iterations: int = 1000,
        ftol: float = 1e-8,
        xtol: float = 1e-8,
        gtol: float = 1e-5,
        patience: int = 10,
        track_history: bool = True,
        callbacks: list[OptimizationCallback] | None = None,
        bounds: Bounds | None = None,
        constraints: list[ConstraintFunction] | None = None,
        verbose: bool = False,
    ):
        """
        Initialize the optimizer.

        Args:
            max_iterations: Maximum number of iterations.
            ftol: Function value tolerance for convergence.
            xtol: Solution tolerance for convergence.
            gtol: Gradient norm tolerance for convergence.
            patience: Number of iterations without improvement before stopping.
            track_history: Whether to track optimization history.
            callbacks: List of callbacks to call at each iteration.
            bounds: Variable bounds.
            constraints: List of constraint functions.
            verbose: Whether to print progress.
        """
        self.convergence_config = ConvergenceConfig(
            ftol=ftol,
            xtol=xtol,
            gtol=gtol,
            max_iterations=max_iterations,
            patience=patience,
        )
        self.track_history = track_history
        self.callback_manager = CallbackManager(callbacks)
        self.bounds = bounds
        self.constraints = constraints or []
        self.verbose = verbose

        self._n_function_evals = 0
        self._n_gradient_evals = 0

    @abstractmethod
    def optimize(
        self,
        objective: ObjectiveFunction,
        x0: NDArray[np.float64],
        gradient: GradientFunction | None = None,
        **kwargs: Any,
    ) -> ClassicalOptimizationResult:
        """
        Run the optimization.

        Args:
            objective: The objective function to minimize.
            x0: Initial guess.
            gradient: Optional gradient function.
            **kwargs: Additional optimizer-specific arguments.

        Returns:
            ClassicalOptimizationResult containing the optimization results.
        """
        ...

    def _evaluate_objective(self, objective: ObjectiveFunction, x: NDArray[np.float64]) -> float:
        """Evaluate objective and track function evaluations."""
        self._n_function_evals += 1
        return objective(x)

    def _evaluate_gradient(
        self, gradient: GradientFunction, x: NDArray[np.float64]
    ) -> NDArray[np.float64]:
        """Evaluate gradient and track gradient evaluations."""
        self._n_gradient_evals += 1
        return gradient(x)

    def _numerical_gradient(
        self,
        objective: ObjectiveFunction,
        x: NDArray[np.float64],
        eps: float = 1e-8,
    ) -> NDArray[np.float64]:
        """Compute numerical gradient using central differences."""
        grad = np.zeros_like(x)
        for i in range(len(x)):
            x_plus = x.copy()
            x_minus = x.copy()
            x_plus[i] += eps
            x_minus[i] -= eps
            grad[i] = (
                self._evaluate_objective(objective, x_plus)
                - self._evaluate_objective(objective, x_minus)
            ) / (2 * eps)
        return grad

    def _compute_constraint_violation(self, x: NDArray[np.float64]) -> float:
        """Compute total constraint violation."""
        if not self.constraints:
            return 0.0
        return sum(max(0.0, c(x)) for c in self.constraints)

    def _apply_bounds(self, x: NDArray[np.float64]) -> NDArray[np.float64]:
        """Apply bounds to the solution."""
        if self.bounds is not None:
            return self.bounds.clip(x)
        return x

    def _reset_counters(self) -> None:
        """Reset function and gradient evaluation counters."""
        self._n_function_evals = 0
        self._n_gradient_evals = 0

    def _log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            pass

    @property
    def name(self) -> str:
        """Return the optimizer name."""
        return self.__class__.__name__

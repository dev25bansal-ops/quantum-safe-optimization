"""
Gradient-based optimization algorithms.

This module provides gradient descent variants including vanilla GD,
momentum, Nesterov accelerated gradient, Adam, and AdaGrad, along with
various learning rate schedules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .base import (
    BaseClassicalOptimizer,
    Bounds,
    ClassicalOptimizationResult,
    ConstraintFunction,
    ConvergenceChecker,
    ConvergenceStatus,
    GradientFunction,
    ObjectiveFunction,
    OptimizationCallback,
    OptimizationHistory,
    OptimizationState,
)


class GDVariant(Enum):
    """Gradient descent variant types."""

    VANILLA = auto()
    MOMENTUM = auto()
    NESTEROV = auto()
    ADAM = auto()
    ADAGRAD = auto()
    RMSPROP = auto()
    ADAMW = auto()


class LRScheduleType(Enum):
    """Learning rate schedule types."""

    CONSTANT = auto()
    STEP_DECAY = auto()
    EXPONENTIAL = auto()
    COSINE_ANNEALING = auto()
    LINEAR_WARMUP = auto()
    REDUCE_ON_PLATEAU = auto()


@dataclass
class LRScheduleConfig:
    """Configuration for learning rate schedules."""

    schedule_type: LRScheduleType = LRScheduleType.CONSTANT
    initial_lr: float = 0.01
    decay_rate: float = 0.1
    decay_steps: int = 100
    min_lr: float = 1e-6
    warmup_steps: int = 0
    T_max: int = 1000
    patience: int = 10
    factor: float = 0.5


class LearningRateScheduler:
    """Learning rate scheduler with various decay strategies."""

    def __init__(self, config: LRScheduleConfig):
        self.config = config
        self._best_loss = float("inf")
        self._plateau_count = 0
        self._current_lr = config.initial_lr

    def get_lr(self, iteration: int, loss: float | None = None) -> float:
        """
        Get the learning rate for the current iteration.

        Args:
            iteration: Current iteration number.
            loss: Current loss value (used for reduce_on_plateau).

        Returns:
            Learning rate for this iteration.
        """
        if iteration < self.config.warmup_steps:
            warmup_factor = (iteration + 1) / self.config.warmup_steps
            return self.config.initial_lr * warmup_factor

        effective_iter = iteration - self.config.warmup_steps

        if self.config.schedule_type == LRScheduleType.CONSTANT:
            lr = self.config.initial_lr

        elif self.config.schedule_type == LRScheduleType.STEP_DECAY:
            n_decays = effective_iter // self.config.decay_steps
            lr = self.config.initial_lr * (self.config.decay_rate**n_decays)

        elif self.config.schedule_type == LRScheduleType.EXPONENTIAL:
            lr = self.config.initial_lr * (
                self.config.decay_rate ** (effective_iter / self.config.decay_steps)
            )

        elif self.config.schedule_type == LRScheduleType.COSINE_ANNEALING:
            lr = self.config.min_lr + 0.5 * (self.config.initial_lr - self.config.min_lr) * (
                1 + np.cos(np.pi * effective_iter / self.config.T_max)
            )

        elif self.config.schedule_type == LRScheduleType.LINEAR_WARMUP:
            remaining = self.config.T_max - self.config.warmup_steps
            if remaining > 0:
                lr = self.config.initial_lr * (1 - effective_iter / remaining)
            else:
                lr = self.config.initial_lr

        elif self.config.schedule_type == LRScheduleType.REDUCE_ON_PLATEAU:
            if loss is not None:
                if loss < self._best_loss - 1e-8:
                    self._best_loss = loss
                    self._plateau_count = 0
                else:
                    self._plateau_count += 1
                    if self._plateau_count >= self.config.patience:
                        self._current_lr *= self.config.factor
                        self._plateau_count = 0
            lr = self._current_lr

        else:
            lr = self.config.initial_lr

        return max(lr, self.config.min_lr)


class LineSearch:
    """Line search methods for step size selection."""

    @staticmethod
    def backtracking(
        objective: ObjectiveFunction,
        x: NDArray[np.float64],
        direction: NDArray[np.float64],
        gradient: NDArray[np.float64],
        fx: float,
        alpha: float = 1.0,
        rho: float = 0.5,
        c: float = 1e-4,
        max_iters: int = 20,
    ) -> tuple[float, float, int]:
        """
        Backtracking line search with Armijo condition.

        Args:
            objective: Objective function.
            x: Current point.
            direction: Search direction.
            gradient: Gradient at x.
            fx: Function value at x.
            alpha: Initial step size.
            rho: Step size reduction factor.
            c: Armijo condition constant.
            max_iters: Maximum iterations.

        Returns:
            Tuple of (step_size, new_fx, n_evals).
        """
        slope = np.dot(gradient, direction)
        n_evals = 0

        for _ in range(max_iters):
            x_new = x + alpha * direction
            fx_new = objective(x_new)
            n_evals += 1

            if fx_new <= fx + c * alpha * slope:
                return alpha, fx_new, n_evals

            alpha *= rho

        return alpha, objective(x + alpha * direction), n_evals + 1

    @staticmethod
    def wolfe(
        objective: ObjectiveFunction,
        gradient_fn: GradientFunction,
        x: NDArray[np.float64],
        direction: NDArray[np.float64],
        gradient: NDArray[np.float64],
        fx: float,
        alpha: float = 1.0,
        c1: float = 1e-4,
        c2: float = 0.9,
        max_iters: int = 20,
    ) -> tuple[float, float, int, int]:
        """
        Line search satisfying strong Wolfe conditions.

        Returns:
            Tuple of (step_size, new_fx, n_f_evals, n_g_evals).
        """
        alpha_lo, alpha_hi = 0.0, float("inf")
        n_f_evals, n_g_evals = 0, 0
        slope = np.dot(gradient, direction)

        for _ in range(max_iters):
            x_new = x + alpha * direction
            fx_new = objective(x_new)
            n_f_evals += 1

            if fx_new > fx + c1 * alpha * slope:
                alpha_hi = alpha
                alpha = (alpha_lo + alpha_hi) / 2
                continue

            grad_new = gradient_fn(x_new)
            n_g_evals += 1
            new_slope = np.dot(grad_new, direction)

            if abs(new_slope) <= -c2 * slope:
                return alpha, fx_new, n_f_evals, n_g_evals

            if new_slope >= 0:
                alpha_hi = alpha
            else:
                alpha_lo = alpha

            if alpha_hi < float("inf"):
                alpha = (alpha_lo + alpha_hi) / 2
            else:
                alpha *= 2

        return alpha, objective(x + alpha * direction), n_f_evals + 1, n_g_evals


@dataclass
class AdamState:
    """State for Adam optimizer."""

    m: NDArray[np.float64]
    v: NDArray[np.float64]
    t: int = 0


@dataclass
class MomentumState:
    """State for momentum-based optimizers."""

    velocity: NDArray[np.float64]


@dataclass
class AdaGradState:
    """State for AdaGrad optimizer."""

    accumulated_grad_sq: NDArray[np.float64]


@dataclass
class RMSPropState:
    """State for RMSProp optimizer."""

    cache: NDArray[np.float64]


class GradientDescentOptimizer(BaseClassicalOptimizer):
    """
    Gradient descent optimizer with multiple variants and learning rate schedules.

    Supports vanilla gradient descent, momentum, Nesterov accelerated gradient,
    Adam, AdaGrad, RMSProp, and AdamW optimizers.

    Example:
        >>> import numpy as np
        >>> optimizer = GradientDescentOptimizer(
        ...     variant=GDVariant.ADAM,
        ...     learning_rate=0.001,
        ...     lr_schedule=LRScheduleType.COSINE_ANNEALING,
        ...     max_iterations=1000
        ... )
        >>> def objective(x):
        ...     return np.sum(x**2)
        >>> def gradient(x):
        ...     return 2 * x
        >>> result = optimizer.optimize(objective, np.ones(10), gradient=gradient)
        >>> print(f"Optimal value: {result.fx:.6f}")
    """

    def __init__(
        self,
        variant: GDVariant = GDVariant.ADAM,
        learning_rate: float = 0.01,
        lr_schedule: LRScheduleType = LRScheduleType.CONSTANT,
        lr_config: LRScheduleConfig | None = None,
        momentum: float = 0.9,
        beta1: float = 0.9,
        beta2: float = 0.999,
        epsilon: float = 1e-8,
        weight_decay: float = 0.0,
        use_line_search: bool = False,
        line_search_type: str = "backtracking",
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
        Initialize gradient descent optimizer.

        Args:
            variant: GD variant (VANILLA, MOMENTUM, NESTEROV, ADAM, ADAGRAD, RMSPROP, ADAMW).
            learning_rate: Initial learning rate.
            lr_schedule: Learning rate schedule type.
            lr_config: Custom learning rate schedule configuration.
            momentum: Momentum coefficient (for MOMENTUM/NESTEROV).
            beta1: Adam first moment decay rate.
            beta2: Adam second moment decay rate.
            epsilon: Small constant for numerical stability.
            weight_decay: L2 regularization coefficient (for ADAMW).
            use_line_search: Whether to use line search for step size.
            line_search_type: Type of line search ("backtracking" or "wolfe").
            max_iterations: Maximum iterations.
            ftol: Function tolerance.
            xtol: Solution tolerance.
            gtol: Gradient tolerance.
            patience: Early stopping patience.
            track_history: Whether to track optimization history.
            callbacks: Optimization callbacks.
            bounds: Variable bounds.
            constraints: Constraint functions.
            verbose: Whether to print progress.
        """
        super().__init__(
            max_iterations=max_iterations,
            ftol=ftol,
            xtol=xtol,
            gtol=gtol,
            patience=patience,
            track_history=track_history,
            callbacks=callbacks,
            bounds=bounds,
            constraints=constraints,
            verbose=verbose,
        )
        self.variant = variant
        self.learning_rate = learning_rate
        self.momentum = momentum
        self.beta1 = beta1
        self.beta2 = beta2
        self.epsilon = epsilon
        self.weight_decay = weight_decay
        self.use_line_search = use_line_search
        self.line_search_type = line_search_type

        if lr_config is not None:
            self.lr_config = lr_config
        else:
            self.lr_config = LRScheduleConfig(
                schedule_type=lr_schedule,
                initial_lr=learning_rate,
                T_max=max_iterations,
            )

    def optimize(
        self,
        objective: ObjectiveFunction,
        x0: NDArray[np.float64],
        gradient: GradientFunction | None = None,
        **kwargs: Any,
    ) -> ClassicalOptimizationResult:
        """
        Run gradient descent optimization.

        Args:
            objective: Objective function to minimize.
            x0: Initial guess.
            gradient: Gradient function (computed numerically if not provided).
            **kwargs: Additional arguments (unused).

        Returns:
            ClassicalOptimizationResult with optimization results.
        """
        self._reset_counters()
        x = self._apply_bounds(x0.copy().astype(np.float64))
        n = len(x)

        grad_fn = (
            gradient if gradient is not None else lambda x: self._numerical_gradient(objective, x)
        )

        state = self._init_optimizer_state(n)
        lr_scheduler = LearningRateScheduler(self.lr_config)
        convergence_checker = ConvergenceChecker(self.convergence_config)
        history = OptimizationHistory()

        fx = self._evaluate_objective(objective, x)
        g = self._evaluate_gradient(grad_fn, x) if gradient else grad_fn(x)
        if gradient is None:
            self._n_gradient_evals = 0

        status = ConvergenceStatus.NOT_CONVERGED

        for iteration in range(self.convergence_config.max_iterations):
            lr = lr_scheduler.get_lr(iteration, fx)

            step, state = self._compute_step(g, state, lr)

            if self.variant == GDVariant.NESTEROV:
                x_lookahead = x - self.momentum * state.velocity
                g = (
                    self._evaluate_gradient(grad_fn, x_lookahead)
                    if gradient
                    else grad_fn(x_lookahead)
                )

            if self.use_line_search and self.variant in (GDVariant.VANILLA, GDVariant.MOMENTUM):
                direction = -g
                if self.line_search_type == "wolfe" and gradient is not None:
                    alpha, fx_new, nf, ng = LineSearch.wolfe(
                        objective, grad_fn, x, direction, g, fx
                    )
                    self._n_function_evals += nf
                    self._n_gradient_evals += ng
                else:
                    alpha, fx_new, nf = LineSearch.backtracking(objective, x, direction, g, fx)
                    self._n_function_evals += nf
                step = alpha * direction

            x_new = self._apply_bounds(x + step)
            fx_new = self._evaluate_objective(objective, x_new)
            g = self._evaluate_gradient(grad_fn, x_new) if gradient else grad_fn(x_new)

            opt_state = OptimizationState(
                iteration=iteration,
                x=x_new,
                fx=fx_new,
                gradient=g,
                step_size=np.linalg.norm(step),
                constraint_violation=self._compute_constraint_violation(x_new),
            )

            if self.track_history:
                history.append(opt_state)

            if self.callback_manager.notify(opt_state):
                status = ConvergenceStatus.EARLY_STOPPED
                break

            status = convergence_checker.check(iteration, x_new, fx_new, g)
            if status != ConvergenceStatus.NOT_CONVERGED:
                break

            if self.verbose and iteration % 100 == 0:
                self._log(f"Iter {iteration}: fx={fx_new:.6e}, |g|={np.linalg.norm(g):.6e}")

            x = x_new
            fx = fx_new

        success = status in (
            ConvergenceStatus.CONVERGED_FTOL,
            ConvergenceStatus.CONVERGED_XTOL,
            ConvergenceStatus.CONVERGED_GTOL,
        )

        return ClassicalOptimizationResult(
            x=x,
            fx=fx,
            success=success,
            status=status,
            message=self._get_status_message(status),
            n_iterations=iteration + 1,
            n_function_evals=self._n_function_evals,
            n_gradient_evals=self._n_gradient_evals,
            history=history,
            constraint_violation=self._compute_constraint_violation(x),
        )

    def _init_optimizer_state(self, n: int) -> Any:
        """Initialize optimizer-specific state."""
        if self.variant in (GDVariant.MOMENTUM, GDVariant.NESTEROV):
            return MomentumState(velocity=np.zeros(n))
        elif self.variant in (GDVariant.ADAM, GDVariant.ADAMW):
            return AdamState(m=np.zeros(n), v=np.zeros(n), t=0)
        elif self.variant == GDVariant.ADAGRAD:
            return AdaGradState(accumulated_grad_sq=np.zeros(n))
        elif self.variant == GDVariant.RMSPROP:
            return RMSPropState(cache=np.zeros(n))
        return None

    def _compute_step(
        self, g: NDArray[np.float64], state: Any, lr: float
    ) -> tuple[NDArray[np.float64], Any]:
        """Compute the update step based on variant."""
        if self.variant == GDVariant.VANILLA:
            return -lr * g, state

        elif self.variant == GDVariant.MOMENTUM:
            state.velocity = self.momentum * state.velocity - lr * g
            return state.velocity, state

        elif self.variant == GDVariant.NESTEROV:
            state.velocity = self.momentum * state.velocity - lr * g
            return state.velocity, state

        elif self.variant == GDVariant.ADAM:
            state.t += 1
            state.m = self.beta1 * state.m + (1 - self.beta1) * g
            state.v = self.beta2 * state.v + (1 - self.beta2) * (g**2)
            m_hat = state.m / (1 - self.beta1**state.t)
            v_hat = state.v / (1 - self.beta2**state.t)
            step = -lr * m_hat / (np.sqrt(v_hat) + self.epsilon)
            return step, state

        elif self.variant == GDVariant.ADAMW:
            state.t += 1
            state.m = self.beta1 * state.m + (1 - self.beta1) * g
            state.v = self.beta2 * state.v + (1 - self.beta2) * (g**2)
            m_hat = state.m / (1 - self.beta1**state.t)
            v_hat = state.v / (1 - self.beta2**state.t)
            step = -lr * (m_hat / (np.sqrt(v_hat) + self.epsilon))
            return step, state

        elif self.variant == GDVariant.ADAGRAD:
            state.accumulated_grad_sq += g**2
            step = -lr * g / (np.sqrt(state.accumulated_grad_sq) + self.epsilon)
            return step, state

        elif self.variant == GDVariant.RMSPROP:
            state.cache = self.beta2 * state.cache + (1 - self.beta2) * (g**2)
            step = -lr * g / (np.sqrt(state.cache) + self.epsilon)
            return step, state

        return -lr * g, state

    def _get_status_message(self, status: ConvergenceStatus) -> str:
        """Get human-readable status message."""
        messages = {
            ConvergenceStatus.CONVERGED_FTOL: "Converged: function tolerance reached",
            ConvergenceStatus.CONVERGED_XTOL: "Converged: solution tolerance reached",
            ConvergenceStatus.CONVERGED_GTOL: "Converged: gradient tolerance reached",
            ConvergenceStatus.MAX_ITERATIONS: "Maximum iterations reached",
            ConvergenceStatus.EARLY_STOPPED: "Early stopped by callback",
            ConvergenceStatus.NOT_CONVERGED: "Not converged",
            ConvergenceStatus.FAILED: "Optimization failed",
        }
        return messages.get(status, "Unknown status")

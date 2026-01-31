"""
Optimization problem domain models.

Defines the core structures for representing optimization problems including
variables, constraints, and problem metadata.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable
from uuid import UUID, uuid4


class VariableType(Enum):
    """Types of optimization variables."""

    CONTINUOUS = "continuous"
    DISCRETE = "discrete"
    BINARY = "binary"


class ConstraintType(Enum):
    """Types of optimization constraints."""

    EQUALITY = "equality"
    INEQUALITY_LE = "inequality_le"  # Less than or equal
    INEQUALITY_GE = "inequality_ge"  # Greater than or equal


@dataclass(frozen=True)
class Variable:
    """
    Represents an optimization variable.

    Attributes:
        name: Unique name identifying the variable.
        var_type: Type of the variable (continuous, discrete, binary).
        lower_bound: Lower bound of the variable domain.
        upper_bound: Upper bound of the variable domain.
        initial_value: Optional initial value for the optimizer.
        discrete_values: For discrete variables, the set of allowed values.
    """

    name: str
    var_type: VariableType = VariableType.CONTINUOUS
    lower_bound: float | None = None
    upper_bound: float | None = None
    initial_value: float | None = None
    discrete_values: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        """Validate variable configuration."""
        if self.var_type == VariableType.BINARY:
            if self.lower_bound is not None and self.lower_bound != 0:
                raise ValueError("Binary variables must have lower_bound=0")
            if self.upper_bound is not None and self.upper_bound != 1:
                raise ValueError("Binary variables must have upper_bound=1")
        if self.var_type == VariableType.DISCRETE and not self.discrete_values:
            raise ValueError("Discrete variables must specify discrete_values")
        if (
            self.lower_bound is not None
            and self.upper_bound is not None
            and self.lower_bound > self.upper_bound
        ):
            raise ValueError("lower_bound cannot exceed upper_bound")

    def is_bounded(self) -> bool:
        """Check if the variable has finite bounds."""
        return self.lower_bound is not None and self.upper_bound is not None


@dataclass(frozen=True)
class Constraint:
    """
    Represents an optimization constraint.

    For equality constraints: g(x) = 0
    For inequality_le: g(x) <= 0
    For inequality_ge: g(x) >= 0

    Attributes:
        name: Unique name identifying the constraint.
        constraint_type: Type of constraint (equality or inequality).
        expression: A callable that computes g(x) given variable values.
        tolerance: Tolerance for constraint satisfaction.
    """

    name: str
    constraint_type: ConstraintType
    expression: Callable[[dict[str, float]], float]
    tolerance: float = 1e-6

    def evaluate(self, variables: dict[str, float]) -> float:
        """
        Evaluate the constraint function at given variable values.

        Args:
            variables: Dictionary mapping variable names to their values.

        Returns:
            The constraint function value g(x).
        """
        return self.expression(variables)

    def is_satisfied(self, variables: dict[str, float]) -> bool:
        """
        Check if the constraint is satisfied.

        Args:
            variables: Dictionary mapping variable names to their values.

        Returns:
            True if the constraint is satisfied within tolerance.
        """
        value = self.evaluate(variables)
        if self.constraint_type == ConstraintType.EQUALITY:
            return abs(value) <= self.tolerance
        elif self.constraint_type == ConstraintType.INEQUALITY_LE:
            return value <= self.tolerance
        else:  # INEQUALITY_GE
            return value >= -self.tolerance


@dataclass(frozen=True)
class ProblemMetadata:
    """
    Metadata associated with an optimization problem.

    Attributes:
        id: Unique identifier for the problem.
        name: Human-readable problem name.
        description: Detailed problem description.
        created_at: Timestamp of problem creation.
        tags: Tags for categorization and search.
        owner_id: ID of the problem owner/creator.
        custom_data: Additional custom metadata.
    """

    id: UUID = field(default_factory=uuid4)
    name: str = ""
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    tags: tuple[str, ...] = ()
    owner_id: str | None = None
    custom_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationProblem:
    """
    Represents a complete optimization problem.

    An optimization problem consists of:
    - An objective function to minimize (or maximize)
    - Decision variables with bounds
    - Constraints that must be satisfied
    - Problem metadata

    Attributes:
        objective: The objective function f(x) to optimize.
        variables: List of optimization variables.
        constraints: List of constraints.
        metadata: Problem metadata.
        minimize: If True, minimize the objective; otherwise maximize.
        gradient: Optional gradient function for gradient-based methods.
        hessian: Optional Hessian function for second-order methods.
    """

    objective: Callable[[dict[str, float]], float]
    variables: list[Variable]
    constraints: list[Constraint] = field(default_factory=list)
    metadata: ProblemMetadata = field(default_factory=ProblemMetadata)
    minimize: bool = True
    gradient: Callable[[dict[str, float]], dict[str, float]] | None = None
    hessian: (
        Callable[[dict[str, float]], dict[str, dict[str, float]]] | None
    ) = None

    def __post_init__(self) -> None:
        """Validate problem configuration."""
        if not self.variables:
            raise ValueError("Problem must have at least one variable")
        var_names = [v.name for v in self.variables]
        if len(var_names) != len(set(var_names)):
            raise ValueError("Variable names must be unique")
        constraint_names = [c.name for c in self.constraints]
        if len(constraint_names) != len(set(constraint_names)):
            raise ValueError("Constraint names must be unique")

    @property
    def num_variables(self) -> int:
        """Return the number of variables."""
        return len(self.variables)

    @property
    def num_constraints(self) -> int:
        """Return the number of constraints."""
        return len(self.constraints)

    @property
    def variable_names(self) -> list[str]:
        """Return list of variable names."""
        return [v.name for v in self.variables]

    def evaluate_objective(self, values: dict[str, float]) -> float:
        """
        Evaluate the objective function.

        Args:
            values: Dictionary mapping variable names to their values.

        Returns:
            The objective function value.
        """
        return self.objective(values)

    def evaluate(self, values: list[float] | dict[str, float]) -> float:
        """
        Evaluate the objective function with list or dict input.

        Args:
            values: Either a list of values (in variable order) or a dict.

        Returns:
            The objective function value.
        """
        if isinstance(values, dict):
            return self.objective(values)
        # Convert list to dict using variable names
        value_dict = {
            self.variables[i].name: values[i] for i in range(len(values))
        }
        return self.objective(value_dict)

    def check_constraints(self, values: dict[str, float]) -> dict[str, bool]:
        """
        Check which constraints are satisfied.

        Args:
            values: Dictionary mapping variable names to their values.

        Returns:
            Dictionary mapping constraint names to satisfaction status.
        """
        return {c.name: c.is_satisfied(values) for c in self.constraints}

    def is_feasible(self, values: dict[str, float]) -> bool:
        """
        Check if a solution is feasible (satisfies all constraints).

        Args:
            values: Dictionary mapping variable names to their values.

        Returns:
            True if all constraints are satisfied.
        """
        return all(self.check_constraints(values).values())

    def get_bounds(self) -> list[tuple[float | None, float | None]]:
        """
        Get bounds for all variables in order.

        Returns:
            List of (lower, upper) bound tuples.
        """
        return [(v.lower_bound, v.upper_bound) for v in self.variables]

    def get_bounds_array(self) -> "np.ndarray":
        """
        Get bounds as numpy array of shape (n_vars, 2).

        Returns:
            Array with lower bounds in column 0, upper bounds in column 1.
        """
        import numpy as np
        bounds = self.get_bounds()
        return np.array([
            [lb if lb is not None else -np.inf, ub if ub is not None else np.inf]
            for lb, ub in bounds
        ])

    def get_initial_point(self) -> dict[str, float]:
        """
        Get initial point from variable initial values.

        Returns:
            Dictionary mapping variable names to initial values.
            Uses 0.0 for variables without specified initial values.
        """
        return {
            v.name: v.initial_value if v.initial_value is not None else 0.0
            for v in self.variables
        }

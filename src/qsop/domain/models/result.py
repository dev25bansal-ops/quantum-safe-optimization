"""
Result domain models.

Defines structures for optimization results and quantum execution results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ConvergenceInfo:
    """
    Information about optimization convergence.

    Attributes:
        converged: Whether the optimization converged.
        final_gradient_norm: Norm of the gradient at the solution.
        constraint_violation: Maximum constraint violation.
        iterations_to_converge: Number of iterations to reach convergence.
        reason: Textual description of termination reason.
    """

    converged: bool
    final_gradient_norm: float | None = None
    constraint_violation: float | None = None
    iterations_to_converge: int | None = None
    reason: str = ""


@dataclass(frozen=True)
class OptimizationResult:
    """
    Result of an optimization run.

    Attributes:
        optimal_value: The optimal objective function value found.
        optimal_parameters: Dictionary of optimal variable values.
        iterations: Number of iterations performed.
        function_evaluations: Number of objective function evaluations.
        gradient_evaluations: Number of gradient evaluations.
        convergence: Convergence information.
        objective_history: History of objective values per iteration.
        parameter_history: History of parameter values per iteration.
        constraint_values: Final constraint function values.
        algorithm: Name of the algorithm used.
        wall_time_seconds: Wall clock time for optimization.
        metadata: Additional result metadata.
    """

    optimal_value: float
    optimal_parameters: dict[str, float]
    iterations: int
    function_evaluations: int = 0
    gradient_evaluations: int = 0
    convergence: ConvergenceInfo = field(
        default_factory=lambda: ConvergenceInfo(converged=False)
    )
    objective_history: tuple[float, ...] = ()
    parameter_history: tuple[dict[str, float], ...] = ()
    constraint_values: dict[str, float] = field(default_factory=dict)
    algorithm: str = ""
    wall_time_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_feasible(self, tolerance: float = 1e-6) -> bool:
        """
        Check if the solution is feasible.

        Args:
            tolerance: Tolerance for constraint satisfaction.

        Returns:
            True if all constraints are satisfied within tolerance.
        """
        if not self.constraint_values:
            return True
        return all(abs(v) <= tolerance for v in self.constraint_values.values())


@dataclass(frozen=True)
class MeasurementResult:
    """
    Result of a single quantum circuit measurement.

    Attributes:
        bitstring: The measured bitstring.
        count: Number of times this bitstring was observed.
        probability: Estimated probability of this outcome.
    """

    bitstring: str
    count: int
    probability: float


@dataclass(frozen=True)
class QuantumExecutionResult:
    """
    Result of quantum circuit execution.

    Attributes:
        measurements: List of measurement results.
        counts: Raw measurement counts dictionary.
        expectation_values: Computed expectation values for observables.
        num_qubits: Number of qubits in the circuit.
        shots: Number of shots executed.
        execution_time_seconds: Time taken for execution.
        backend_name: Name of the backend used.
        job_id: Backend job identifier.
        circuit_depth: Depth of the executed circuit.
        transpiled_depth: Depth after transpilation.
        timestamp: When the execution occurred.
        metadata: Additional execution metadata.
    """

    measurements: tuple[MeasurementResult, ...]
    counts: dict[str, int]
    expectation_values: dict[str, float] = field(default_factory=dict)
    num_qubits: int = 0
    shots: int = 0
    execution_time_seconds: float = 0.0
    backend_name: str = ""
    job_id: str = ""
    circuit_depth: int = 0
    transpiled_depth: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_counts(self) -> int:
        """Return total number of measurement counts."""
        return sum(self.counts.values())

    @property
    def num_unique_outcomes(self) -> int:
        """Return number of unique measurement outcomes."""
        return len(self.counts)

    def get_most_probable(self, n: int = 1) -> list[MeasurementResult]:
        """
        Get the n most probable measurement outcomes.

        Args:
            n: Number of outcomes to return.

        Returns:
            List of measurement results sorted by probability descending.
        """
        sorted_measurements = sorted(
            self.measurements, key=lambda m: m.probability, reverse=True
        )
        return list(sorted_measurements[:n])

    def get_probability(self, bitstring: str) -> float:
        """
        Get the probability of a specific bitstring.

        Args:
            bitstring: The bitstring to look up.

        Returns:
            Probability of the bitstring, or 0 if not observed.
        """
        for m in self.measurements:
            if m.bitstring == bitstring:
                return m.probability
        return 0.0

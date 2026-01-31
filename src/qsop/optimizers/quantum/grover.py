"""Grover-based optimizer for optimization problems."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol, Sequence

import numpy as np
from numpy.typing import NDArray
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.circuit import Gate
from qiskit.circuit.library import GroverOperator, MCMT, ZGate


@dataclass
class GroverProblem:
    """Optimization problem for Grover search.
    
    Attributes:
        num_qubits: Number of decision variable qubits.
        objective: Objective function mapping bitstring to cost.
        threshold: Solutions with cost <= threshold are marked.
        is_minimization: If True, mark solutions below threshold.
    """
    
    num_qubits: int
    objective: Callable[[str], float]
    threshold: float | None = None
    is_minimization: bool = True

    def evaluate(self, bitstring: str) -> float:
        """Evaluate objective function for a bitstring."""
        return self.objective(bitstring)

    def is_solution(self, bitstring: str) -> bool:
        """Check if bitstring is a valid solution."""
        if self.threshold is None:
            return False
        cost = self.evaluate(bitstring)
        if self.is_minimization:
            return cost <= self.threshold
        return cost >= self.threshold


@dataclass
class GroverResult:
    """Result from Grover optimization.
    
    Attributes:
        best_bitstring: Best solution found.
        best_value: Objective value of best solution.
        counts: Final measurement counts.
        num_iterations: Total Grover iterations used.
        solutions_found: All solutions meeting threshold.
    """
    
    best_bitstring: str
    best_value: float
    counts: dict[str, int]
    num_iterations: int
    solutions_found: list[tuple[str, float]] = field(default_factory=list)


class QuantumBackend(Protocol):
    """Protocol for quantum backends."""
    
    def run(
        self,
        circuit: QuantumCircuit,
        shots: int = 1024,
    ) -> dict[str, int]:
        """Execute circuit and return measurement counts."""
        ...


class GroverOptimizer:
    """Grover-based optimizer using amplitude amplification.
    
    Uses Grover's algorithm to search for optimal or near-optimal
    solutions to combinatorial optimization problems.
    
    Example:
        >>> def objective(x):
        ...     return sum(int(b) for b in x)  # count ones
        >>> problem = GroverProblem(num_qubits=4, objective=objective, threshold=1)
        >>> optimizer = GroverOptimizer(backend=backend)
        >>> result = optimizer.optimize(problem)
    """
    
    def __init__(
        self,
        backend: QuantumBackend | None = None,
        max_iterations: int | None = None,
        adaptive: bool = True,
        seed: int | None = None,
    ):
        """Initialize Grover optimizer.
        
        Args:
            backend: Quantum backend for circuit execution.
            max_iterations: Maximum Grover iterations (None for auto).
            adaptive: Use adaptive iteration count.
            seed: Random seed for reproducibility.
        """
        self.backend = backend
        self.max_iterations = max_iterations
        self.adaptive = adaptive
        self.rng = np.random.default_rng(seed)

    def build_phase_oracle(
        self,
        problem: GroverProblem,
        marked_states: list[str] | None = None,
    ) -> QuantumCircuit:
        """Build phase oracle that marks solution states.
        
        Args:
            problem: Optimization problem.
            marked_states: Explicit list of states to mark (optional).
            
        Returns:
            Oracle circuit.
        """
        n = problem.num_qubits
        oracle = QuantumCircuit(n, name="Oracle")
        
        if marked_states is None:
            marked_states = []
            for i in range(2**n):
                bitstring = format(i, f"0{n}b")
                if problem.is_solution(bitstring):
                    marked_states.append(bitstring)
        
        for state in marked_states:
            for i, bit in enumerate(state[::-1]):
                if bit == "0":
                    oracle.x(i)
            
            if n == 1:
                oracle.z(0)
            elif n == 2:
                oracle.cz(0, 1)
            else:
                oracle.h(n - 1)
                oracle.mcx(list(range(n - 1)), n - 1)
                oracle.h(n - 1)
            
            for i, bit in enumerate(state[::-1]):
                if bit == "0":
                    oracle.x(i)
        
        return oracle

    def build_objective_oracle(
        self,
        problem: GroverProblem,
        threshold: float,
        num_ancilla: int = 4,
    ) -> QuantumCircuit:
        """Build oracle based on objective function comparison.
        
        Uses ancilla qubits to compute f(x) <= threshold.
        This is a simplified implementation; full arithmetic
        circuits would be more efficient.
        
        Args:
            problem: Optimization problem.
            threshold: Threshold for marking.
            num_ancilla: Number of ancilla qubits for computation.
            
        Returns:
            Oracle circuit.
        """
        marked_states = []
        for i in range(2**problem.num_qubits):
            bitstring = format(i, f"0{problem.num_qubits}b")
            cost = problem.evaluate(bitstring)
            if problem.is_minimization:
                if cost <= threshold:
                    marked_states.append(bitstring)
            else:
                if cost >= threshold:
                    marked_states.append(bitstring)
        
        return self.build_phase_oracle(problem, marked_states)

    def build_diffusion_operator(self, num_qubits: int) -> QuantumCircuit:
        """Build Grover diffusion operator.
        
        Args:
            num_qubits: Number of qubits.
            
        Returns:
            Diffusion circuit.
        """
        diffusion = QuantumCircuit(num_qubits, name="Diffusion")
        
        diffusion.h(range(num_qubits))
        diffusion.x(range(num_qubits))
        
        if num_qubits == 1:
            diffusion.z(0)
        elif num_qubits == 2:
            diffusion.cz(0, 1)
        else:
            diffusion.h(num_qubits - 1)
            diffusion.mcx(list(range(num_qubits - 1)), num_qubits - 1)
            diffusion.h(num_qubits - 1)
        
        diffusion.x(range(num_qubits))
        diffusion.h(range(num_qubits))
        
        return diffusion

    def build_grover_circuit(
        self,
        problem: GroverProblem,
        num_iterations: int,
        oracle: QuantumCircuit | None = None,
    ) -> QuantumCircuit:
        """Build complete Grover search circuit.
        
        Args:
            problem: Optimization problem.
            num_iterations: Number of Grover iterations.
            oracle: Optional pre-built oracle.
            
        Returns:
            Grover search circuit.
        """
        n = problem.num_qubits
        circuit = QuantumCircuit(n, n)
        
        circuit.h(range(n))
        
        if oracle is None:
            oracle = self.build_phase_oracle(problem)
        diffusion = self.build_diffusion_operator(n)
        
        for _ in range(num_iterations):
            circuit.compose(oracle, inplace=True)
            circuit.compose(diffusion, inplace=True)
        
        circuit.measure(range(n), range(n))
        
        return circuit

    def estimate_num_solutions(
        self,
        problem: GroverProblem,
    ) -> int:
        """Estimate number of solutions by classical evaluation.
        
        Args:
            problem: Optimization problem.
            
        Returns:
            Number of solutions.
        """
        count = 0
        for i in range(2**problem.num_qubits):
            bitstring = format(i, f"0{problem.num_qubits}b")
            if problem.is_solution(bitstring):
                count += 1
        return count

    def compute_optimal_iterations(
        self,
        num_qubits: int,
        num_solutions: int,
    ) -> int:
        """Compute optimal number of Grover iterations.
        
        Args:
            num_qubits: Number of qubits.
            num_solutions: Number of marked solutions.
            
        Returns:
            Optimal iteration count.
        """
        if num_solutions == 0:
            return 0
        
        N = 2**num_qubits
        if num_solutions >= N:
            return 0
        
        theta = np.arcsin(np.sqrt(num_solutions / N))
        optimal = int(np.round(np.pi / (4 * theta) - 0.5))
        
        return max(1, optimal)

    def adaptive_search(
        self,
        problem: GroverProblem,
        shots: int = 1024,
    ) -> tuple[dict[str, int], int]:
        """Run adaptive Grover search with unknown number of solutions.
        
        Uses exponentially increasing iteration counts.
        
        Args:
            problem: Optimization problem.
            shots: Number of measurement shots.
            
        Returns:
            Tuple of (counts, total_iterations).
        """
        if self.backend is None:
            raise ValueError("Backend must be set")
        
        n = problem.num_qubits
        max_iter = self.max_iterations or int(np.ceil(np.sqrt(2**n)))
        
        m = 1
        total_iterations = 0
        best_counts: dict[str, int] = {}
        
        while m <= max_iter:
            k = self.rng.integers(1, m + 1)
            circuit = self.build_grover_circuit(problem, k)
            counts = self.backend.run(circuit, shots=shots)
            total_iterations += k
            
            for bitstring, count in counts.items():
                if problem.is_solution(bitstring):
                    best_counts[bitstring] = best_counts.get(bitstring, 0) + count
            
            if best_counts:
                break
            
            m = min(int(m * 1.5) + 1, max_iter)
        
        if not best_counts:
            best_counts = counts
        
        return best_counts, total_iterations

    def fixed_search(
        self,
        problem: GroverProblem,
        num_iterations: int,
        shots: int = 1024,
    ) -> dict[str, int]:
        """Run Grover search with fixed iteration count.
        
        Args:
            problem: Optimization problem.
            num_iterations: Number of Grover iterations.
            shots: Number of measurement shots.
            
        Returns:
            Measurement counts.
        """
        if self.backend is None:
            raise ValueError("Backend must be set")
        
        circuit = self.build_grover_circuit(problem, num_iterations)
        return self.backend.run(circuit, shots=shots)

    def optimize(
        self,
        problem: GroverProblem,
        shots: int = 1024,
        threshold_search: bool = True,
    ) -> GroverResult:
        """Run Grover optimization.
        
        Args:
            problem: Optimization problem.
            shots: Number of measurement shots.
            threshold_search: Adaptively search for optimal threshold.
            
        Returns:
            GroverResult with best solution found.
        """
        if self.backend is None:
            raise ValueError("Backend must be set")
        
        n = problem.num_qubits
        
        if threshold_search and problem.threshold is None:
            return self._threshold_based_search(problem, shots)
        
        if self.adaptive:
            counts, total_iterations = self.adaptive_search(problem, shots)
        else:
            num_solutions = self.estimate_num_solutions(problem)
            if num_solutions > 0:
                num_iter = self.compute_optimal_iterations(n, num_solutions)
            else:
                num_iter = int(np.ceil(np.sqrt(2**n)))
            
            if self.max_iterations:
                num_iter = min(num_iter, self.max_iterations)
            
            counts = self.fixed_search(problem, num_iter, shots)
            total_iterations = num_iter
        
        solutions_found: list[tuple[str, float]] = []
        best_bitstring = ""
        best_value = float("inf") if problem.is_minimization else float("-inf")
        
        for bitstring, count in counts.items():
            value = problem.evaluate(bitstring)
            
            if problem.threshold is not None and problem.is_solution(bitstring):
                solutions_found.append((bitstring, value))
            
            if problem.is_minimization:
                if value < best_value:
                    best_value = value
                    best_bitstring = bitstring
            else:
                if value > best_value:
                    best_value = value
                    best_bitstring = bitstring
        
        if not best_bitstring:
            best_bitstring = max(counts, key=lambda k: counts[k])
            best_value = problem.evaluate(best_bitstring)
        
        return GroverResult(
            best_bitstring=best_bitstring,
            best_value=best_value,
            counts=counts,
            num_iterations=total_iterations,
            solutions_found=solutions_found,
        )

    def _threshold_based_search(
        self,
        problem: GroverProblem,
        shots: int,
    ) -> GroverResult:
        """Search for optimal solution by adaptive threshold.
        
        Repeatedly runs Grover search with decreasing thresholds.
        
        Args:
            problem: Optimization problem.
            shots: Number of measurement shots.
            
        Returns:
            GroverResult with best solution found.
        """
        n = problem.num_qubits
        all_values = []
        for i in range(min(2**n, 1000)):
            if i < 2**n:
                bitstring = format(i, f"0{n}b")
                all_values.append(problem.evaluate(bitstring))
        
        if not all_values:
            return GroverResult(
                best_bitstring="0" * n,
                best_value=problem.evaluate("0" * n),
                counts={},
                num_iterations=0,
            )
        
        if problem.is_minimization:
            threshold = np.median(all_values)
        else:
            threshold = np.median(all_values)
        
        best_bitstring = ""
        best_value = float("inf") if problem.is_minimization else float("-inf")
        total_iterations = 0
        all_counts: dict[str, int] = {}
        solutions_found: list[tuple[str, float]] = []
        
        for _ in range(int(np.log2(max(1, len(set(all_values)))))):
            search_problem = GroverProblem(
                num_qubits=n,
                objective=problem.objective,
                threshold=threshold,
                is_minimization=problem.is_minimization,
            )
            
            if self.adaptive:
                counts, iters = self.adaptive_search(search_problem, shots // 2)
            else:
                num_solutions = self.estimate_num_solutions(search_problem)
                if num_solutions > 0:
                    num_iter = self.compute_optimal_iterations(n, num_solutions)
                    num_iter = min(num_iter, self.max_iterations or num_iter)
                    counts = self.fixed_search(search_problem, num_iter, shots // 2)
                    iters = num_iter
                else:
                    break
            
            total_iterations += iters
            
            for bitstring, count in counts.items():
                all_counts[bitstring] = all_counts.get(bitstring, 0) + count
                value = problem.evaluate(bitstring)
                
                if problem.is_minimization:
                    if value < best_value:
                        best_value = value
                        best_bitstring = bitstring
                    if value <= threshold:
                        solutions_found.append((bitstring, value))
                        threshold = value - 0.001
                else:
                    if value > best_value:
                        best_value = value
                        best_bitstring = bitstring
                    if value >= threshold:
                        solutions_found.append((bitstring, value))
                        threshold = value + 0.001
        
        if not best_bitstring:
            best_bitstring = "0" * n
            best_value = problem.evaluate(best_bitstring)
        
        return GroverResult(
            best_bitstring=best_bitstring,
            best_value=best_value,
            counts=all_counts,
            num_iterations=total_iterations,
            solutions_found=solutions_found,
        )

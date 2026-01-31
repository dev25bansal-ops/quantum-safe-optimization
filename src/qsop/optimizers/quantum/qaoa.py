"""QAOA (Quantum Approximate Optimization Algorithm) optimizer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Protocol, Sequence

import numpy as np
from numpy.typing import NDArray
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter


class ParameterInitStrategy(Enum):
    """Parameter initialization strategies for QAOA."""
    
    RANDOM = "random"
    HEURISTIC = "heuristic"
    FIXED = "fixed"
    INTERPOLATION = "interpolation"


@dataclass
class QAOAProblem:
    """Represents a combinatorial optimization problem for QAOA.
    
    Attributes:
        num_qubits: Number of qubits (decision variables).
        cost_terms: List of (coefficient, qubit_indices) for cost Hamiltonian.
        linear_terms: List of (coefficient, qubit_index) for linear Z terms.
        constant: Constant offset in the cost function.
    """
    
    num_qubits: int
    cost_terms: list[tuple[float, tuple[int, ...]]] = field(default_factory=list)
    linear_terms: list[tuple[float, int]] = field(default_factory=list)
    constant: float = 0.0

    @classmethod
    def from_ising(
        cls,
        h: dict[int, float],
        J: dict[tuple[int, int], float],
        offset: float = 0.0,
    ) -> QAOAProblem:
        """Create problem from Ising model coefficients.
        
        Args:
            h: Linear coefficients {qubit: coefficient}.
            J: Quadratic coefficients {(i, j): coefficient}.
            offset: Constant offset.
            
        Returns:
            QAOAProblem instance.
        """
        all_qubits = set(h.keys())
        for i, j in J.keys():
            all_qubits.add(i)
            all_qubits.add(j)
        
        num_qubits = max(all_qubits) + 1 if all_qubits else 0
        
        linear_terms = [(coeff, qubit) for qubit, coeff in h.items()]
        cost_terms = [(coeff, (i, j)) for (i, j), coeff in J.items()]
        
        return cls(
            num_qubits=num_qubits,
            cost_terms=cost_terms,
            linear_terms=linear_terms,
            constant=offset,
        )

    @classmethod
    def from_qubo(
        cls,
        Q: dict[tuple[int, int], float],
        offset: float = 0.0,
    ) -> QAOAProblem:
        """Create problem from QUBO matrix.
        
        Args:
            Q: QUBO coefficients {(i, j): coefficient}.
            offset: Constant offset.
            
        Returns:
            QAOAProblem instance.
        """
        h: dict[int, float] = {}
        J: dict[tuple[int, int], float] = {}
        
        for (i, j), coeff in Q.items():
            if i == j:
                h[i] = h.get(i, 0.0) + coeff / 2
                offset += coeff / 2
            else:
                if i > j:
                    i, j = j, i
                J[(i, j)] = J.get((i, j), 0.0) + coeff / 4
                h[i] = h.get(i, 0.0) + coeff / 4
                h[j] = h.get(j, 0.0) + coeff / 4
                offset += coeff / 4
        
        return cls.from_ising(h, J, offset)


@dataclass
class QAOAResult:
    """Result from QAOA optimization.
    
    Attributes:
        optimal_params: Optimized gamma and beta parameters.
        optimal_value: Best expectation value found.
        best_bitstring: Most likely solution bitstring.
        counts: Measurement counts from final circuit.
        num_iterations: Number of optimization iterations.
        history: Optimization history (values at each iteration).
    """
    
    optimal_params: NDArray[np.float64]
    optimal_value: float
    best_bitstring: str
    counts: dict[str, int]
    num_iterations: int
    history: list[float] = field(default_factory=list)


class QuantumBackend(Protocol):
    """Protocol for quantum backends."""
    
    def run(
        self,
        circuit: QuantumCircuit,
        shots: int = 1024,
    ) -> dict[str, int]:
        """Execute circuit and return measurement counts."""
        ...

    def get_statevector(
        self,
        circuit: QuantumCircuit,
    ) -> NDArray[np.complex128]:
        """Get statevector from circuit execution."""
        ...


class QAOAOptimizer:
    """QAOA optimizer for combinatorial optimization problems.
    
    Implements the Quantum Approximate Optimization Algorithm with
    configurable number of layers (p), parameter initialization,
    and mixer Hamiltonians.
    
    Example:
        >>> problem = QAOAProblem.from_ising(h={0: 1.0}, J={(0, 1): -1.0})
        >>> optimizer = QAOAOptimizer(p=2, backend=backend)
        >>> result = optimizer.optimize(problem)
        >>> print(result.best_bitstring)
    """
    
    def __init__(
        self,
        p: int = 1,
        backend: QuantumBackend | None = None,
        init_strategy: ParameterInitStrategy = ParameterInitStrategy.RANDOM,
        mixer_type: str = "x",
        seed: int | None = None,
    ):
        """Initialize QAOA optimizer.
        
        Args:
            p: Number of QAOA layers.
            backend: Quantum backend for circuit execution.
            init_strategy: Parameter initialization strategy.
            mixer_type: Type of mixer Hamiltonian ('x', 'xy', 'grover').
            seed: Random seed for reproducibility.
        """
        if p < 1:
            raise ValueError("Number of layers p must be >= 1")
        
        self.p = p
        self.backend = backend
        self.init_strategy = init_strategy
        self.mixer_type = mixer_type
        self.rng = np.random.default_rng(seed)
        
        self._gamma_params: list[Parameter] = []
        self._beta_params: list[Parameter] = []

    def build_cost_operator(
        self,
        circuit: QuantumCircuit,
        problem: QAOAProblem,
        gamma: Parameter | float,
    ) -> QuantumCircuit:
        """Apply cost Hamiltonian evolution to circuit.
        
        Args:
            circuit: Quantum circuit to modify.
            problem: QAOA problem definition.
            gamma: Rotation angle parameter.
            
        Returns:
            Modified circuit.
        """
        for coeff, qubit in problem.linear_terms:
            circuit.rz(2 * coeff * gamma, qubit)
        
        for coeff, (i, j) in problem.cost_terms:
            circuit.cx(i, j)
            circuit.rz(2 * coeff * gamma, j)
            circuit.cx(i, j)
        
        return circuit

    def build_mixer_operator(
        self,
        circuit: QuantumCircuit,
        num_qubits: int,
        beta: Parameter | float,
    ) -> QuantumCircuit:
        """Apply mixer Hamiltonian evolution to circuit.
        
        Args:
            circuit: Quantum circuit to modify.
            num_qubits: Number of qubits.
            beta: Rotation angle parameter.
            
        Returns:
            Modified circuit.
        """
        if self.mixer_type == "x":
            for qubit in range(num_qubits):
                circuit.rx(2 * beta, qubit)
        elif self.mixer_type == "xy":
            for i in range(num_qubits - 1):
                circuit.rxx(beta, i, i + 1)
                circuit.ryy(beta, i, i + 1)
            if num_qubits > 2:
                circuit.rxx(beta, num_qubits - 1, 0)
                circuit.ryy(beta, num_qubits - 1, 0)
        elif self.mixer_type == "grover":
            circuit.h(range(num_qubits))
            circuit.x(range(num_qubits))
            circuit.h(num_qubits - 1)
            circuit.mcx(list(range(num_qubits - 1)), num_qubits - 1)
            circuit.h(num_qubits - 1)
            circuit.x(range(num_qubits))
            circuit.h(range(num_qubits))
        else:
            raise ValueError(f"Unknown mixer type: {self.mixer_type}")
        
        return circuit

    def build_circuit(
        self,
        problem: QAOAProblem,
        gammas: Sequence[Parameter | float] | None = None,
        betas: Sequence[Parameter | float] | None = None,
    ) -> QuantumCircuit:
        """Build QAOA circuit with p layers.
        
        Args:
            problem: QAOA problem definition.
            gammas: Cost layer parameters (creates new if None).
            betas: Mixer layer parameters (creates new if None).
            
        Returns:
            Parameterized QAOA circuit.
        """
        n = problem.num_qubits
        circuit = QuantumCircuit(n, n)
        
        circuit.h(range(n))
        
        if gammas is None:
            self._gamma_params = [Parameter(f"γ_{i}") for i in range(self.p)]
            gammas = self._gamma_params
        if betas is None:
            self._beta_params = [Parameter(f"β_{i}") for i in range(self.p)]
            betas = self._beta_params
        
        for layer in range(self.p):
            self.build_cost_operator(circuit, problem, gammas[layer])
            self.build_mixer_operator(circuit, n, betas[layer])
        
        circuit.measure(range(n), range(n))
        
        return circuit

    def initialize_parameters(
        self,
        problem: QAOAProblem,
        initial_params: NDArray[np.float64] | None = None,
    ) -> NDArray[np.float64]:
        """Initialize QAOA parameters based on strategy.
        
        Args:
            problem: QAOA problem definition.
            initial_params: Optional initial parameter values.
            
        Returns:
            Array of [gamma_0, ..., gamma_{p-1}, beta_0, ..., beta_{p-1}].
        """
        if initial_params is not None:
            if len(initial_params) != 2 * self.p:
                raise ValueError(
                    f"Expected {2 * self.p} parameters, got {len(initial_params)}"
                )
            return initial_params.copy()
        
        if self.init_strategy == ParameterInitStrategy.RANDOM:
            gammas = self.rng.uniform(0, 2 * np.pi, self.p)
            betas = self.rng.uniform(0, np.pi, self.p)
        
        elif self.init_strategy == ParameterInitStrategy.HEURISTIC:
            max_coeff = 1.0
            if problem.cost_terms:
                max_coeff = max(abs(c) for c, _ in problem.cost_terms)
            if problem.linear_terms:
                max_coeff = max(max_coeff, max(abs(c) for c, _ in problem.linear_terms))
            
            gammas = np.array([0.5 / max_coeff * (i + 1) / self.p for i in range(self.p)])
            betas = np.array([np.pi / 4 * (1 - i / self.p) for i in range(self.p)])
        
        elif self.init_strategy == ParameterInitStrategy.FIXED:
            gammas = np.full(self.p, np.pi / 4)
            betas = np.full(self.p, np.pi / 8)
        
        elif self.init_strategy == ParameterInitStrategy.INTERPOLATION:
            if self.p == 1:
                gammas = np.array([np.pi / 4])
                betas = np.array([np.pi / 8])
            else:
                gammas = np.linspace(0.1, np.pi / 2, self.p)
                betas = np.linspace(np.pi / 4, 0.1, self.p)
        
        else:
            raise ValueError(f"Unknown init strategy: {self.init_strategy}")
        
        return np.concatenate([gammas, betas])

    def compute_expectation(
        self,
        problem: QAOAProblem,
        counts: dict[str, int],
    ) -> float:
        """Compute expectation value of cost Hamiltonian from counts.
        
        Args:
            problem: QAOA problem definition.
            counts: Measurement counts.
            
        Returns:
            Expected cost value.
        """
        total_shots = sum(counts.values())
        expectation = 0.0
        
        for bitstring, count in counts.items():
            bits = [int(b) for b in bitstring[::-1]]
            spins = [1 - 2 * b for b in bits]
            
            cost = problem.constant
            
            for coeff, qubit in problem.linear_terms:
                cost += coeff * spins[qubit]
            
            for coeff, (i, j) in problem.cost_terms:
                cost += coeff * spins[i] * spins[j]
            
            expectation += cost * count / total_shots
        
        return expectation

    def evaluate_circuit(
        self,
        problem: QAOAProblem,
        params: NDArray[np.float64],
        shots: int = 1024,
    ) -> tuple[float, dict[str, int]]:
        """Evaluate QAOA circuit with given parameters.
        
        Args:
            problem: QAOA problem definition.
            params: Parameter values [gammas, betas].
            shots: Number of measurement shots.
            
        Returns:
            Tuple of (expectation_value, measurement_counts).
        """
        if self.backend is None:
            raise ValueError("Backend must be set to evaluate circuits")
        
        gammas = params[:self.p]
        betas = params[self.p:]
        
        circuit = self.build_circuit(problem, gammas=gammas, betas=betas)
        counts = self.backend.run(circuit, shots=shots)
        expectation = self.compute_expectation(problem, counts)
        
        return expectation, counts

    def optimize(
        self,
        problem: QAOAProblem,
        initial_params: NDArray[np.float64] | None = None,
        shots: int = 1024,
        maxiter: int = 100,
        callback: Callable[[NDArray[np.float64], float], None] | None = None,
    ) -> QAOAResult:
        """Run QAOA optimization.
        
        Args:
            problem: QAOA problem definition.
            initial_params: Optional initial parameters.
            shots: Number of shots per evaluation.
            maxiter: Maximum optimization iterations.
            callback: Optional callback(params, value) at each iteration.
            
        Returns:
            QAOAResult with optimal parameters and solution.
        """
        from scipy.optimize import minimize
        
        params = self.initialize_parameters(problem, initial_params)
        history: list[float] = []
        
        def objective(x: NDArray[np.float64]) -> float:
            value, _ = self.evaluate_circuit(problem, x, shots)
            history.append(value)
            if callback:
                callback(x, value)
            return value
        
        result = minimize(
            objective,
            params,
            method="COBYLA",
            options={"maxiter": maxiter},
        )
        
        final_value, final_counts = self.evaluate_circuit(
            problem, result.x, shots=shots * 4
        )
        
        best_bitstring = max(final_counts, key=lambda k: final_counts[k])
        
        return QAOAResult(
            optimal_params=result.x,
            optimal_value=final_value,
            best_bitstring=best_bitstring,
            counts=final_counts,
            num_iterations=len(history),
            history=history,
        )

    def get_circuit_depth(self, problem: QAOAProblem) -> int:
        """Get the depth of the QAOA circuit.
        
        Args:
            problem: QAOA problem definition.
            
        Returns:
            Circuit depth.
        """
        circuit = self.build_circuit(problem)
        return circuit.depth()

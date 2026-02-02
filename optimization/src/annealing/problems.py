"""
Quantum Annealing Problem Definitions

Provides QUBO and Ising model formulations for quantum annealing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


class AnnealingProblem(ABC):
    """Base class for quantum annealing problems."""
    
    @property
    @abstractmethod
    def num_variables(self) -> int:
        """Number of binary variables."""
        pass
    
    @abstractmethod
    def to_qubo(self) -> Dict[Tuple[int, int], float]:
        """Convert to QUBO dictionary format."""
        pass
    
    @abstractmethod
    def to_ising(self) -> Tuple[Dict[int, float], Dict[Tuple[int, int], float], float]:
        """Convert to Ising model (h, J, offset)."""
        pass
    
    @abstractmethod
    def evaluate_solution(self, solution: Dict[int, int]) -> float:
        """Evaluate objective for a solution."""
        pass
    
    @abstractmethod
    def decode_solution(self, solution: Dict[int, int]) -> Any:
        """Decode to problem-specific solution."""
        pass


@dataclass
class QUBOProblem(AnnealingProblem):
    """
    Quadratic Unconstrained Binary Optimization (QUBO) Problem.
    
    Minimize: x^T Q x
    where x ∈ {0, 1}^n and Q is the QUBO matrix.
    """
    
    qubo_matrix: Dict[Tuple[int, int], float]
    variable_names: Optional[Dict[int, str]] = None
    
    def __init__(
        self,
        qubo: Dict[Tuple[int, int], float],
        variable_names: Optional[Dict[int, str]] = None,
    ):
        """
        Initialize QUBO problem.
        
        Args:
            qubo: QUBO dictionary {(i, j): coefficient}
            variable_names: Optional mapping from indices to names
        """
        self.qubo_matrix = qubo
        self.variable_names = variable_names
        
        # Determine number of variables
        all_vars = set()
        for (i, j) in qubo.keys():
            all_vars.add(i)
            all_vars.add(j)
        self._num_variables = max(all_vars) + 1 if all_vars else 0
    
    @classmethod
    def from_matrix(cls, Q: np.ndarray) -> "QUBOProblem":
        """Create from numpy matrix."""
        qubo = {}
        n = Q.shape[0]
        for i in range(n):
            for j in range(i, n):
                if Q[i, j] != 0 or Q[j, i] != 0:
                    qubo[(i, j)] = Q[i, j] + (Q[j, i] if j != i else 0)
        return cls(qubo)
    
    @classmethod
    def max_cut(cls, edges: List[Tuple[int, int]], weights: Optional[List[float]] = None) -> "QUBOProblem":
        """
        Create QUBO for MaxCut problem.
        
        MaxCut QUBO: minimize Σ_{(i,j)∈E} w_ij * x_i * (1 - x_j) + w_ij * (1 - x_i) * x_j
                   = maximize Σ_{(i,j)∈E} w_ij * (x_i + x_j - 2*x_i*x_j)
        """
        if weights is None:
            weights = [1.0] * len(edges)
        
        qubo = {}
        for (i, j), w in zip(edges, weights):
            # Linear terms (negated for minimization)
            qubo[(i, i)] = qubo.get((i, i), 0) - w
            qubo[(j, j)] = qubo.get((j, j), 0) - w
            # Quadratic term
            key = (min(i, j), max(i, j))
            qubo[key] = qubo.get(key, 0) + 2 * w
        
        return cls(qubo)
    
    @classmethod
    def number_partitioning(cls, numbers: List[float]) -> "QUBOProblem":
        """
        Create QUBO for number partitioning problem.
        
        Partition numbers into two sets with equal sums.
        Minimize: (Σ_i n_i * (2*x_i - 1))^2
        """
        n = len(numbers)
        c = sum(numbers)
        
        qubo = {}
        for i in range(n):
            # Linear term
            qubo[(i, i)] = numbers[i] * (numbers[i] - c)
            # Quadratic terms
            for j in range(i + 1, n):
                qubo[(i, j)] = 2 * numbers[i] * numbers[j]
        
        return cls(qubo)
    
    @classmethod
    def knapsack(
        cls,
        values: List[float],
        weights: List[float],
        capacity: int,
        penalty: float = 100.0,
    ) -> "QUBOProblem":
        """
        Create QUBO for 0-1 knapsack problem.
        
        Maximize value while respecting capacity constraint.
        """
        n = len(values)
        
        qubo = {}
        
        # Objective: maximize value (negate for minimization)
        for i in range(n):
            qubo[(i, i)] = qubo.get((i, i), 0) - values[i]
        
        # Capacity constraint: (Σ w_i x_i - C)^2
        # Expanded: Σ w_i^2 x_i + 2*Σ_{i<j} w_i w_j x_i x_j - 2C*Σ w_i x_i + C^2
        for i in range(n):
            qubo[(i, i)] = qubo.get((i, i), 0) + penalty * (weights[i]**2 - 2*capacity*weights[i])
            for j in range(i + 1, n):
                qubo[(i, j)] = qubo.get((i, j), 0) + penalty * 2 * weights[i] * weights[j]
        
        return cls(qubo)
    
    @property
    def num_variables(self) -> int:
        return self._num_variables
    
    def to_qubo(self) -> Dict[Tuple[int, int], float]:
        return self.qubo_matrix.copy()
    
    def to_ising(self) -> Tuple[Dict[int, float], Dict[Tuple[int, int], float], float]:
        """
        Convert QUBO to Ising model.
        
        Using: x_i = (1 + s_i) / 2  where s_i ∈ {-1, +1}
        """
        h = {}  # Linear terms
        J = {}  # Quadratic terms
        offset = 0.0
        
        for (i, j), coef in self.qubo_matrix.items():
            if i == j:
                # Linear QUBO term: Q_ii * x_i
                # = Q_ii * (1 + s_i) / 2
                # = Q_ii/2 + Q_ii/2 * s_i
                h[i] = h.get(i, 0) + coef / 2
                offset += coef / 2
            else:
                # Quadratic QUBO term: Q_ij * x_i * x_j
                # = Q_ij * (1 + s_i)(1 + s_j) / 4
                # = Q_ij/4 * (1 + s_i + s_j + s_i*s_j)
                h[i] = h.get(i, 0) + coef / 4
                h[j] = h.get(j, 0) + coef / 4
                key = (min(i, j), max(i, j))
                J[key] = J.get(key, 0) + coef / 4
                offset += coef / 4
        
        return h, J, offset
    
    def evaluate_solution(self, solution: Dict[int, int]) -> float:
        """Evaluate QUBO objective."""
        total = 0.0
        for (i, j), coef in self.qubo_matrix.items():
            xi = solution.get(i, 0)
            xj = solution.get(j, 0)
            total += coef * xi * xj
        return total
    
    def decode_solution(self, solution: Dict[int, int]) -> Dict[str, Any]:
        """Decode solution."""
        selected = [i for i, v in solution.items() if v == 1]
        
        result = {
            "selected_variables": selected,
            "bitstring": ''.join(str(solution.get(i, 0)) for i in range(self.num_variables)),
            "objective_value": self.evaluate_solution(solution),
        }
        
        if self.variable_names:
            result["selected_names"] = [self.variable_names.get(i, str(i)) for i in selected]
        
        return result


@dataclass
class IsingProblem(AnnealingProblem):
    """
    Ising Model Problem.
    
    Minimize: Σ_i h_i s_i + Σ_{i<j} J_ij s_i s_j
    where s_i ∈ {-1, +1}
    """
    
    h: Dict[int, float]  # Linear terms
    J: Dict[Tuple[int, int], float]  # Quadratic terms
    offset: float = 0.0
    
    def __init__(
        self,
        h: Dict[int, float],
        J: Dict[Tuple[int, int], float],
        offset: float = 0.0,
    ):
        """
        Initialize Ising problem.
        
        Args:
            h: Linear biases {variable: bias}
            J: Quadratic couplings {(i, j): coupling}
            offset: Constant energy offset
        """
        self.h = h
        self.J = J
        self.offset = offset
        
        # Determine number of variables
        all_vars = set(h.keys())
        for (i, j) in J.keys():
            all_vars.add(i)
            all_vars.add(j)
        self._num_variables = max(all_vars) + 1 if all_vars else 0
    
    @classmethod
    def from_graph(
        cls,
        edges: List[Tuple[int, int]],
        couplings: Optional[List[float]] = None,
        fields: Optional[Dict[int, float]] = None,
    ) -> "IsingProblem":
        """Create Ising model from graph structure."""
        if couplings is None:
            couplings = [1.0] * len(edges)
        
        J = {(min(i, j), max(i, j)): c for (i, j), c in zip(edges, couplings)}
        h = fields or {}
        
        return cls(h, J)
    
    @property
    def num_variables(self) -> int:
        return self._num_variables
    
    def to_qubo(self) -> Dict[Tuple[int, int], float]:
        """Convert Ising to QUBO using s_i = 2*x_i - 1."""
        qubo = {}
        
        # Linear terms: h_i * s_i = h_i * (2*x_i - 1) = 2*h_i*x_i - h_i
        for i, bias in self.h.items():
            qubo[(i, i)] = qubo.get((i, i), 0) + 2 * bias
        
        # Quadratic terms: J_ij * s_i * s_j = J_ij * (2*x_i - 1)(2*x_j - 1)
        # = 4*J_ij*x_i*x_j - 2*J_ij*x_i - 2*J_ij*x_j + J_ij
        for (i, j), coupling in self.J.items():
            qubo[(i, i)] = qubo.get((i, i), 0) - 2 * coupling
            qubo[(j, j)] = qubo.get((j, j), 0) - 2 * coupling
            key = (min(i, j), max(i, j))
            qubo[key] = qubo.get(key, 0) + 4 * coupling
        
        return qubo
    
    def to_ising(self) -> Tuple[Dict[int, float], Dict[Tuple[int, int], float], float]:
        return self.h.copy(), self.J.copy(), self.offset
    
    def evaluate_solution(self, solution: Dict[int, int]) -> float:
        """Evaluate Ising energy. Solution should use {-1, +1}."""
        energy = self.offset
        
        for i, bias in self.h.items():
            energy += bias * solution.get(i, 1)
        
        for (i, j), coupling in self.J.items():
            energy += coupling * solution.get(i, 1) * solution.get(j, 1)
        
        return energy
    
    def decode_solution(self, solution: Dict[int, int]) -> Dict[str, Any]:
        """Decode Ising solution."""
        return {
            "spins": dict(solution),
            "energy": self.evaluate_solution(solution),
            "magnetization": sum(solution.values()) / len(solution) if solution else 0,
        }


@dataclass
class ConstrainedProblem(AnnealingProblem):
    """
    Constrained Quadratic Model (CQM) Problem.
    
    Supports linear and quadratic constraints for D-Wave hybrid CQM solver.
    """
    
    objective: Dict[Tuple[int, int], float]
    constraints: List[Dict[str, Any]]
    variable_types: Dict[int, str]  # "BINARY", "SPIN", or "INTEGER"
    
    def __init__(
        self,
        objective: Dict[Tuple[int, int], float],
        variable_types: Optional[Dict[int, str]] = None,
    ):
        """
        Initialize constrained problem.
        
        Args:
            objective: Objective function coefficients
            variable_types: Variable type mapping
        """
        self.objective = objective
        self.constraints = []
        
        # Determine variables
        all_vars = set()
        for (i, j) in objective.keys():
            all_vars.add(i)
            all_vars.add(j)
        self._num_variables = max(all_vars) + 1 if all_vars else 0
        
        self.variable_types = variable_types or {i: "BINARY" for i in range(self._num_variables)}
    
    def add_constraint(
        self,
        coefficients: Dict[int, float],
        sense: str,  # "<=", ">=", "=="
        rhs: float,
        label: str = None,
    ):
        """
        Add a linear constraint.
        
        Args:
            coefficients: {variable: coefficient}
            sense: Comparison operator
            rhs: Right-hand side value
            label: Constraint label
        """
        self.constraints.append({
            "coefficients": coefficients,
            "sense": sense,
            "rhs": rhs,
            "label": label or f"c{len(self.constraints)}",
        })
    
    def add_quadratic_constraint(
        self,
        linear: Dict[int, float],
        quadratic: Dict[Tuple[int, int], float],
        sense: str,
        rhs: float,
        label: str = None,
    ):
        """Add a quadratic constraint."""
        self.constraints.append({
            "linear": linear,
            "quadratic": quadratic,
            "sense": sense,
            "rhs": rhs,
            "label": label or f"qc{len(self.constraints)}",
            "is_quadratic": True,
        })
    
    @property
    def num_variables(self) -> int:
        return self._num_variables
    
    def to_qubo(self) -> Dict[Tuple[int, int], float]:
        """
        Convert to QUBO with penalty terms for constraints.
        Note: This is an approximation. Use CQM solver for exact handling.
        """
        qubo = self.objective.copy()
        penalty = 1000.0  # Large penalty
        
        for constraint in self.constraints:
            if constraint.get("is_quadratic"):
                continue  # Skip quadratic constraints in QUBO conversion
            
            coeffs = constraint["coefficients"]
            rhs = constraint["rhs"]
            sense = constraint["sense"]
            
            # Add penalty: P * (Σ a_i x_i - b)^2
            if sense == "==":
                for i, a_i in coeffs.items():
                    qubo[(i, i)] = qubo.get((i, i), 0) + penalty * (a_i**2 - 2*a_i*rhs)
                    for j, a_j in coeffs.items():
                        if j > i:
                            key = (i, j)
                            qubo[key] = qubo.get(key, 0) + penalty * 2 * a_i * a_j
        
        return qubo
    
    def to_ising(self) -> Tuple[Dict[int, float], Dict[Tuple[int, int], float], float]:
        """Convert QUBO representation to Ising."""
        qubo = self.to_qubo()
        temp_qubo = QUBOProblem(qubo)
        return temp_qubo.to_ising()
    
    def evaluate_solution(self, solution: Dict[int, int]) -> float:
        """Evaluate objective value."""
        total = 0.0
        for (i, j), coef in self.objective.items():
            xi = solution.get(i, 0)
            xj = solution.get(j, 0)
            total += coef * xi * xj
        return total
    
    def check_constraints(self, solution: Dict[int, int]) -> List[Dict[str, Any]]:
        """Check which constraints are satisfied."""
        results = []
        
        for constraint in self.constraints:
            if constraint.get("is_quadratic"):
                continue
            
            lhs = sum(c * solution.get(i, 0) for i, c in constraint["coefficients"].items())
            rhs = constraint["rhs"]
            sense = constraint["sense"]
            
            if sense == "<=":
                satisfied = lhs <= rhs
            elif sense == ">=":
                satisfied = lhs >= rhs
            else:  # "=="
                satisfied = abs(lhs - rhs) < 1e-6
            
            results.append({
                "label": constraint["label"],
                "lhs": lhs,
                "rhs": rhs,
                "sense": sense,
                "satisfied": satisfied,
            })
        
        return results
    
    def decode_solution(self, solution: Dict[int, int]) -> Dict[str, Any]:
        """Decode solution with constraint checking."""
        constraint_results = self.check_constraints(solution)
        feasible = all(r["satisfied"] for r in constraint_results)
        
        return {
            "solution": dict(solution),
            "objective_value": self.evaluate_solution(solution),
            "feasible": feasible,
            "constraints": constraint_results,
            "num_violated": sum(1 for r in constraint_results if not r["satisfied"]),
        }

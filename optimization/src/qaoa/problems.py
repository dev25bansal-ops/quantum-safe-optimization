"""
QAOA Problem Definitions

Provides problem-specific Hamiltonian construction for QAOA.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
import numpy as np
import pennylane as qml


class QAOAProblem(ABC):
    """Base class for QAOA problems."""

    @property
    @abstractmethod
    def num_qubits(self) -> int:
        """Number of qubits required."""
        pass

    @abstractmethod
    def cost_hamiltonian(self) -> qml.Hamiltonian:
        """Construct the cost Hamiltonian."""
        pass

    @abstractmethod
    def mixer_hamiltonian(self) -> qml.Hamiltonian:
        """Construct the mixer Hamiltonian."""
        pass

    @abstractmethod
    def evaluate_solution(self, bitstring: str) -> float:
        """Evaluate the cost of a solution bitstring."""
        pass

    @abstractmethod
    def decode_solution(self, bitstring: str) -> Any:
        """Decode bitstring to problem-specific solution."""
        pass


@dataclass
class MaxCutProblem(QAOAProblem):
    """
    MaxCut Problem for QAOA.

    Given a graph G = (V, E), find a partition of vertices into two sets
    such that the number of edges between the sets is maximized.

    Cost function: C = Σ_{(i,j)∈E} w_ij * (1 - Z_i Z_j) / 2
    """

    graph: nx.Graph

    def __init__(self, edges: List[Tuple[int, int]], weights: Optional[List[float]] = None):
        """
        Initialize MaxCut problem.

        Args:
            edges: List of edges as (i, j) tuples
            weights: Optional edge weights (default: all 1.0)
        """
        self.graph = nx.Graph()

        if weights is None:
            weights = [1.0] * len(edges)

        for (i, j), w in zip(edges, weights):
            self.graph.add_edge(i, j, weight=w)

    @classmethod
    def from_networkx(cls, graph: nx.Graph) -> "MaxCutProblem":
        """Create from NetworkX graph."""
        instance = cls.__new__(cls)
        instance.graph = graph
        return instance

    @classmethod
    def random_graph(
        cls, num_nodes: int, edge_probability: float = 0.5, seed: int = None
    ) -> "MaxCutProblem":
        """Generate random Erdős-Rényi graph."""
        graph = nx.erdos_renyi_graph(num_nodes, edge_probability, seed=seed)
        for u, v in graph.edges():
            graph[u][v]["weight"] = 1.0
        return cls.from_networkx(graph)

    @property
    def num_qubits(self) -> int:
        return self.graph.number_of_nodes()

    def cost_hamiltonian(self) -> qml.Hamiltonian:
        """
        Construct MaxCut cost Hamiltonian.

        H_C = Σ_{(i,j)∈E} w_ij * (1 - Z_i Z_j) / 2
            = Σ_{(i,j)∈E} w_ij/2 - Σ_{(i,j)∈E} w_ij/2 * Z_i Z_j
        """
        coeffs = []
        ops = []

        for i, j, data in self.graph.edges(data=True):
            w = data.get("weight", 1.0)
            coeffs.append(-w / 2)  # Negative because we minimize in QAOA
            ops.append(qml.PauliZ(i) @ qml.PauliZ(j))

        return qml.Hamiltonian(coeffs, ops)

    def mixer_hamiltonian(self) -> qml.Hamiltonian:
        """Standard X-mixer: H_B = Σ_i X_i"""
        coeffs = [1.0] * self.num_qubits
        ops = [qml.PauliX(i) for i in range(self.num_qubits)]
        return qml.Hamiltonian(coeffs, ops)

    def evaluate_solution(self, bitstring: str) -> float:
        """Evaluate cut value for a partition."""
        x = np.array([int(b) for b in bitstring])
        cut_value = 0.0

        for i, j, data in self.graph.edges(data=True):
            w = data.get("weight", 1.0)
            if x[i] != x[j]:
                cut_value += w

        return cut_value

    def decode_solution(self, bitstring: str) -> Dict[str, Any]:
        """Decode to partition sets."""
        x = [int(b) for b in bitstring]
        set_0 = [i for i, v in enumerate(x) if v == 0]
        set_1 = [i for i, v in enumerate(x) if v == 1]

        return {
            "partition": (set_0, set_1),
            "cut_value": self.evaluate_solution(bitstring),
            "cut_edges": [(i, j) for i, j in self.graph.edges() if x[i] != x[j]],
        }


@dataclass
class PortfolioProblem(QAOAProblem):
    """
    Portfolio Optimization Problem for QAOA.

    Select k assets from n to minimize risk (variance) while achieving target return.

    Objective: min x^T Σ x - λ * μ^T x
    Constraint: Σ x_i = k (select exactly k assets)
    """

    expected_returns: np.ndarray
    covariance_matrix: np.ndarray
    num_assets_to_select: int
    risk_aversion: float = 1.0
    penalty_weight: float = 10.0

    def __init__(
        self,
        expected_returns: List[float],
        covariance_matrix: List[List[float]],
        num_assets_to_select: int,
        risk_aversion: float = 1.0,
        penalty_weight: float = 10.0,
    ):
        """
        Initialize portfolio optimization problem.

        Args:
            expected_returns: Expected return for each asset
            covariance_matrix: Covariance matrix of returns
            num_assets_to_select: Number of assets to include in portfolio (k)
            risk_aversion: Trade-off between risk and return (λ)
            penalty_weight: Penalty for constraint violation
        """
        self.expected_returns = np.array(expected_returns)
        self.covariance_matrix = np.array(covariance_matrix)
        self.num_assets_to_select = num_assets_to_select
        self.risk_aversion = risk_aversion
        self.penalty_weight = penalty_weight

    @property
    def num_qubits(self) -> int:
        return len(self.expected_returns)

    def cost_hamiltonian(self) -> qml.Hamiltonian:
        """
        Construct portfolio cost Hamiltonian.

        H = Σ_ij σ_ij (1-Z_i)(1-Z_j)/4 - λ Σ_i μ_i (1-Z_i)/2 + P(Σ_i x_i - k)^2
        """
        n = self.num_qubits
        coeffs = []
        ops = []

        # Risk term: x^T Σ x
        for i in range(n):
            for j in range(n):
                coef = self.covariance_matrix[i, j] / 4
                if i == j:
                    coeffs.append(coef)
                    ops.append(qml.Identity(0))
                    coeffs.append(-coef)
                    ops.append(qml.PauliZ(i))
                else:
                    coeffs.append(coef)
                    ops.append(qml.PauliZ(i) @ qml.PauliZ(j))

        # Return term: -λ μ^T x
        for i in range(n):
            coef = -self.risk_aversion * self.expected_returns[i] / 2
            coeffs.append(-coef)
            ops.append(qml.PauliZ(i))

        # Constraint penalty: P * (Σ x_i - k)^2
        k = self.num_assets_to_select
        P = self.penalty_weight

        # Expand (Σ_i x_i - k)^2 = Σ_i x_i^2 + 2*Σ_{i<j} x_i*x_j - 2k*Σ_i x_i + k^2
        # Using x_i = (1 - Z_i)/2

        # Constant terms and linear Z terms
        for i in range(n):
            coeffs.append(P * (1 - 2 * k / n) / 4)
            ops.append(qml.PauliZ(i))

        # Quadratic ZZ terms
        for i in range(n):
            for j in range(i + 1, n):
                coeffs.append(P / 2)
                ops.append(qml.PauliZ(i) @ qml.PauliZ(j))

        return qml.Hamiltonian(coeffs, ops)

    def mixer_hamiltonian(self) -> qml.Hamiltonian:
        """Standard X-mixer."""
        coeffs = [1.0] * self.num_qubits
        ops = [qml.PauliX(i) for i in range(self.num_qubits)]
        return qml.Hamiltonian(coeffs, ops)

    def evaluate_solution(self, bitstring: str) -> float:
        """Evaluate portfolio objective."""
        x = np.array([int(b) for b in bitstring])

        # Risk (variance)
        risk = x @ self.covariance_matrix @ x

        # Expected return
        expected_return = self.expected_returns @ x

        # Constraint violation
        num_selected = np.sum(x)
        constraint_violation = (num_selected - self.num_assets_to_select) ** 2

        return (
            risk - self.risk_aversion * expected_return + self.penalty_weight * constraint_violation
        )

    def decode_solution(self, bitstring: str) -> Dict[str, Any]:
        """Decode to portfolio allocation."""
        x = np.array([int(b) for b in bitstring])
        selected = np.where(x == 1)[0].tolist()

        # Calculate metrics
        risk = x @ self.covariance_matrix @ x
        expected_return = self.expected_returns @ x

        return {
            "selected_assets": selected,
            "num_selected": len(selected),
            "portfolio_risk": float(risk),
            "expected_return": float(expected_return),
            "sharpe_ratio": float(expected_return / np.sqrt(risk)) if risk > 0 else 0.0,
            "feasible": len(selected) == self.num_assets_to_select,
        }


@dataclass
class TSPProblem(QAOAProblem):
    """
    Traveling Salesman Problem for QAOA.

    Find the shortest route visiting all cities exactly once.
    Uses one-hot encoding: x_{i,p} = 1 if city i is at position p.
    """

    distance_matrix: np.ndarray
    penalty_weight: float = 100.0

    def __init__(
        self,
        distances: List[List[float]],
        penalty_weight: float = 100.0,
    ):
        """
        Initialize TSP.

        Args:
            distances: Distance matrix D[i][j] = distance from city i to j
            penalty_weight: Penalty for constraint violations
        """
        self.distance_matrix = np.array(distances)
        self.penalty_weight = penalty_weight
        self._num_cities = len(distances)

    @classmethod
    def random_euclidean(cls, num_cities: int, seed: int = None) -> "TSPProblem":
        """Generate random Euclidean TSP."""
        rng = np.random.default_rng(seed)
        coords = rng.random((num_cities, 2))

        distances = np.zeros((num_cities, num_cities))
        for i in range(num_cities):
            for j in range(num_cities):
                if i != j:
                    distances[i, j] = np.linalg.norm(coords[i] - coords[j])

        return cls(distances.tolist())

    @property
    def num_qubits(self) -> int:
        """n^2 qubits for n cities (one-hot encoding)."""
        return self._num_cities**2

    def _qubit_index(self, city: int, position: int) -> int:
        """Get qubit index for x_{city, position}."""
        return city * self._num_cities + position

    def cost_hamiltonian(self) -> qml.Hamiltonian:
        """Construct TSP Hamiltonian with constraints."""
        n = self._num_cities
        coeffs = []
        ops = []

        # Distance cost: Σ_{i,j,p} d_ij * x_{i,p} * x_{j,p+1}
        for p in range(n):
            next_p = (p + 1) % n
            for i in range(n):
                for j in range(n):
                    if i != j:
                        q1 = self._qubit_index(i, p)
                        q2 = self._qubit_index(j, next_p)
                        coef = self.distance_matrix[i, j] / 4
                        coeffs.append(coef)
                        ops.append(qml.PauliZ(q1) @ qml.PauliZ(q2))

        # Constraint: each city visited exactly once
        P = self.penalty_weight
        for i in range(n):
            # Σ_p x_{i,p} = 1
            for p1 in range(n):
                for p2 in range(p1 + 1, n):
                    q1 = self._qubit_index(i, p1)
                    q2 = self._qubit_index(i, p2)
                    coeffs.append(P / 2)
                    ops.append(qml.PauliZ(q1) @ qml.PauliZ(q2))

        # Constraint: each position has exactly one city
        for p in range(n):
            for i1 in range(n):
                for i2 in range(i1 + 1, n):
                    q1 = self._qubit_index(i1, p)
                    q2 = self._qubit_index(i2, p)
                    coeffs.append(P / 2)
                    ops.append(qml.PauliZ(q1) @ qml.PauliZ(q2))

        return qml.Hamiltonian(coeffs, ops)

    def mixer_hamiltonian(self) -> qml.Hamiltonian:
        """Standard X-mixer."""
        coeffs = [1.0] * self.num_qubits
        ops = [qml.PauliX(i) for i in range(self.num_qubits)]
        return qml.Hamiltonian(coeffs, ops)

    def evaluate_solution(self, bitstring: str) -> float:
        """Evaluate tour length."""
        n = self._num_cities
        x = np.array([int(b) for b in bitstring]).reshape(n, n)

        # Extract tour
        tour = []
        for p in range(n):
            cities = np.where(x[:, p] == 1)[0]
            if len(cities) == 1:
                tour.append(cities[0])
            else:
                return float("inf")  # Invalid solution

        # Calculate tour length
        total = 0.0
        for i in range(n):
            total += self.distance_matrix[tour[i], tour[(i + 1) % n]]

        return total

    def decode_solution(self, bitstring: str) -> Dict[str, Any]:
        """Decode to tour."""
        n = self._num_cities
        x = np.array([int(b) for b in bitstring]).reshape(n, n)

        tour = []
        for p in range(n):
            cities = np.where(x[:, p] == 1)[0]
            if len(cities) == 1:
                tour.append(int(cities[0]))

        return {
            "tour": tour,
            "tour_length": self.evaluate_solution(bitstring),
            "feasible": len(tour) == n and len(set(tour)) == n,
        }


@dataclass
class GraphColoringProblem(QAOAProblem):
    """
    Graph Coloring Problem for QAOA.

    Color vertices of a graph with k colors such that no adjacent vertices
    have the same color.
    """

    graph: nx.Graph
    num_colors: int
    penalty_weight: float = 10.0

    def __init__(
        self,
        edges: List[Tuple[int, int]],
        num_colors: int,
        penalty_weight: float = 10.0,
    ):
        """
        Initialize graph coloring problem.

        Args:
            edges: List of edges
            num_colors: Number of available colors (k)
            penalty_weight: Penalty for constraint violations
        """
        self.graph = nx.Graph()
        self.graph.add_edges_from(edges)
        self.num_colors = num_colors
        self.penalty_weight = penalty_weight

    @property
    def num_qubits(self) -> int:
        """n * k qubits for n vertices and k colors."""
        return self.graph.number_of_nodes() * self.num_colors

    def _qubit_index(self, vertex: int, color: int) -> int:
        """Get qubit index for x_{vertex, color}."""
        return vertex * self.num_colors + color

    def cost_hamiltonian(self) -> qml.Hamiltonian:
        """Construct graph coloring Hamiltonian."""
        n = self.graph.number_of_nodes()
        k = self.num_colors
        P = self.penalty_weight

        coeffs = []
        ops = []

        # Constraint: each vertex has exactly one color
        for v in range(n):
            for c1 in range(k):
                for c2 in range(c1 + 1, k):
                    q1 = self._qubit_index(v, c1)
                    q2 = self._qubit_index(v, c2)
                    coeffs.append(P / 2)
                    ops.append(qml.PauliZ(q1) @ qml.PauliZ(q2))

        # Constraint: adjacent vertices have different colors
        for u, v in self.graph.edges():
            for c in range(k):
                q1 = self._qubit_index(u, c)
                q2 = self._qubit_index(v, c)
                coeffs.append(P / 4)
                ops.append(qml.PauliZ(q1) @ qml.PauliZ(q2))

        return qml.Hamiltonian(coeffs, ops)

    def mixer_hamiltonian(self) -> qml.Hamiltonian:
        """Standard X-mixer."""
        coeffs = [1.0] * self.num_qubits
        ops = [qml.PauliX(i) for i in range(self.num_qubits)]
        return qml.Hamiltonian(coeffs, ops)

    def evaluate_solution(self, bitstring: str) -> float:
        """Evaluate number of constraint violations."""
        n = self.graph.number_of_nodes()
        k = self.num_colors
        x = np.array([int(b) for b in bitstring]).reshape(n, k)

        violations = 0

        # Check single-color constraint
        for v in range(n):
            if np.sum(x[v]) != 1:
                violations += 1

        # Check edge constraint
        for u, v in self.graph.edges():
            for c in range(k):
                if x[u, c] == 1 and x[v, c] == 1:
                    violations += 1

        return float(violations)

    def decode_solution(self, bitstring: str) -> Dict[str, Any]:
        """Decode to coloring."""
        n = self.graph.number_of_nodes()
        k = self.num_colors
        x = np.array([int(b) for b in bitstring]).reshape(n, k)

        coloring = {}
        for v in range(n):
            colors = np.where(x[v] == 1)[0]
            if len(colors) == 1:
                coloring[v] = int(colors[0])

        violations = self.evaluate_solution(bitstring)

        return {
            "coloring": coloring,
            "num_colors_used": len(set(coloring.values())),
            "violations": int(violations),
            "feasible": violations == 0,
        }

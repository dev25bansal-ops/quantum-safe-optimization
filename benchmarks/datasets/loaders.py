"""
Benchmark Dataset Loaders.

Provides loaders for standard optimization datasets:
- GSET MaxCut instances
- TSPLIB TSP instances
- Synthetic random graphs
"""

import logging
import random
from dataclasses import dataclass
from typing import Sequence

import networkx as nx
import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkProblem:
    """Generic benchmark problem."""

    name: str
    problem_type: str  # "maxcut", "tsp", "portfolio", etc.
    data: dict
    optimal_value: float | None = None
    metadata: dict | None = None


class GSETMaxCutLoader:
    """Load GSET (Graph Set) MaxCut benchmark instances."""

    GSET_INSTANCES = [
        "G1",
        "G2",
        "G3",
        "G4",
        "G5",
        "G6",
        "G7",
        "G8",
        "G9",
        "G10",
        "G11",
        "G12",
        "G13",
        "G14",
        "G15",
        "G16",
        "G17",
        "G18",
        "G19",
        "G20",
        "G21",
        "G22",
    ]

    def __init__(self):
        """Initialize GSET loader."""
        self._loaded_instances: dict[str, nx.Graph] = {}

    def load_instance(self, name: str) -> BenchmarkProblem:
        """
        Load a specific GSET instance.

        Args:
            name: GSET instance name (e.g., "G1", "G2", ...)

        Returns:
            BenchmarkProblem with MaxCut data
        """
        if name not in self.GSET_INSTANCES:
            raise ValueError(f"Unknown GSET instance: {name}. Available: {self.GSET_INSTANCES}")

        # In production, would download from GSET repository
        # For now, generate synthetic graphs based on GSET specifications
        graph = self._generate_gset_graph(name)

        return BenchmarkProblem(
            name=f"GSET-{name}",
            problem_type="maxcut",
            data={
                "graph": graph,
                "num_nodes": graph.number_of_nodes(),
                "num_edges": graph.number_of_edges(),
            },
            metadata={
                "dataset": "GSET",
                "instance": name,
            },
        )

    def _generate_gset_graph(self, name: str) -> nx.Graph:
        """
        Generate a synthetic graph approximating GSET instance.

        GSET instances vary in structure:
        - G1-G10: Random graphs
        - G11-G20: Random geometric graphs
        - G21-G22: Dense regular graphs

        Args:
            name: Instance name

        Returns:
            NetworkX graph
        """
        # Extract instance number
        inst_num = int(name[1:])

        if inst_num <= 10:
            # Random graph (Erdős-Rényi)
            n = 10 + 2 * inst_num
            p = 0.5
            graph = nx.erdos_renyi_graph(n, p, seed=inst_num * 42)

        elif inst_num <= 20:
            # Random geometric graph
            n = 8 + inst_num
            radius = 0.3 + 0.02 * inst_num
            graph = nx.random_geometric_graph(n, radius, seed=inst_num * 42)

        else:
            # Dense regular graph
            n = 20 + inst_num
            d = n // 2
            graph = nx.random_regular_graph(d, n, seed=inst_num * 42)

        # Assign random weights (0.1 to 1.0)
        for u, v in graph.edges():
            graph[u][v]["weight"] = random.uniform(0.1, 1.0)

        # Ensure graph is connected
        if not nx.is_connected(graph):
            graph = nx.complete_graph(graph.number_of_nodes())
            for u, v in graph.edges():
                graph[u][v]["weight"] = random.uniform(0.1, 1.0)

        return graph

    def get_all_instances(self) -> Sequence[BenchmarkProblem]:
        """
        Load all GSET instances.

        Returns:
            List of all BenchmarkProblem instances
        """
        return [self.load_instance(name) for name in self.GSET_INSTANCES]


class TSPLIBLoader:
    """Load TSPLIB TSP (Traveling Salesman Problem) instances."""

    TSPLIB_INSTANCES = [
        "berlin52",
        "d1655",
        "d198",
        "dsj1000",
        "eil101",
        "eil51",
        "fl417",
        "gr137",
        "gr202",
        "gr229",
        "kroA100",
        "kroA150",
        "kroA200",
        "lin105",
        "lin318",
        "pcb442",
        "pr76",
        "pr107",
        "pr124",
        "pr144",
        "pr2392",
        "rat99",
        "rat575",
        "rd100",
        "st70",
        "u159",
        "u2319",
        "ulysses16",
        "ulysses22",
    ]

    def __init__(self):
        """Initialize TSPLIB loader."""
        self._loaded_instances: dict[str, tuple[list[tuple[int, int]], list[list[float]]]] = {}

    def load_instance(self, name: str) -> BenchmarkProblem:
        """
        Load a specific TSPLIB instance.

        Args:
            name: TSPLIB instance name (e.g., "berlin52", "eil101")

        Returns:
            BenchmarkProblem with TSP data
        """
        if name not in self.TSPLIB_INSTANCES:
            raise ValueError(f"Unknown TSPLIB instance: {name}. Available: {self.TSPLIB_INSTANCES}")

        # In production, would download from TSPLIB repository
        # For now, generate synthetic TSP instances
        nodes, distances = self._generate_tsp_instance(name)

        return BenchmarkProblem(
            name=f"TSPLIB-{name}",
            problem_type="tsp",
            data={
                "nodes": nodes,
                "distances": distances,
                "num_cities": len(nodes),
            },
            metadata={
                "dataset": "TSPLIB",
                "instance": name,
            },
        )

    def _generate_tsp_instance(self, name: str) -> tuple[list[tuple[int, int]], list[list[float]]]:
        """
        Generate a synthetic TSP instance with Euclidean distances.

        Args:
            name: Instance name

        Returns:
            Tuple of (nodes_coordinates, distance_matrix)
        """
        # Extract city count from name if possible
        if "berlin52" in name:
            n_cities = 52
        elif "eil" in name:
            n_cities = int(name[3:])
        elif "d" in name and name.startswith("d"):
            n_cities = int(name[1:])
        elif "st70" in name:
            n_cities = 70
        elif name.startswith("pr"):
            n_cities = int(name[2:])
        else:
            # Default to reasonable size
            n_cities = 50

        # Generate random city coordinates
        random.seed(hash(name) % (2**32))
        nodes = [(random.uniform(0, 100), random.uniform(0, 100)) for _ in range(n_cities)]

        # Compute Euclidean distance matrix
        distances = np.zeros((n_cities, n_cities))
        for i in range(n_cities):
            for j in range(n_cities):
                if i != j:
                    x1, y1 = nodes[i]
                    x2, y2 = nodes[j]
                    distances[i, j] = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

        return nodes, distances.tolist()

    def get_all_instances(self) -> Sequence[BenchmarkProblem]:
        """
        Load all TSPLIB instances.

        Returns:
            List of all BenchmarkProblem instances
        """
        return [
            self.load_instance(name) for name in self.TSPLIB_INSTANCES[:5]
        ]  # Limit to 5 for demo


class SyntheticGenerator:
    """Generate synthetic benchmark instances."""

    def generate_maxcut(
        self,
        num_nodes: int = 20,
        graph_type: str = "random",
        edge_prob: float = 0.5,
        seed: int = 42,
    ) -> BenchmarkProblem:
        """
        Generate synthetic MaxCut instance.

        Args:
            num_nodes: Number of nodes in the graph
            graph_type: Type of graph ("random", "erdos", "geometric", "barbell")
            edge_prob: Probability of edge creation (for random graphs)
            seed: Random seed

        Returns:
            BenchmarkProblem with MaxCut data
        """
        random.seed(seed)
        np.random.seed(seed)

        if graph_type == "random" or graph_type == "erdos":
            graph = nx.erdos_renyi_graph(num_nodes, edge_prob, seed=seed)
        elif graph_type == "geometric":
            radius = 0.3 + edge_prob * 0.3
            graph = nx.random_geometric_graph(num_nodes, radius, seed=seed)
        elif graph_type == "barbell":
            graph = nx.barbell_graph(num_nodes // 3, num_nodes // 3)
        elif graph_type == "grid":
            n_side = int(np.sqrt(num_nodes))
            graph = nx.grid_2d_graph(n_side, n_side)
        else:
            graph = nx.erdos_renyi_graph(num_nodes, 0.5, seed=seed)

        # Ensure connected graph
        if not nx.is_connected(graph):
            graph = nx.complete_graph(num_nodes)

        # Assign random weights
        if graph_type != "grid":
            for u, v in graph.edges():
                graph[u][v]["weight"] = random.uniform(0.1, 1.0)
        else:
            for u, v in graph.edges():
                graph[u][v]["weight"] = 1.0

        return BenchmarkProblem(
            name=f"MaxCut-{graph_type}-{num_nodes}nodes",
            problem_type="maxcut",
            data={
                "graph": graph,
                "num_nodes": num_nodes,
                "num_edges": graph.number_of_edges(),
                "graph_type": graph_type,
            },
            metadata={
                "synthetic": True,
                "seed": seed,
            },
        )

    def generate_portfolio(
        self,
        num_assets: int = 10,
        expected_returns: NDArray[np.float64] | None = None,
        covariance_matrix: NDArray[np.float64] | None = None,
        seed: int = 42,
        risk_budget: float = 0.1,
    ) -> BenchmarkProblem:
        """
        Generate synthetic Portfolio Optimization instance.

        Args:
            num_assets: Number of assets
            expected_returns: Asset expected returns (optional)
            covariance_matrix: Asset covariance matrix (optional)
            seed: Random seed
            risk_budget: Maximum allowed risk (variance)

        Returns:
            BenchmarkProblem with Portfolio Optimization data
        """
        random.seed(seed)
        np.random.seed(seed)

        # Generate random expected returns if not provided
        if expected_returns is None:
            expected_returns = np.random.uniform(0.01, 0.15, num_assets)

        # Generate random covariance matrix if not provided
        if covariance_matrix is None:
            # Generate positive semi-definite matrix
            L = np.random.randn(num_assets, num_assets)
            covariance_matrix = 0.01 * (L @ L.T) + 0.01 * np.eye(num_assets)

        return BenchmarkProblem(
            name=f"Portfolio-{num_assets}assets",
            problem_type="portfolio",
            data={
                "num_assets": num_assets,
                "expected_returns": expected_returns.tolist(),
                "covariance_matrix": covariance_matrix.tolist(),
                "risk_budget": risk_budget,
            },
            metadata={
                "synthetic": True,
                "seed": seed,
            },
        )

    def generate_graph_coloring(
        self,
        num_nodes: int = 20,
        edge_prob: float = 0.5,
        num_colors: int | None = None,
        seed: int = 42,
    ) -> BenchmarkProblem:
        """
        Generate synthetic Graph Coloring instance.

        Args:
            num_nodes: Number of nodes
            edge_prob: Probability of edge creation
            num_colors: Number of colors available (optional)
            seed: Random seed

        Returns:
            BenchmarkProblem with Graph Coloring data
        """
        random.seed(seed)
        graph = nx.erdos_renyi_graph(num_nodes, edge_prob, seed=seed)

        if not nx.is_connected(graph):
            graph = nx.complete_graph(num_nodes)

        # Estimate chromatic number or use provided value
        if num_colors is None:
            # Greedy upper bound on chromatic number
            colors = nx.greedy_color(graph)
            num_colors = max(colors.values()) + 1

        return BenchmarkProblem(
            name=f"GraphColoring-{num_nodes}nodes",
            problem_type="graph_coloring",
            data={
                "graph": graph,
                "num_nodes": num_nodes,
                "num_colors": num_colors,
            },
            metadata={
                "synthetic": True,
                "seed": seed,
            },
        )


class BenchmarkRunner:
    """Run benchmarks on optimization algorithms."""

    def __init__(self):
        """Initialize benchmark runner."""
        self.gset_loader = GSETMaxCutLoader()
        self.tsplib_loader = TSPLIBLoader()
        self.synthetic_generator = SyntheticGenerator()
        self.results: list[dict] = []

    def run_maxcut_benchmark(
        self,
        algorithm: callable,
        num_instances: int = 3,
        instance_names: list[str] | None = None,
        **kwargs,
    ) -> list[dict]:
        """
        Run MaxCut benchmark.

        Args:
            algorithm: Optimization algorithm function
            num_instances: Number of instances to test
            instance_names: Specific GSET instances to use
            **kwargs: Additional algorithm parameters

        Returns:
            List of benchmark results
        """
        instances = []
        if instance_names:
            instances = [
                self.gset_loader.load_instance(name) for name in instance_names[:num_instances]
            ]
        else:
            all_instances = self.gset_loader.get_all_instances()
            instances = all_instances[:num_instances]

        results = []
        for problem in instances:
            result = self._run_single_benchmark(algorithm, problem, **kwargs)
            results.append(result)

        self.results.extend(results)
        return results

    def _run_single_benchmark(
        self, algorithm: callable, problem: BenchmarkProblem, **kwargs
    ) -> dict:
        """Run benchmark on a single problem instance."""
        logger.info(f"Running benchmark on {problem.name}")

        try:
            # Run algorithm
            start_time = time.time()
            solution = algorithm(problem, **kwargs)
            end_time = time.time()

            # Compute metrics
            runtime = end_time - start_time

            return {
                "problem": problem.name,
                "problem_type": problem.problem_type,
                "solution": solution,
                "runtime": runtime,
                "success": True,
                "metadata": problem.metadata,
            }
        except Exception as e:
            logger.error(f"Benchmark failed on {problem.name}: {e}")
            return {
                "problem": problem.name,
                "problem_type": problem.problem_type,
                "solution": None,
                "runtime": 0,
                "success": False,
                "error": str(e),
                "metadata": problem.metadata,
            }


def time() -> float:
    """Get current time (import avoid)."""
    import time as _time

    return _time.time()


__all__ = [
    "BenchmarkProblem",
    "GSETMaxCutLoader",
    "TSPLIBLoader",
    "SyntheticGenerator",
    "BenchmarkRunner",
]

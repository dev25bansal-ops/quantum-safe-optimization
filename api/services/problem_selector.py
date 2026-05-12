"""Problem Type Auto-Selector Service.

Intelligently determines whether a problem should be solved using
classical or quantum approaches based on problem characteristics,
current quantum hardware quality, and historical performance data.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class RecommendedApproach(str, Enum):
    """Recommended solving approach."""

    CLASSICAL = "classical"
    QUANTUM = "quantum"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


@dataclass
class ProblemCharacteristics:
    """Characteristics of an optimization problem."""

    problem_type: str  # QAOA, VQE, ANNEALING, etc.
    num_variables: int
    num_constraints: int = 0
    connectivity: float = 0.5  # 0.0-1.0, how connected the problem graph is
    is_sparse: bool = True
    has_known_classical_solution: bool = False
    problem_structure: str = "general"  # general, tree, planar, etc.


@dataclass
class HardwareCapabilities:
    """Current quantum hardware capabilities."""

    available_qubits: int = 100
    coherence_time_us: float = 100.0
    gate_error_rate: float = 0.01
    connectivity_topology: str = "heavy-hex"  # heavy-hex, grid, fully-connected
    max_circuit_depth: int = 100
    queue_time_seconds: float = 60.0


@dataclass
class RecommendationResult:
    """Result of the auto-selection analysis."""

    approach: RecommendedApproach
    confidence: float  # 0.0-1.0
    reason: str
    suggested_backend: str
    estimated_classical_time_seconds: float
    estimated_quantuum_time_seconds: float
    parameters: dict[str, Any] = field(default_factory=dict)


class ProblemAutoSelector:
    """Auto-selects the best solving approach for a given problem."""

    def __init__(
        self,
        hardware: HardwareCapabilities | None = None,
        classical_threshold_qubits: int = 50,
    ):
        self.hardware = hardware or HardwareCapabilities()
        self.classical_threshold_qubits = classical_threshold_qubits

    def analyze(
        self,
        problem: ProblemCharacteristics,
        max_acceptable_time_seconds: float = 300.0,
    ) -> RecommendationResult:
        """Analyze problem and recommend best approach.

        Args:
            problem: Problem characteristics
            max_acceptable_time_seconds: Maximum acceptable solve time

        Returns:
            RecommendationResult with approach and reasoning
        """
        # Rule-based heuristic analysis
        if problem.problem_type == "QAOA":
            return self._recommend_qaoa(problem, max_acceptable_time_seconds)
        elif problem.problem_type == "VQE":
            return self._recommend_vqe(problem, max_acceptable_time_seconds)
        elif problem.problem_type == "ANNEALING":
            return self._recommend_annealing(problem, max_acceptable_time_seconds)

        return RecommendationResult(
            approach=RecommendedApproach.UNKNOWN,
            confidence=0.0,
            reason=f"Unknown problem type: {problem.problem_type}",
            suggested_backend="local_simulator",
            estimated_classical_time_seconds=0.0,
            estimated_quantuum_time_seconds=0.0,
        )

    def _recommend_qaoa(
        self,
        problem: ProblemCharacteristics,
        max_time: float,
    ) -> RecommendationResult:
        """Recommend approach for QAOA problems."""
        num_qubits_needed = problem.num_variables

        # Small problems: classical is faster
        if num_qubits_needed <= 20:
            return RecommendationResult(
                approach=RecommendedApproach.CLASSICAL,
                confidence=0.9,
                reason=f"Small problem ({num_qubits_needed} variables). Classical algorithms are faster and more reliable.",
                suggested_backend="classical_simulated_annealing",
                estimated_classical_time_seconds=num_qubits_needed * 0.01,
                estimated_quantuum_time_seconds=num_qubits_needed * 1.0 + self.hardware.queue_time_seconds,
                parameters={"algorithm": "simulated_annealing", "temperature_schedule": "exponential"},
            )

        # Medium problems: hybrid approach
        if num_qubits_needed <= self.hardware.available_qubits * 0.5:
            # Check if quantum hardware is good enough
            if self.hardware.gate_error_rate < 0.005 and self.hardware.max_circuit_depth >= num_qubits_needed * 10:
                return RecommendationResult(
                    approach=RecommendedApproach.QUANTUM,
                    confidence=0.7,
                    reason=f"Problem size fits current quantum hardware. Low error rate supports quantum advantage.",
                    suggested_backend="ibm_quantum",
                    estimated_classical_time_seconds=num_qubits_needed ** 2 * 0.1,
                    estimated_quantuum_time_seconds=num_qubits_needed * 2.0 + self.hardware.queue_time_seconds,
                    parameters={"layers": min(3, num_qubits_needed // 5), "optimizer": "COBYLA", "shots": 2000},
                )
            else:
                return RecommendationResult(
                    approach=RecommendedApproach.HYBRID,
                    confidence=0.6,
                    reason=f"Problem size is suitable but hardware error rate is high. Use classical pre-processing + quantum refinement.",
                    suggested_backend="hybrid_engine",
                    estimated_classical_time_seconds=num_qubits_needed ** 2 * 0.05,
                    estimated_quantuum_time_seconds=num_qubits_needed * 3.0 + self.hardware.queue_time_seconds,
                    parameters={
                        "classical_phase": "graph_partitioning",
                        "quantum_phase": "qaoa_refinement",
                        "qaoa_layers": 2,
                    },
                )

        # Large problems: beyond current quantum capability
        return RecommendationResult(
            approach=RecommendedApproach.CLASSICAL,
            confidence=0.8,
            reason=f"Problem too large for current quantum hardware ({num_qubits_needed} > {self.hardware.available_qubits} qubits).",
            suggested_backend="classical_gurobi",
            estimated_classical_time_seconds=num_qubits_needed ** 3 * 0.001,
            estimated_quantuum_time_seconds=float("inf"),
            parameters={"algorithm": "branch_and_cut", "time_limit": max_time},
        )

    def _recommend_vqe(
        self,
        problem: ProblemCharacteristics,
        max_time: float,
    ) -> RecommendationResult:
        """Recommend approach for VQE problems."""
        num_qubits_needed = problem.num_variables

        # VQE is primarily a quantum algorithm for chemistry
        if num_qubits_needed <= self.hardware.available_qubits:
            return RecommendationResult(
                approach=RecommendedApproach.QUANTUM,
                confidence=0.8,
                reason="VQE is naturally suited for quantum hardware. Molecular simulations benefit from quantum state representation.",
                suggested_backend="ibm_quantum",
                estimated_classical_time_seconds=2 ** num_qubits_needed * 0.0001,
                estimated_quantuum_time_seconds=num_qubits_needed * 10.0 + self.hardware.queue_time_seconds,
                parameters={"ansatz": "UCCSD", "optimizer": "SPSA", "shots": 4000},
            )

        return RecommendationResult(
            approach=RecommendedApproach.CLASSICAL,
            confidence=0.7,
            reason=f"Molecule too large for current quantum hardware. Use classical DFT or coupled-cluster methods.",
            suggested_backend="classical_psi4",
            estimated_classical_time_seconds=2 ** min(num_qubits_needed, 30) * 0.001,
            estimated_quantuum_time_seconds=float("inf"),
            parameters={"method": "CCSD(T)", "basis_set": "cc-pVTZ"},
        )

    def _recommend_annealing(
        self,
        problem: ProblemCharacteristics,
        max_time: float,
    ) -> RecommendationResult:
        """Recommend approach for annealing/QUBO problems."""
        num_vars = problem.num_variables

        # D-Wave has limited qubits and connectivity
        if num_vars <= 500 and problem.is_sparse:
            return RecommendationResult(
                approach=RecommendedApproach.QUANTUM,
                confidence=0.75,
                reason=f"Sparse QUBO with {num_vars} variables fits D-Wave annealing architecture well.",
                suggested_backend="dwave",
                estimated_classical_time_seconds=num_vars ** 2 * 0.001,
                estimated_quantuum_time_seconds=0.01 + self.hardware.queue_time_seconds,
                parameters={"num_reads": 1000, "annealing_time_us": 20, "chain_strength": 1.0},
            )

        return RecommendationResult(
            approach=RecommendedApproach.CLASSICAL,
            confidence=0.85,
            reason=f"Dense or large QUBO better solved with classical simulated annealing or tabu search.",
            suggested_backend="classical_neal",
            estimated_classical_time_seconds=num_vars ** 2 * 0.0001,
            estimated_quantuum_time_seconds=float("inf") if num_vars > 5000 else num_vars * 0.01,
            parameters={"sampler": "SimulatedAnnealingSampler", "num_reads": 1000, "beta_range": [0.1, 10]},
        )

    def get_hardware_status(self) -> dict[str, Any]:
        """Get current quantum hardware status."""
        hw = self.hardware
        return {
            "available_qubits": hw.available_qubits,
            "coherence_time_us": hw.coherence_time_us,
            "gate_error_rate": hw.gate_error_rate,
            "connectivity_topology": hw.connectivity_topology,
            "max_circuit_depth": hw.max_circuit_depth,
            "estimated_queue_time_seconds": hw.queue_time_seconds,
            "health": "good" if hw.gate_error_rate < 0.01 else "degraded",
        }


# Global auto-selector instance
_auto_selector: ProblemAutoSelector | None = None


def get_auto_selector() -> ProblemAutoSelector:
    """Get the global problem auto-selector."""
    global _auto_selector
    if _auto_selector is None:
        _auto_selector = ProblemAutoSelector()
    return _auto_selector


def init_auto_selector(hardware: HardwareCapabilities | None = None) -> ProblemAutoSelector:
    """Initialize the global problem auto-selector."""
    global _auto_selector
    _auto_selector = ProblemAutoSelector(hardware=hardware)
    return _auto_selector

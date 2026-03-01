"""
D-Wave Backend Implementation

Provides integration with D-Wave quantum annealing systems.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from .base import (
    BackendConfig,
    BackendType,
    JobResult,
    JobStatus,
    QuantumBackend,
)


class DWaveBackend(QuantumBackend):
    """
    D-Wave quantum annealing backend.

    Supports:
    - D-Wave Advantage (5000+ qubits)
    - Hybrid BQM solvers
    - Hybrid CQM solvers (constrained optimization)
    - Simulated annealing
    """

    def __init__(self, config: BackendConfig):
        super().__init__(config)
        self._client = None
        self._sampler = None

    @property
    def backend_type(self) -> BackendType:
        return BackendType.DWAVE

    async def connect(self) -> None:
        """Connect to D-Wave Leap."""
        try:
            from dwave.cloud import Client

            if self.config.api_token:
                self._client = Client(token=self.config.api_token)
            else:
                # Use environment variable or config file
                self._client = Client.from_config()

            self._is_connected = True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to D-Wave: {e}")

    async def disconnect(self) -> None:
        """Disconnect from D-Wave."""
        if self._client:
            self._client.close()
        self._client = None
        self._is_connected = False

    async def get_available_devices(self) -> List[Dict[str, Any]]:
        """Get list of available D-Wave solvers."""
        if not self._client:
            raise RuntimeError("Not connected to D-Wave")

        solvers = self._client.get_solvers()
        return [
            {
                "name": s.name,
                "num_qubits": s.num_qubits if hasattr(s, "num_qubits") else None,
                "category": s.properties.get("category", "unknown"),
                "avg_load": s.avg_load() if hasattr(s, "avg_load") else None,
            }
            for s in solvers
        ]

    async def execute_circuit(
        self,
        circuit: Any,
        shots: int = 1000,
        device_name: Optional[str] = None,
    ) -> JobResult:
        """
        D-Wave doesn't execute gate-model circuits.
        This method converts to QUBO if possible, otherwise raises an error.
        """
        raise NotImplementedError(
            "D-Wave is a quantum annealer and doesn't support gate-model circuits. "
            "Use run_qubo() or run_bqm() instead."
        )

    async def run_qubo(
        self,
        qubo_matrix: Dict[tuple, float],
        num_reads: int = 1000,
        annealing_time: Optional[int] = None,
        use_hybrid: bool = True,
    ) -> JobResult:
        """
        Run a QUBO problem on D-Wave.

        Args:
            qubo_matrix: QUBO as dict {(i, j): coefficient}
            num_reads: Number of samples
            annealing_time: Annealing time in microseconds
            use_hybrid: Use hybrid solver (recommended for large problems)

        Returns:
            JobResult with optimal solution
        """
        from dimod import BinaryQuadraticModel
        from dwave.system import DWaveSampler, EmbeddingComposite, LeapHybridSampler

        if not self._client:
            raise RuntimeError("Not connected to D-Wave")

        job_id = str(uuid.uuid4())
        submitted_at = datetime.utcnow()

        try:
            # Convert QUBO dict to BQM
            bqm = BinaryQuadraticModel.from_qubo(qubo_matrix)

            if use_hybrid:
                sampler = LeapHybridSampler()
                sampleset = sampler.sample(bqm)
            else:
                sampler = EmbeddingComposite(DWaveSampler())
                params = {"num_reads": num_reads}
                if annealing_time:
                    params["annealing_time"] = annealing_time
                sampleset = sampler.sample(bqm, **params)

            # Get best solution
            best_sample = sampleset.first.sample
            best_energy = sampleset.first.energy

            # Convert to bitstring
            num_vars = max(max(k) for k in qubo_matrix.keys()) + 1
            optimal_bitstring = "".join(str(best_sample.get(i, 0)) for i in range(num_vars))

            # Get counts
            counts = {}
            for sample, energy, num_occurrences in sampleset.data(
                ["sample", "energy", "num_occurrences"]
            ):
                bitstring = "".join(str(sample.get(i, 0)) for i in range(num_vars))
                counts[bitstring] = counts.get(bitstring, 0) + num_occurrences

            return JobResult(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                backend_type=self.backend_type,
                device_name="hybrid" if use_hybrid else "Advantage",
                submitted_at=submitted_at,
                completed_at=datetime.utcnow(),
                optimal_value=float(best_energy),
                optimal_bitstring=optimal_bitstring,
                counts=counts,
                raw_result=sampleset,
            )
        except Exception as e:
            return JobResult(
                job_id=job_id,
                status=JobStatus.FAILED,
                backend_type=self.backend_type,
                device_name="dwave",
                submitted_at=submitted_at,
                completed_at=datetime.utcnow(),
                error_message=str(e),
            )

    async def run_bqm(
        self,
        linear: Dict[int, float],
        quadratic: Dict[tuple, float],
        offset: float = 0.0,
        vartype: str = "BINARY",
        num_reads: int = 1000,
        use_hybrid: bool = True,
    ) -> JobResult:
        """
        Run a Binary Quadratic Model on D-Wave.

        Args:
            linear: Linear terms {variable: bias}
            quadratic: Quadratic terms {(i, j): bias}
            offset: Constant energy offset
            vartype: "BINARY" (0,1) or "SPIN" (-1,+1)
            num_reads: Number of samples
            use_hybrid: Use hybrid solver

        Returns:
            JobResult with optimal solution
        """
        from dimod import BinaryQuadraticModel, Vartype
        from dwave.system import DWaveSampler, EmbeddingComposite, LeapHybridSampler

        if not self._client:
            raise RuntimeError("Not connected to D-Wave")

        job_id = str(uuid.uuid4())
        submitted_at = datetime.utcnow()

        try:
            vtype = Vartype.BINARY if vartype == "BINARY" else Vartype.SPIN
            bqm = BinaryQuadraticModel(linear, quadratic, offset, vtype)

            if use_hybrid:
                sampler = LeapHybridSampler()
                sampleset = sampler.sample(bqm)
            else:
                sampler = EmbeddingComposite(DWaveSampler())
                sampleset = sampler.sample(bqm, num_reads=num_reads)

            best_sample = sampleset.first.sample
            best_energy = sampleset.first.energy

            # Convert to bitstring
            variables = sorted(linear.keys())
            optimal_bitstring = "".join(str(best_sample[v]) for v in variables)

            return JobResult(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                backend_type=self.backend_type,
                device_name="hybrid" if use_hybrid else "Advantage",
                submitted_at=submitted_at,
                completed_at=datetime.utcnow(),
                optimal_value=float(best_energy),
                optimal_bitstring=optimal_bitstring,
                raw_result=sampleset,
            )
        except Exception as e:
            return JobResult(
                job_id=job_id,
                status=JobStatus.FAILED,
                backend_type=self.backend_type,
                device_name="dwave",
                submitted_at=submitted_at,
                completed_at=datetime.utcnow(),
                error_message=str(e),
            )

    async def run_cqm(
        self,
        objective: Any,
        constraints: List[Any],
        time_limit: int = 60,
    ) -> JobResult:
        """
        Run a Constrained Quadratic Model on D-Wave hybrid.

        Args:
            objective: Objective function (minimize)
            constraints: List of constraint expressions
            time_limit: Maximum solve time in seconds

        Returns:
            JobResult with optimal solution
        """
        from dimod import ConstrainedQuadraticModel
        from dwave.system import LeapHybridCQMSampler

        if not self._client:
            raise RuntimeError("Not connected to D-Wave")

        job_id = str(uuid.uuid4())
        submitted_at = datetime.utcnow()

        try:
            cqm = ConstrainedQuadraticModel()
            cqm.set_objective(objective)

            for i, constraint in enumerate(constraints):
                cqm.add_constraint(constraint, label=f"c{i}")

            sampler = LeapHybridCQMSampler()
            sampleset = sampler.sample_cqm(cqm, time_limit=time_limit)

            # Filter feasible solutions
            feasible = sampleset.filter(lambda d: d.is_feasible)

            if len(feasible) > 0:
                best = feasible.first
                return JobResult(
                    job_id=job_id,
                    status=JobStatus.COMPLETED,
                    backend_type=self.backend_type,
                    device_name="hybrid_cqm",
                    submitted_at=submitted_at,
                    completed_at=datetime.utcnow(),
                    optimal_value=float(best.energy),
                    raw_result=feasible,
                )
            else:
                return JobResult(
                    job_id=job_id,
                    status=JobStatus.COMPLETED,
                    backend_type=self.backend_type,
                    device_name="hybrid_cqm",
                    submitted_at=submitted_at,
                    completed_at=datetime.utcnow(),
                    error_message="No feasible solution found",
                    raw_result=sampleset,
                )
        except Exception as e:
            return JobResult(
                job_id=job_id,
                status=JobStatus.FAILED,
                backend_type=self.backend_type,
                device_name="hybrid_cqm",
                submitted_at=submitted_at,
                completed_at=datetime.utcnow(),
                error_message=str(e),
            )

    async def run_vqe(
        self,
        hamiltonian: Any,
        ansatz: Any,
        optimizer: str = "COBYLA",
        initial_params: Optional[np.ndarray] = None,
        shots: int = 1000,
        max_iterations: int = 100,
    ) -> JobResult:
        """D-Wave doesn't support VQE directly."""
        raise NotImplementedError(
            "D-Wave is a quantum annealer and doesn't support VQE. "
            "Use IBM Quantum, AWS Braket, or Azure Quantum for VQE."
        )

    async def run_qaoa(
        self,
        cost_hamiltonian: Any,
        mixer_hamiltonian: Any,
        layers: int = 1,
        optimizer: str = "COBYLA",
        initial_params: Optional[np.ndarray] = None,
        shots: int = 1000,
    ) -> JobResult:
        """
        D-Wave doesn't support gate-model QAOA.
        Consider converting your problem to QUBO and using run_qubo().
        """
        raise NotImplementedError(
            "D-Wave is a quantum annealer and doesn't support gate-model QAOA. "
            "Convert your problem to QUBO and use run_qubo() instead."
        )

    async def get_job_status(self, job_id: str) -> JobStatus:
        """Get status of a D-Wave computation."""
        return JobStatus.COMPLETED

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a D-Wave computation."""
        return False

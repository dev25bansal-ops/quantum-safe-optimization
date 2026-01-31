"""
Quantum backend port definition.

Defines the protocol for quantum computing backends that can execute
quantum circuits.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from qsop.domain.models.result import QuantumExecutionResult


@dataclass(frozen=True)
class BackendCapabilities:
    """
    Capabilities and properties of a quantum backend.

    Attributes:
        name: Backend name.
        num_qubits: Number of available qubits.
        basis_gates: Set of native gate names.
        supported_instructions: All supported instructions.
        max_shots: Maximum number of shots per execution.
        max_circuits: Maximum circuits per job.
        dynamic_reprate_enabled: Whether dynamic repetition rate is supported.
        simulator: Whether this is a simulator.
        local: Whether this runs locally.
        coupling_map: Qubit connectivity (list of [q1, q2] pairs).
        instruction_durations: Gate duration information.
        max_execution_time: Maximum job execution time in seconds.
        online: Whether the backend is currently online.
        pending_jobs: Number of jobs in queue.
        metadata: Additional backend-specific metadata.
    """

    name: str
    num_qubits: int
    basis_gates: frozenset[str] = frozenset()
    supported_instructions: frozenset[str] = frozenset()
    max_shots: int = 100000
    max_circuits: int = 300
    dynamic_reprate_enabled: bool = False
    simulator: bool = False
    local: bool = False
    coupling_map: tuple[tuple[int, int], ...] = ()
    instruction_durations: dict[str, float] = field(default_factory=dict)
    max_execution_time: int = 3600
    online: bool = True
    pending_jobs: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def supports_gate(self, gate: str) -> bool:
        """Check if a gate is in the basis gate set."""
        return gate.lower() in {g.lower() for g in self.basis_gates}

    def are_qubits_connected(self, q1: int, q2: int) -> bool:
        """Check if two qubits are connected."""
        if not self.coupling_map:
            return True  # Assume full connectivity if no map provided
        return (q1, q2) in self.coupling_map or (q2, q1) in self.coupling_map


@runtime_checkable
class QuantumBackend(Protocol):
    """
    Protocol for quantum computing backends.

    Provides synchronous and asynchronous execution of quantum circuits.
    """

    @property
    def name(self) -> str:
        """Return the backend name."""
        ...

    @property
    def capabilities(self) -> BackendCapabilities:
        """Return the backend capabilities."""
        ...

    def run(
        self,
        circuit: Any,
        shots: int = 1024,
        **options: Any,
    ) -> QuantumExecutionResult:
        """
        Execute a quantum circuit and wait for results.

        Args:
            circuit: The quantum circuit to execute (format depends on backend).
            shots: Number of measurement shots.
            **options: Backend-specific execution options.

        Returns:
            The quantum execution result.

        Raises:
            QuantumBackendError: If execution fails.
        """
        ...

    def submit(
        self,
        circuit: Any,
        shots: int = 1024,
        **options: Any,
    ) -> str:
        """
        Submit a quantum circuit for asynchronous execution.

        Args:
            circuit: The quantum circuit to execute.
            shots: Number of measurement shots.
            **options: Backend-specific execution options.

        Returns:
            Job ID that can be used to retrieve results.

        Raises:
            QuantumBackendError: If submission fails.
        """
        ...

    def get_result(self, job_id: str) -> QuantumExecutionResult:
        """
        Get the result of a previously submitted job.

        Args:
            job_id: The job identifier returned by submit().

        Returns:
            The quantum execution result.

        Raises:
            QuantumBackendError: If retrieval fails or job not found.
        """
        ...

    def get_job_status(self, job_id: str) -> str:
        """
        Get the status of a submitted job.

        Args:
            job_id: The job identifier.

        Returns:
            Status string (e.g., 'QUEUED', 'RUNNING', 'DONE', 'ERROR').

        Raises:
            QuantumBackendError: If status check fails.
        """
        ...

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a submitted job.

        Args:
            job_id: The job identifier.

        Returns:
            True if cancellation was successful.

        Raises:
            QuantumBackendError: If cancellation fails.
        """
        ...

    def transpile(
        self,
        circuit: Any,
        optimization_level: int = 1,
        **options: Any,
    ) -> Any:
        """
        Transpile a circuit for this backend.

        Args:
            circuit: The quantum circuit to transpile.
            optimization_level: Optimization level (0-3).
            **options: Additional transpilation options.

        Returns:
            The transpiled circuit.

        Raises:
            QuantumBackendError: If transpilation fails.
        """
        ...

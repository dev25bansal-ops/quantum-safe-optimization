"""
Mock AWS Braket and Azure Quantum providers for testing and failover demonstration.
"""

from typing import Any

from qsop.domain.models.result import QuantumExecutionResult
from qsop.domain.ports.quantum_backend import BackendCapabilities


class MockProviderBackend:
    """Base class for mock provider backends."""

    def __init__(self, name: str, capabilities: BackendCapabilities) -> None:
        self._name = name
        self._capabilities = capabilities

    @property
    def name(self) -> str:
        return self._name

    @property
    def capabilities(self) -> BackendCapabilities:
        return self._capabilities

    def run(self, circuit: Any, shots: int = 1024, **options: Any) -> QuantumExecutionResult:
        return QuantumExecutionResult(
            job_id="mock_job_id",
            counts={"00": shots // 2, "11": shots // 2},
            metadata={"backend": self.name},
        )

    def submit(self, circuit: Any, shots: int = 1024, **options: Any) -> str:
        return f"mock_job_{self.name}"

    def retrieve_result(self, job_id: str) -> QuantumExecutionResult:
        return self.run(None)

    def get_job_status(self, job_id: str) -> str:
        return "DONE"

    def cancel_job(self, job_id: str) -> bool:
        return True

    def transpile(self, circuit: Any, optimization_level: int = 1, **options: Any) -> Any:
        return circuit


class AWSBraketMock(MockProviderBackend):
    """Mock AWS Braket Backend."""

    def __init__(self, name: str = "aws.braket.mock", num_qubits: int = 80) -> None:
        caps = BackendCapabilities(
            name=name,
            num_qubits=num_qubits,
            basis_gates=frozenset(["rx", "ry", "rz", "cz"]),
            simulator=False,
            local=False,
            online=True,
            pending_jobs=5,
        )
        super().__init__(name, caps)


class AzureQuantumMock(MockProviderBackend):
    """Mock Azure Quantum Backend."""

    def __init__(self, name: str = "azure.quantum.mock", num_qubits: int = 40) -> None:
        caps = BackendCapabilities(
            name=name,
            num_qubits=num_qubits,
            basis_gates=frozenset(["h", "x", "y", "z", "cx"]),
            simulator=False,
            local=False,
            online=True,
            pending_jobs=10,
        )
        super().__init__(name, caps)

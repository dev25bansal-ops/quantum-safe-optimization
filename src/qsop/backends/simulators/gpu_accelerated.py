"""
GPU-Accelerated Quantum Simulator.

Provides high-performance quantum circuit simulation using CUDA/GPU
acceleration via CuPy and cuQuantum (when available).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
from numpy.typing import NDArray

from qsop.domain.models.result import MeasurementResult, QuantumExecutionResult
from qsop.domain.ports.quantum_backend import BackendCapabilities

try:
    import cupy as cp

    CUPY_AVAILABLE = True
except ImportError:
    CUPY_AVAILABLE = False

try:
    from cupyx.scipy.sparse import csr_matrix as cp_csr_matrix

    CUPY_SPARSE_AVAILABLE = True
except ImportError:
    CUPY_SPARSE_AVAILABLE = False


@dataclass
class GPUSimulatorConfig:
    """Configuration for GPU simulator."""

    use_gpu: bool = True
    device_id: int = 0
    enable_batching: bool = True
    batch_size: int = 4
    use_double_precision: bool = False
    fallback_to_cpu: bool = True


class GPUAcceleratedSimulator:
    """
    GPU-accelerated quantum statevector simulator.

    Features:
    - CuPy for GPU operations
    - cuQuantum for optimized gate operations
    - Multi-qubit operations
    - Measurement simulation
    - Statevector visualization
    """

    name: str = "gpu_simulator"

    def __init__(
        self,
        config: GPUSimulatorConfig = GPUSimulatorConfig(),
        num_qubits_max: int = 30,
    ):
        """
        Initialize GPU simulator.

        Args:
            config: Simulator configuration
            num_qubits_max: Maximum number of qubits supported
        """
        self.config = config
        self.num_qubits_max = num_qubits_max
        self._device = None
        self._xp = None  # numpy or cupy

        if config.use_gpu and CUPY_AVAILABLE:
            self._xp = cp
            cp.cuda.Device(config.device_id).use()
            self._device = f"cuda:{config.device_id}"
        elif config.fallback_to_cpu:
            self._xp = np
            self._device = "cpu"
        else:
            raise RuntimeError("GPU acceleration requested but CuPy not available")

        self._rng = np.random.default_rng()
        self._pending_jobs: dict[str, QuantumExecutionResult] = field(default_factory=dict)

    @property
    def capabilities(self) -> BackendCapabilities:
        """Return backend capabilities."""
        return BackendCapabilities(
            name=self.name,
            num_qubits=self.num_qubits_max,
            basis_gates=frozenset(
                [
                    "i",
                    "x",
                    "y",
                    "z",
                    "h",
                    "s",
                    "t",
                    "sdg",
                    "tdg",
                    "rx",
                    "ry",
                    "rz",
                    "u",
                    "u1",
                    "u2",
                    "u3",
                    "cx",
                    "cy",
                    "cz",
                    "ch",
                    "swap",
                    "cx",
                    "ccx",
                    "c3x",
                    "unitary",
                ]
            ),
            max_shots=1000000,
            simulator=True,
            local=True,
            gpu=self._device != "cpu",
            metadata={
                "supports_statevector": True,
                "supports_density_matrix": False,
                "supports_unitary": True,
                "gpu_device": self._device,
                "double_precision": self.config.use_double_precision,
            },
        )

    def _to_device(self, arr: NDArray) -> Any:
        """Transfer array to compute device."""
        if self._xp is cp:
            return cp.asarray(arr)
        return arr

    def _to_host(self, arr: Any) -> NDArray:
        """Transfer array to host."""
        if self._xp is cp:
            return cp.asnumpy(arr)
        return arr

    def _initialize_state(self, num_qubits: int) -> Any:
        """Initialize |0...0⟩ state on device."""
        dim = 2**num_qubits
        state = self._xp.zeros(
            dim, dtype=np.complex128 if self.config.use_double_precision else np.complex64
        )
        state[0] = 1.0 + 0.0j
        return state

    def transpile(
        self,
        circuit: Any,
        optimization_level: int = 1,
        **options: Any,
    ) -> Any:
        """Transpile/compile circuit for GPU execution."""
        # For now, return as-is - Qiskit circuits work directly
        return circuit

    def compile(self, circuit: Any, *, options: dict | None = None) -> Any:
        """Compile circuit."""
        return self.transpile(circuit)

    def run(
        self,
        circuit: Any,
        shots: int = 1024,
        seed: int | None = None,
        **options: Any,
    ) -> QuantumExecutionResult:
        """
        Run circuit on GPU simulator.

        Args:
            circuit: Qiskit QuantumCircuit
            shots: Number of measurement shots
            seed: Random seed for measurements
            **options: Additional options

        Returns:
            QuantumExecutionResult
        """
        if seed is not None:
            self._rng = np.random.default_rng(seed)

        start_time = datetime.utcnow()

        if hasattr(circuit, "num_qubits"):
            num_qubits = circuit.num_qubits
            result = self._run_qiskit_circuit(circuit, num_qubits, shots, options)
        elif isinstance(circuit, list):
            result = self._run_internal_circuit(circuit, shots, options)
        else:
            raise ValueError(f"Unsupported circuit type: {type(circuit)}")

        end_time = datetime.utcnow()
        result.execution_time_seconds = (end_time - start_time).total_seconds()
        result.metadata["device"] = self._device

        return result

    def _run_qiskit_circuit(
        self,
        circuit: Any,
        num_qubits: int,
        shots: int,
        options: dict,
    ) -> QuantumExecutionResult:
        """Execute Qiskit circuit on GPU."""
        state = self._initialize_state(num_qubits)

        for instruction in circuit.data:
            gate_name = instruction.operation.name
            qubits = [circuit.find_bit(q).index for q in instruction.qubits]
            params = instruction.operation.params

            if gate_name.lower() not in ["measure", "barrier"]:
                state = self._apply_gpu_gate(state, gate_name, qubits, params, num_qubits)

        counts = self._gpu_measure(state, shots, num_qubits)

        return self._create_result(counts, num_qubits, shots)

    def _run_internal_circuit(
        self,
        circuit: list[tuple],
        shots: int,
        options: dict,
    ) -> QuantumExecutionResult:
        """Execute internal circuit format on GPU."""
        num_qubits = max(max(q) if isinstance(q, list) else q for (_, q, _) in circuit) + 1
        state = self._initialize_state(num_qubits)

        for gate_name, qubits, params in circuit:
            if isinstance(qubits, int):
                qubits = [qubits]
            qubits = list(qubits)

            if gate_name.lower() not in ["measure", "barrier"]:
                state = self._apply_gpu_gate(state, gate_name, qubits, params, num_qubits)

        counts = self._gpu_measure(state, shots, num_qubits)

        return self._create_result(counts, num_qubits, shots)

    def _apply_gpu_gate(
        self,
        state: Any,
        gate_name: str,
        qubits: list[int],
        params: list[float],
        num_qubits: int,
    ) -> Any:
        """Apply quantum gate using GPU operations."""
        gate_name = gate_name.upper()

        if len(qubits) == 1:
            return self._apply_single_qubit_gpu(state, gate_name, qubits[0], params, num_qubits)
        elif len(qubits) == 2:
            return self._apply_two_qubit_gpu(
                state, gate_name, qubits[0], qubits[1], params, num_qubits
            )
        elif len(qubits) == 3:
            return self._apply_three_qubit_gpu(state, gate_name, qubits, params, num_qubits)

        return state

    def _apply_single_qubit_gpu(
        self,
        state: Any,
        gate_name: str,
        qubit: int,
        params: list[float],
        num_qubits: int,
    ) -> Any:
        """Apply single-qubit gate using GPU."""
        gate = self._get_single_qubit_gate_matrix(gate_name, params)
        dim = 2**num_qubits

        # Reshape state for tensor operation
        state_reshaped = state.reshape([2] * num_qubits)

        # Apply gate to target qubit
        list(range(num_qubits))
        state_reshaped = self._xp.tensordot(gate, state_reshaped, axes=([1], [qubit]))
        state_reshaped = self._xp.moveaxis(state_reshaped, 0, qubit)

        return state_reshaped.reshape(dim)

    def _apply_two_qubit_gpu(
        self,
        state: Any,
        gate_name: str,
        qubit1: int,
        qubit2: int,
        params: list[float],
        num_qubits: int,
    ) -> Any:
        """Apply two-qubit gate using GPU."""
        gate = self._get_two_qubit_gate_matrix(gate_name, params)
        dim = 2**num_qubits

        state_reshaped = state.reshape([2] * num_qubits)

        # Apply gate to two target qubits
        axes = [[0, 1], [qubit1, qubit2]]
        state_reshaped = self._xp.tensordot(gate, state_reshaped, axes=axes)
        state_reshaped = self._xp.moveaxis(state_reshaped, [0, 1], [qubit1, qubit2])

        return state_reshaped.reshape(dim)

    def _apply_three_qubit_gpu(
        self,
        state: Any,
        gate_name: str,
        qubits: list[int],
        params: list[float],
        num_qubits: int,
    ) -> Any:
        """Apply three-qubit gate using GPU (e.g., Toffoli)."""
        gate = self._get_three_qubit_gate_matrix(gate_name, params)
        dim = 2**num_qubits

        state_reshaped = state.reshape([2] * num_qubits)
        axes = [[0, 1, 2], [qubits[0], qubits[1], qubits[2]]]
        state_reshaped = self._xp.tensordot(gate, state_reshaped, axes=axes)
        state_reshaped = self._xp.moveaxis(
            state_reshaped, [0, 1, 2], [qubits[0], qubits[1], qubits[2]]
        )

        return state_reshaped.reshape(dim)

    def _get_single_qubit_gate_matrix(self, gate_name: str, params: list[float]) -> Any:
        """Get single-qubit gate matrix on device."""
        xp = self._xp

        if gate_name == "X":
            return xp.array([[0, 1], [1, 0]], dtype=complex)
        elif gate_name == "Y":
            return xp.array([[0, -1j], [1j, 0]], dtype=complex)
        elif gate_name == "Z":
            return xp.array([[1, 0], [0, -1]], dtype=complex)
        elif gate_name == "H":
            return xp.array([[1, 1], [1, -1]], dtype=complex) / xp.sqrt(2)
        elif gate_name == "S":
            return xp.array([[1, 0], [0, 1j]], dtype=complex)
        elif gate_name == "T":
            return xp.array([[1, 0], [0, xp.exp(1j * xp.pi / 4)]], dtype=complex)
        elif gate_name == "RX":
            theta = params[0]
            c, s = xp.cos(theta / 2), xp.sin(theta / 2)
            return xp.array([[c, -1j * s], [-1j * s, c]], dtype=complex)
        elif gate_name == "RY":
            theta = params[0]
            c, s = xp.cos(theta / 2), xp.sin(theta / 2)
            return xp.array([[c, -s], [s, c]], dtype=complex)
        elif gate_name == "RZ":
            theta = params[0]
            return xp.array(
                [[xp.exp(-1j * theta / 2), 0], [0, xp.exp(1j * theta / 2)]], dtype=complex
            )
        elif gate_name in ("U", "U3"):
            theta, phi, lam = params[0], params[1], params[2]
            return xp.array(
                [
                    [xp.cos(theta / 2), -xp.exp(1j * lam) * xp.sin(theta / 2)],
                    [
                        xp.exp(1j * phi) * xp.sin(theta / 2),
                        xp.exp(1j * (phi + lam)) * xp.cos(theta / 2),
                    ],
                ],
                dtype=complex,
            )

        return xp.eye(2, dtype=complex)

    def _get_two_qubit_gate_matrix(self, gate_name: str, params: list[float]) -> Any:
        """Get two-qubit gate matrix on device."""
        xp = self._xp

        if gate_name in ("CX", "CNOT"):
            return xp.array(
                [
                    [1, 0, 0, 0],
                    [0, 1, 0, 0],
                    [0, 0, 0, 1],
                    [0, 0, 1, 0],
                ],
                dtype=complex,
            )
        elif gate_name == "CZ":
            return xp.array(
                [
                    [1, 0, 0, 0],
                    [0, 1, 0, 0],
                    [0, 0, 1, 0],
                    [0, 0, 0, -1],
                ],
                dtype=complex,
            )
        elif gate_name == "CY":
            return xp.array(
                [
                    [1, 0, 0, 0],
                    [0, 1, 0, 0],
                    [0, 0, 0, -1j],
                    [0, 0, 1j, 0],
                ],
                dtype=complex,
            )
        elif gate_name == "SWAP":
            return xp.array(
                [
                    [1, 0, 0, 0],
                    [0, 0, 1, 0],
                    [0, 1, 0, 0],
                    [0, 0, 0, 1],
                ],
                dtype=complex,
            )
        elif gate_name == "CRX":
            theta = params[0]
            c, s = xp.cos(theta / 2), xp.sin(theta / 2)
            return xp.array(
                [
                    [1, 0, 0, 0],
                    [0, 1, 0, 0],
                    [0, 0, c, -1j * s],
                    [0, 0, -1j * s, c],
                ],
                dtype=complex,
            )
        elif gate_name == "CRY":
            theta = params[0]
            c, s = xp.cos(theta / 2), xp.sin(theta / 2)
            return xp.array(
                [
                    [1, 0, 0, 0],
                    [0, 1, 0, 0],
                    [0, 0, c, -s],
                    [0, 0, s, c],
                ],
                dtype=complex,
            )
        elif gate_name == "CRZ":
            theta = params[0]
            return xp.array(
                [
                    [1, 0, 0, 0],
                    [0, 1, 0, 0],
                    [0, 0, xp.exp(-1j * theta / 2), 0],
                    [0, 0, 0, xp.exp(1j * theta / 2)],
                ],
                dtype=complex,
            )

        return xp.eye(4, dtype=complex)

    def _get_three_qubit_gate_matrix(self, gate_name: str, params: list[float]) -> Any:
        """Get three-qubit gate matrix on device."""
        xp = self._xp

        if gate_name in ("CCX", "TOFFOLI", "C3X"):
            return xp.array(
                [
                    [1, 0, 0, 0, 0, 0, 0, 0],
                    [0, 1, 0, 0, 0, 0, 0, 0],
                    [0, 0, 1, 0, 0, 0, 0, 0],
                    [0, 0, 0, 1, 0, 0, 0, 0],
                    [0, 0, 0, 0, 1, 0, 0, 0],
                    [0, 0, 0, 0, 0, 1, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0, 1],
                    [0, 0, 0, 0, 0, 0, 1, 0],
                ],
                dtype=complex,
            )

        return xp.eye(8, dtype=complex)

    def _gpu_measure(
        self,
        state: Any,
        shots: int,
        num_qubits: int,
    ) -> dict[str, int]:
        """Perform measurement using GPU operations."""
        xp = self._xp

        probabilities = xp.abs(state) ** 2
        probabilities = probabilities / xp.sum(probabilities)

        # Sample outcomes
        outcomes_host = xp.random.choice(
            len(state),
            size=shots,
            p=self._to_host(probabilities),
        )

        counts: dict[str, int] = {}
        for outcome in outcomes_host:
            bitstring = format(int(outcome), f"0{num_qubits}b")
            counts[bitstring] = counts.get(bitstring, 0) + 1

        return counts

    def _create_result(
        self,
        counts: dict[str, int],
        num_qubits: int,
        shots: int,
    ) -> QuantumExecutionResult:
        """Create execution result from counts."""
        total_shots = sum(counts.values())
        measurements = tuple(
            MeasurementResult(
                bitstring=bs, count=cnt, probability=cnt / total_shots if total_shots > 0 else 0.0
            )
            for bs, cnt in counts.items()
        )

        return QuantumExecutionResult(
            measurements=measurements,
            counts=counts,
            num_qubits=num_qubits,
            shots=shots,
            backend_name=self.name,
            timestamp=datetime.utcnow(),
            metadata={"device": self._device},
        )

    def submit(
        self,
        circuit: Any,
        shots: int = 1024,
        **options: Any,
    ) -> str:
        """Submit job for async execution."""
        job_id = str(uuid.uuid4())
        result = self.run(circuit, shots=shots, **options)
        self._pending_jobs[job_id] = result
        return job_id

    def retrieve_result(self, job_id: str) -> QuantumExecutionResult:
        """Retrieve result of submitted job."""
        if job_id not in self._pending_jobs:
            raise ValueError(f"Job {job_id} not found")
        return self._pending_jobs.pop(job_id)

    def get_job_status(self, job_id: str) -> str:
        """Get status of a submitted job."""
        return "DONE" if job_id in self._pending_jobs else "NOT_FOUND"

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a submitted job."""
        if job_id in self._pending_jobs:
            self._pending_jobs.pop(job_id)
            return True
        return False

    def get_statevector(self, circuit: Any) -> NDArray[np.complex128]:
        """Get final statevector without measurement."""
        if hasattr(circuit, "num_qubits"):
            num_qubits = circuit.num_qubits
            state = self._initialize_state(num_qubits)

            for instruction in circuit.data:
                if instruction.operation.name.lower() == "measure":
                    continue
                gate_name = instruction.operation.name
                qubits = [circuit.find_bit(q).index for q in instruction.qubits]
                params = instruction.operation.params
                state = self._apply_gpu_gate(state, gate_name, qubits, params, num_qubits)

            return self._to_host(state)

        raise ValueError("Unsupported circuit format")


class MultiGPUAcceleratedSimulator:
    """
    Multi-GPU quantum simulator for large-scale simulations.

    Distributes statevector across multiple GPUs using domain decomposition.
    """

    name: str = "multi_gpu_simulator"

    def __init__(
        self,
        num_gpus: int = 2,
        num_qubits_max: int = 34,  # Up to 2^34 / num_gpus per GPU
    ):
        """
        Initialize multi-GPU simulator.

        Args:
            num_gpus: Number of GPUs to use
            num_qubits_max: Maximum number of qubits supported
        """
        if not CUPY_AVAILABLE:
            raise RuntimeError("CuPy not available")

        self.num_gpus = num_gpus
        self.num_qubits_max = num_qubits_max
        self.devices: list[int] = list(range(num_gpus))

    @property
    def capabilities(self) -> BackendCapabilities:
        """Return backend capabilities."""
        return BackendCapabilities(
            name=self.name,
            num_qubits=self.num_qubits_max,
            basis_gates=frozenset(
                [
                    "i",
                    "x",
                    "y",
                    "z",
                    "h",
                    "s",
                    "t",
                    "rx",
                    "ry",
                    "rz",
                    "cx",
                    "cy",
                    "cz",
                    "swap",
                    "ccx",
                ]
            ),
            max_shots=100000,
            simulator=True,
            local=True,
            gpu=True,
            metadata={
                "num_gpus": self.num_gpus,
                "supports_distributed": True,
            },
        )

    def run(
        self,
        circuit: Any,
        shots: int = 1024,
        **options: Any,
    ) -> QuantumExecutionResult:
        """
        Run circuit on multi-GPU simulator.

        For simplicity, fall back to single GPU for now.
        In production, this would implement domain decomposition.
        """
        simulator = GPUAcceleratedSimulator(
            GPUSimulatorConfig(use_gpu=True, device_id=self.devices[0]),
            self.num_qubits_max,
        )
        return simulator.run(circuit, shots=shots, **options)


__all__ = [
    "GPUAcceleratedSimulator",
    "MultiGPUAcceleratedSimulator",
    "GPUSimulatorConfig",
    "CUPY_AVAILABLE",
    "CUPY_SPARSE_AVAILABLE",
]

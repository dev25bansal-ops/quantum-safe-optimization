"""
IBM Quantum Backend Implementation

Provides integration with IBM Quantum via Qiskit Runtime.
Supports circuit execution, QAOA, and VQE on IBM Quantum hardware.
"""

import asyncio
import logging
import os
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

logger = logging.getLogger(__name__)


class IBMQuantumBackend(QuantumBackend):
    """
    IBM Quantum backend using Qiskit Runtime.

    Supports:
    - Circuit execution on IBM Quantum hardware
    - QAOA via Qiskit Runtime primitives
    - VQE via Qiskit Runtime primitives
    - Session management for efficient job batching
    - Error mitigation options

    Environment Variables:
    - IBM_QUANTUM_TOKEN: API token for authentication
    - IBM_QUANTUM_CHANNEL: Channel (ibm_quantum, ibm_cloud)
    - IBM_QUANTUM_INSTANCE: Instance for ibm_quantum channel (hub/group/project)
    """

    def __init__(self, config: BackendConfig):
        super().__init__(config)
        self._service = None
        self._session = None
        self._backend = None
        self._last_health_check: Optional[datetime] = None
        self._cached_backends: List[Dict[str, Any]] = []

    @property
    def backend_type(self) -> BackendType:
        return BackendType.IBM_QUANTUM

    async def connect(self) -> None:
        """Connect to IBM Quantum using Qiskit Runtime."""
        try:
            from qiskit_ibm_runtime import QiskitRuntimeService

            # Get token from config or environment
            token = self.config.api_token or os.getenv("IBM_QUANTUM_TOKEN")
            channel = self.config.extra_config.get("channel") or os.getenv(
                "IBM_QUANTUM_CHANNEL", "ibm_quantum"
            )
            instance = self.config.extra_config.get("instance") or os.getenv("IBM_QUANTUM_INSTANCE")

            if token:
                kwargs = {
                    "channel": channel,
                    "token": token,
                }
                if instance:
                    kwargs["instance"] = instance

                self._service = QiskitRuntimeService(**kwargs)
                logger.info(f"Connected to IBM Quantum via {channel}")
            else:
                # Try to use saved credentials
                try:
                    self._service = QiskitRuntimeService()
                    logger.info("Connected to IBM Quantum using saved credentials")
                except Exception:
                    raise ConnectionError(
                        "No IBM Quantum credentials found. Set IBM_QUANTUM_TOKEN environment variable."
                    )

            # Pre-fetch available backends for health check
            await self._refresh_backends_cache()

            self._is_connected = True
        except ImportError:
            raise ConnectionError(
                "qiskit-ibm-runtime not installed. Install with: pip install qiskit-ibm-runtime"
            )
        except Exception as e:
            logger.error(f"Failed to connect to IBM Quantum: {e}")
            raise ConnectionError(f"Failed to connect to IBM Quantum: {e}")

    async def disconnect(self) -> None:
        """Close IBM Quantum session."""
        if self._session:
            try:
                self._session.close()
            except Exception as e:
                logger.warning(f"Error closing session: {e}")
            self._session = None
        self._backend = None
        self._is_connected = False
        logger.info("Disconnected from IBM Quantum")

    async def health_check(self) -> bool:
        """Perform health check on the connection."""
        if not self._service:
            return False

        try:
            # Refresh backends list
            await self._refresh_backends_cache()
            self._last_health_check = datetime.utcnow()
            return len(self._cached_backends) > 0
        except Exception as e:
            logger.warning(f"IBM Quantum health check failed: {e}")
            return False

    async def _refresh_backends_cache(self) -> None:
        """Refresh the cached list of available backends."""
        loop = asyncio.get_event_loop()
        backends = await loop.run_in_executor(None, self._service.backends)
        self._cached_backends = [
            {
                "name": b.name,
                "num_qubits": b.num_qubits,
                "status": b.status().status_msg,
                "operational": b.status().operational,
                "pending_jobs": b.status().pending_jobs,
                "simulator": "simulator" in b.name.lower(),
            }
            for b in backends
        ]

    async def get_available_devices(self) -> List[Dict[str, Any]]:
        """Get list of available IBM Quantum backends."""
        if not self._service:
            raise RuntimeError("Not connected to IBM Quantum")

        # Use cache if recent enough
        if (
            self._last_health_check
            and (datetime.utcnow() - self._last_health_check).total_seconds() < 60
        ):
            return self._cached_backends

        await self._refresh_backends_cache()
        return self._cached_backends

    def _get_backend(self, device_name: Optional[str] = None):
        """Get backend instance, caching for reuse."""
        target_device = device_name or self.config.device_name or "ibm_brisbane"

        if self._backend and self._backend.name == target_device:
            return self._backend

        self._backend = self._service.backend(target_device)
        return self._backend

    async def execute_circuit(
        self,
        circuit: Any,
        shots: int = 1000,
        device_name: Optional[str] = None,
    ) -> JobResult:
        """Execute a Qiskit circuit on IBM Quantum."""
        from qiskit_ibm_runtime import SamplerV2 as Sampler

        if not self._service:
            raise RuntimeError("Not connected to IBM Quantum")

        device = device_name or self.config.device_name or "ibm_brisbane"
        backend = self._service.backend(device)

        job_id = str(uuid.uuid4())
        submitted_at = datetime.utcnow()

        try:
            sampler = Sampler(backend=backend)
            job = sampler.run([circuit], shots=shots)
            result = job.result()

            # Extract counts from result
            pub_result = result[0]
            counts = pub_result.data.meas.get_counts()

            # Calculate probabilities
            total_shots = sum(counts.values())
            probabilities = {k: v / total_shots for k, v in counts.items()}

            # Find optimal bitstring (most frequent)
            optimal_bitstring = max(counts, key=counts.get)

            return JobResult(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                backend_type=self.backend_type,
                device_name=device,
                submitted_at=submitted_at,
                completed_at=datetime.utcnow(),
                counts=counts,
                probabilities=probabilities,
                optimal_bitstring=optimal_bitstring,
                raw_result=result,
            )
        except Exception as e:
            return JobResult(
                job_id=job_id,
                status=JobStatus.FAILED,
                backend_type=self.backend_type,
                device_name=device,
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
        """Run VQE using Qiskit Runtime Estimator."""
        from qiskit_ibm_runtime import EstimatorV2 as Estimator
        from qiskit_ibm_runtime import Session
        from scipy.optimize import minimize

        if not self._service:
            raise RuntimeError("Not connected to IBM Quantum")

        device = self.config.device_name or "ibm_brisbane"
        backend = self._service.backend(device)

        job_id = str(uuid.uuid4())
        submitted_at = datetime.utcnow()
        convergence_history = []

        try:
            with Session(backend=backend) as session:
                estimator = Estimator(session=session)

                num_params = ansatz.num_parameters
                if initial_params is None:
                    initial_params = np.random.uniform(-np.pi, np.pi, num_params)

                def cost_function(params):
                    bound_circuit = ansatz.assign_parameters(params)
                    job = estimator.run([(bound_circuit, hamiltonian)])
                    result = job.result()
                    energy = result[0].data.evs
                    convergence_history.append(float(energy))
                    return energy

                result = minimize(
                    cost_function,
                    initial_params,
                    method=optimizer,
                    options={"maxiter": max_iterations},
                )

                return JobResult(
                    job_id=job_id,
                    status=JobStatus.COMPLETED,
                    backend_type=self.backend_type,
                    device_name=device,
                    submitted_at=submitted_at,
                    completed_at=datetime.utcnow(),
                    optimal_value=float(result.fun),
                    optimal_params=result.x,
                    convergence_history=convergence_history,
                )
        except Exception as e:
            return JobResult(
                job_id=job_id,
                status=JobStatus.FAILED,
                backend_type=self.backend_type,
                device_name=device,
                submitted_at=submitted_at,
                completed_at=datetime.utcnow(),
                error_message=str(e),
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
        """Run QAOA using Qiskit Runtime."""
        from qiskit.circuit import Parameter, QuantumCircuit
        from qiskit_ibm_runtime import SamplerV2 as Sampler
        from qiskit_ibm_runtime import Session
        from scipy.optimize import minimize

        if not self._service:
            raise RuntimeError("Not connected to IBM Quantum")

        device = self.config.device_name or "ibm_brisbane"
        backend = self._service.backend(device)

        job_id = str(uuid.uuid4())
        submitted_at = datetime.utcnow()
        convergence_history = []

        try:
            # Build QAOA circuit
            num_qubits = cost_hamiltonian.num_qubits

            gammas = [Parameter(f"γ_{i}") for i in range(layers)]
            betas = [Parameter(f"β_{i}") for i in range(layers)]

            qc = QuantumCircuit(num_qubits)

            # Initial state: uniform superposition
            qc.h(range(num_qubits))

            # QAOA layers
            for layer in range(layers):
                # Cost unitary
                qc.compose(cost_hamiltonian.to_circuit(gammas[layer]), inplace=True)
                # Mixer unitary
                for q in range(num_qubits):
                    qc.rx(2 * betas[layer], q)

            qc.measure_all()

            # Initialize parameters
            num_params = 2 * layers
            if initial_params is None:
                initial_params = np.random.uniform(0, np.pi, num_params)

            with Session(backend=backend) as session:
                sampler = Sampler(session=session)

                def cost_function(params):
                    gamma_vals = params[:layers]
                    beta_vals = params[layers:]

                    param_dict = {}
                    for i, (g, b) in enumerate(zip(gammas, betas)):
                        param_dict[g] = gamma_vals[i]
                        param_dict[b] = beta_vals[i]

                    bound_circuit = qc.assign_parameters(param_dict)
                    job = sampler.run([bound_circuit], shots=shots)
                    result = job.result()

                    counts = result[0].data.meas.get_counts()

                    # Compute expectation value
                    expectation = 0.0
                    total = sum(counts.values())
                    for bitstring, count in counts.items():
                        # Evaluate cost function for this bitstring
                        cost = self._evaluate_cost(bitstring, cost_hamiltonian)
                        expectation += cost * count / total

                    convergence_history.append(expectation)
                    return expectation

                result = minimize(
                    cost_function,
                    initial_params,
                    method=optimizer,
                    options={"maxiter": 100},
                )

                # Get final bitstring distribution
                gamma_vals = result.x[:layers]
                beta_vals = result.x[layers:]
                param_dict = {}
                for i, (g, b) in enumerate(zip(gammas, betas)):
                    param_dict[g] = gamma_vals[i]
                    param_dict[b] = beta_vals[i]

                final_circuit = qc.assign_parameters(param_dict)
                final_job = sampler.run([final_circuit], shots=shots)
                final_result = final_job.result()
                final_counts = final_result[0].data.meas.get_counts()

                optimal_bitstring = max(final_counts, key=final_counts.get)

                return JobResult(
                    job_id=job_id,
                    status=JobStatus.COMPLETED,
                    backend_type=self.backend_type,
                    device_name=device,
                    submitted_at=submitted_at,
                    completed_at=datetime.utcnow(),
                    optimal_value=float(result.fun),
                    optimal_params=result.x,
                    optimal_bitstring=optimal_bitstring,
                    counts=final_counts,
                    convergence_history=convergence_history,
                )
        except Exception as e:
            return JobResult(
                job_id=job_id,
                status=JobStatus.FAILED,
                backend_type=self.backend_type,
                device_name=device,
                submitted_at=submitted_at,
                completed_at=datetime.utcnow(),
                error_message=str(e),
            )

    def _evaluate_cost(self, bitstring: str, hamiltonian: Any) -> float:
        """Evaluate the cost Hamiltonian for a given bitstring."""
        # This is a simplified implementation
        # In practice, evaluate the Hamiltonian expectation
        x = np.array([int(b) for b in bitstring])
        return float(np.sum(x))  # Placeholder

    async def get_job_status(self, job_id: str) -> JobStatus:
        """Get status of an IBM Quantum job."""
        if not self._service:
            raise RuntimeError("Not connected to IBM Quantum")

        try:
            job = self._service.job(job_id)
            status_map = {
                "QUEUED": JobStatus.QUEUED,
                "RUNNING": JobStatus.RUNNING,
                "DONE": JobStatus.COMPLETED,
                "ERROR": JobStatus.FAILED,
                "CANCELLED": JobStatus.CANCELLED,
            }
            return status_map.get(job.status().name, JobStatus.QUEUED)
        except Exception:
            return JobStatus.FAILED

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel an IBM Quantum job."""
        if not self._service:
            raise RuntimeError("Not connected to IBM Quantum")

        try:
            job = self._service.job(job_id)
            job.cancel()
            return True
        except Exception:
            return False

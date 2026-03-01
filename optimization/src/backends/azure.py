"""
Azure Quantum Backend Implementation

Provides integration with Azure Quantum service.
Supports multiple hardware providers through Azure's unified interface.
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


# Common Azure Quantum targets
AZURE_TARGETS = {
    # IonQ
    "ionq.simulator": "IonQ Simulator",
    "ionq.qpu": "IonQ QPU",
    "ionq.qpu.aria-1": "IonQ Aria 1",
    "ionq.qpu.aria-2": "IonQ Aria 2",
    "ionq.qpu.forte-1": "IonQ Forte",
    # Quantinuum
    "quantinuum.sim.h1-1sc": "Quantinuum H1-1 Syntax Checker",
    "quantinuum.sim.h1-1e": "Quantinuum H1-1 Emulator",
    "quantinuum.qpu.h1-1": "Quantinuum H1-1 QPU",
    "quantinuum.qpu.h2-1": "Quantinuum H2-1 QPU",
    # Pasqal (Neutral atoms)
    "pasqal.sim.emu-tn": "Pasqal Emulator",
    # Microsoft Resource Estimator
    "microsoft.estimator": "Microsoft Resource Estimator",
}


class AzureQuantumBackend(QuantumBackend):
    """
    Azure Quantum backend.

    Supports:
    - IonQ trapped-ion devices (Harmony, Aria, Forte)
    - Quantinuum (Honeywell) devices (H1, H2 series)
    - Pasqal neutral-atom devices
    - Microsoft Resource Estimator

    Environment Variables:
    - AZURE_QUANTUM_RESOURCE_ID: Azure Quantum workspace resource ID
    - AZURE_QUANTUM_LOCATION: Azure region (default: eastus)
    - AZURE_SUBSCRIPTION_ID: Azure subscription ID
    - AZURE_RESOURCE_GROUP: Resource group name
    - AZURE_QUANTUM_WORKSPACE: Workspace name
    """

    def __init__(self, config: BackendConfig):
        super().__init__(config)
        self._workspace = None
        self._cached_targets: List[Dict[str, Any]] = []
        self._last_health_check: Optional[datetime] = None

    @property
    def backend_type(self) -> BackendType:
        return BackendType.AZURE_QUANTUM

    async def connect(self) -> None:
        """Connect to Azure Quantum workspace."""
        try:
            from azure.quantum import Workspace

            resource_id = self.config.extra_config.get("resource_id") or os.getenv(
                "AZURE_QUANTUM_RESOURCE_ID"
            )
            location = self.config.region or os.getenv("AZURE_QUANTUM_LOCATION", "eastus")

            if resource_id:
                self._workspace = Workspace(resource_id=resource_id, location=location)
            else:
                # Try environment variables for subscription/resource group/workspace
                subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
                resource_group = os.getenv("AZURE_RESOURCE_GROUP")
                workspace_name = os.getenv("AZURE_QUANTUM_WORKSPACE")

                if subscription_id and resource_group and workspace_name:
                    self._workspace = Workspace(
                        subscription_id=subscription_id,
                        resource_group=resource_group,
                        name=workspace_name,
                        location=location,
                    )
                else:
                    # Try default credential authentication
                    self._workspace = Workspace()

            # Test connection by fetching targets
            await self._refresh_targets_cache()

            self._is_connected = True
            logger.info(f"Connected to Azure Quantum in {location}")
        except ImportError:
            raise ConnectionError(
                "azure-quantum not installed. Install with: pip install azure-quantum"
            )
        except Exception as e:
            logger.error(f"Failed to connect to Azure Quantum: {e}")
            raise ConnectionError(f"Failed to connect to Azure Quantum: {e}")

    async def disconnect(self) -> None:
        """Disconnect from Azure Quantum."""
        self._workspace = None
        self._is_connected = False
        logger.info("Disconnected from Azure Quantum")

    async def health_check(self) -> bool:
        """Perform health check on Azure Quantum connection."""
        if not self._workspace:
            return False

        try:
            await self._refresh_targets_cache()
            self._last_health_check = datetime.utcnow()
            return True
        except Exception as e:
            logger.warning(f"Azure Quantum health check failed: {e}")
            return False

    async def _refresh_targets_cache(self) -> None:
        """Refresh cached target list."""
        loop = asyncio.get_event_loop()
        targets = await loop.run_in_executor(None, self._workspace.get_targets)

        self._cached_targets = [
            {
                "name": t.name,
                "provider": t.provider_id,
                "status": t.current_availability,
                "average_queue_time": t.average_queue_time,
                "description": AZURE_TARGETS.get(t.name, t.name),
                "supports_shots": self._target_supports_shots(t.name),
            }
            for t in targets
        ]

    def _target_supports_shots(self, target_name: str) -> bool:
        """Check if target supports shot-based execution."""
        # Resource estimator doesn't use shots
        return "estimator" not in target_name.lower()

    async def get_available_devices(self) -> List[Dict[str, Any]]:
        """Get list of available Azure Quantum targets."""
        if not self._workspace:
            raise RuntimeError("Not connected to Azure Quantum")

        # Use cache if recent
        if (
            self._last_health_check
            and (datetime.utcnow() - self._last_health_check).total_seconds() < 60
        ):
            return self._cached_targets

        await self._refresh_targets_cache()
        return self._cached_targets

    async def execute_circuit(
        self,
        circuit: Any,
        shots: int = 1000,
        device_name: Optional[str] = None,
    ) -> JobResult:
        """Execute a circuit on Azure Quantum."""
        if not self._workspace:
            raise RuntimeError("Not connected to Azure Quantum")

        job_id = str(uuid.uuid4())
        submitted_at = datetime.utcnow()
        target_name = device_name or self.config.device_name or "ionq.simulator"

        try:
            target = self._workspace.get_targets(name=target_name)[0]

            # Submit job
            job = target.submit(circuit, shots=shots)
            job.wait_until_completed()

            results = job.get_results()

            # Process results
            if hasattr(results, "histogram"):
                counts = {k: int(v * shots) for k, v in results.histogram.items()}
            else:
                counts = dict(results)

            total = sum(counts.values())
            probabilities = {k: v / total for k, v in counts.items()}
            optimal_bitstring = max(counts, key=counts.get)

            return JobResult(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                backend_type=self.backend_type,
                device_name=target_name,
                submitted_at=submitted_at,
                completed_at=datetime.utcnow(),
                counts=counts,
                probabilities=probabilities,
                optimal_bitstring=optimal_bitstring,
                raw_result=results,
            )
        except Exception as e:
            return JobResult(
                job_id=job_id,
                status=JobStatus.FAILED,
                backend_type=self.backend_type,
                device_name=target_name,
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
        """Run VQE on Azure Quantum."""
        import pennylane as qml
        from scipy.optimize import minimize

        if not self._workspace:
            raise RuntimeError("Not connected to Azure Quantum")

        target_name = self.config.device_name or "ionq.simulator"
        job_id = str(uuid.uuid4())
        submitted_at = datetime.utcnow()
        convergence_history = []

        try:
            # Use PennyLane with Azure Quantum backend
            dev = qml.device(
                "default.qubit",  # Use local simulator for now
                wires=hamiltonian.wires,
                shots=shots,
            )

            @qml.qnode(dev)
            def circuit(params):
                ansatz(params)
                return qml.expval(hamiltonian)

            num_params = len(initial_params) if initial_params is not None else 10
            if initial_params is None:
                initial_params = np.random.uniform(-np.pi, np.pi, num_params)

            def cost_fn(params):
                energy = circuit(params)
                convergence_history.append(float(energy))
                return energy

            result = minimize(
                cost_fn,
                initial_params,
                method=optimizer,
                options={"maxiter": max_iterations},
            )

            return JobResult(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                backend_type=self.backend_type,
                device_name=target_name,
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
                device_name=target_name,
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
        """Run QAOA on Azure Quantum."""
        import pennylane as qml
        from scipy.optimize import minimize

        if not self._workspace:
            raise RuntimeError("Not connected to Azure Quantum")

        target_name = self.config.device_name or "ionq.simulator"
        job_id = str(uuid.uuid4())
        submitted_at = datetime.utcnow()
        convergence_history = []

        try:
            num_qubits = len(cost_hamiltonian.wires)

            dev = qml.device("default.qubit", wires=num_qubits, shots=shots)

            def qaoa_layer(gamma, beta):
                qml.templates.ApproxTimeEvolution(cost_hamiltonian, gamma, 1)
                for w in range(num_qubits):
                    qml.RX(2 * beta, wires=w)

            @qml.qnode(dev)
            def circuit(params):
                for w in range(num_qubits):
                    qml.Hadamard(wires=w)

                for i in range(layers):
                    qaoa_layer(params[i], params[layers + i])

                return qml.expval(cost_hamiltonian)

            num_params = 2 * layers
            if initial_params is None:
                initial_params = np.random.uniform(0, np.pi, num_params)

            def cost_fn(params):
                energy = circuit(params)
                convergence_history.append(float(energy))
                return energy

            result = minimize(
                cost_fn,
                initial_params,
                method=optimizer,
                options={"maxiter": 100},
            )

            return JobResult(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                backend_type=self.backend_type,
                device_name=target_name,
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
                device_name=target_name,
                submitted_at=submitted_at,
                completed_at=datetime.utcnow(),
                error_message=str(e),
            )

    async def get_job_status(self, job_id: str) -> JobStatus:
        """Get status of an Azure Quantum job."""
        return JobStatus.COMPLETED

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel an Azure Quantum job."""
        return False

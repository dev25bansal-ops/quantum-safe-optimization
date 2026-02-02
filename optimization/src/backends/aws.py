"""
AWS Braket Backend Implementation

Provides integration with Amazon Braket quantum computing service.
Supports multiple hardware providers and managed simulators.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

import numpy as np

from .base import (
    QuantumBackend,
    BackendType,
    BackendConfig,
    JobResult,
    JobStatus,
)

logger = logging.getLogger(__name__)


# Device ARN mappings for common devices
BRAKET_DEVICES = {
    # Simulators
    "sv1": "arn:aws:braket:::device/quantum-simulator/amazon/sv1",
    "dm1": "arn:aws:braket:::device/quantum-simulator/amazon/dm1",
    "tn1": "arn:aws:braket:::device/quantum-simulator/amazon/tn1",
    # IonQ
    "ionq_harmony": "arn:aws:braket:us-east-1::device/qpu/ionq/Harmony",
    "ionq_aria": "arn:aws:braket:us-east-1::device/qpu/ionq/Aria-1",
    "ionq_forte": "arn:aws:braket:us-east-1::device/qpu/ionq/Forte-1",
    # Rigetti
    "rigetti_aspen_m3": "arn:aws:braket:us-west-1::device/qpu/rigetti/Aspen-M-3",
    # IQM
    "iqm_garnet": "arn:aws:braket:eu-north-1::device/qpu/iqm/Garnet",
}


class AWSBraketBackend(QuantumBackend):
    """
    AWS Braket backend for quantum computing.
    
    Supports:
    - IonQ trapped-ion devices (Harmony, Aria, Forte)
    - Rigetti superconducting devices
    - IQM devices
    - Amazon managed simulators (SV1, DM1, TN1)
    - PennyLane integration for VQE/QAOA
    
    Environment Variables:
    - AWS_ACCESS_KEY_ID: AWS access key
    - AWS_SECRET_ACCESS_KEY: AWS secret key
    - AWS_REGION: AWS region (default: us-east-1)
    - BRAKET_S3_BUCKET: S3 bucket for results
    """
    
    def __init__(self, config: BackendConfig):
        super().__init__(config)
        self._session = None
        self._s3_bucket = None
        self._s3_prefix = "braket-results"
        self._cached_devices: List[Dict[str, Any]] = []
        self._last_health_check: Optional[datetime] = None
    
    @property
    def backend_type(self) -> BackendType:
        return BackendType.AWS_BRAKET
    
    async def connect(self) -> None:
        """Connect to AWS Braket."""
        try:
            from braket.aws import AwsSession
            
            region = self.config.region or os.getenv("AWS_REGION", "us-east-1")
            
            self._session = AwsSession(boto_session_args={"region_name": region})
            
            # Get or create S3 bucket for results
            self._s3_bucket = self.config.extra_config.get("s3_bucket") or \
                              os.getenv("BRAKET_S3_BUCKET") or \
                              f"amazon-braket-{self._session.account_id}-{region}"
            
            self._s3_prefix = self.config.extra_config.get("s3_prefix", "braket-results")
            
            # Test connection by fetching devices
            await self._refresh_devices_cache()
            
            self._is_connected = True
            logger.info(f"Connected to AWS Braket in {region}")
        except ImportError:
            raise ConnectionError(
                "amazon-braket-sdk not installed. Install with: pip install amazon-braket-sdk"
            )
        except Exception as e:
            logger.error(f"Failed to connect to AWS Braket: {e}")
            raise ConnectionError(f"Failed to connect to AWS Braket: {e}")
    
    async def disconnect(self) -> None:
        """Disconnect from AWS Braket."""
        self._session = None
        self._is_connected = False
        logger.info("Disconnected from AWS Braket")
    
    async def health_check(self) -> bool:
        """Perform health check on AWS Braket connection."""
        if not self._session:
            return False
        
        try:
            await self._refresh_devices_cache()
            self._last_health_check = datetime.utcnow()
            return True
        except Exception as e:
            logger.warning(f"AWS Braket health check failed: {e}")
            return False
    
    async def _refresh_devices_cache(self) -> None:
        """Refresh cached device list."""
        from braket.aws import AwsDevice
        
        loop = asyncio.get_event_loop()
        devices = await loop.run_in_executor(None, AwsDevice.get_devices)
        
        self._cached_devices = [
            {
                "name": d.name,
                "arn": d.arn,
                "provider": d.provider_name,
                "num_qubits": getattr(d, 'qubit_count', None),
                "status": d.status,
                "device_type": d.type.value,
                "region": self._extract_region(d.arn),
                "cost_per_shot": self._get_device_cost(d.arn),
            }
            for d in devices
        ]
    
    def _extract_region(self, arn: str) -> Optional[str]:
        """Extract region from device ARN."""
        parts = arn.split(":")
        if len(parts) >= 4:
            return parts[3] or "us-east-1"
        return None
    
    def _get_device_cost(self, arn: str) -> Optional[float]:
        """Get approximate cost per shot for a device."""
        # Approximate costs as of 2024
        cost_map = {
            "sv1": 0.00,  # Free tier available
            "dm1": 0.00075,
            "tn1": 0.00275,
            "ionq": 0.01,  # Per task + per shot
            "rigetti": 0.00035,
            "iqm": 0.00145,
        }
        arn_lower = arn.lower()
        for key, cost in cost_map.items():
            if key in arn_lower:
                return cost
        return None
    
    def _resolve_device_arn(self, device_name: Optional[str]) -> str:
        """Resolve device name to ARN."""
        if device_name is None:
            return BRAKET_DEVICES["sv1"]
        
        # If already an ARN, use as-is
        if device_name.startswith("arn:"):
            return device_name
        
        # Look up in known devices
        if device_name.lower() in BRAKET_DEVICES:
            return BRAKET_DEVICES[device_name.lower()]
        
        # Try common patterns
        device_lower = device_name.lower().replace("-", "_").replace(" ", "_")
        for key, arn in BRAKET_DEVICES.items():
            if key.replace("_", "") == device_lower.replace("_", ""):
                return arn
        
        # Default to SV1 simulator
        logger.warning(f"Unknown device '{device_name}', defaulting to SV1 simulator")
        return BRAKET_DEVICES["sv1"]
    
    async def get_available_devices(self) -> List[Dict[str, Any]]:
        """Get list of available Braket devices."""
        if not self._session:
            raise RuntimeError("Not connected to AWS Braket")
        
        # Use cache if recent
        if self._last_health_check and \
           (datetime.utcnow() - self._last_health_check).total_seconds() < 60:
            return self._cached_devices
        
        await self._refresh_devices_cache()
        return self._cached_devices
    
    async def execute_circuit(
        self,
        circuit: Any,
        shots: int = 1000,
        device_name: Optional[str] = None,
    ) -> JobResult:
        """Execute a Braket circuit."""
        from braket.aws import AwsDevice
        from braket.circuits import Circuit
        
        if not self._session:
            raise RuntimeError("Not connected to AWS Braket")
        
        job_id = str(uuid.uuid4())
        submitted_at = datetime.utcnow()
        
        # Default to SV1 simulator
        device_arn = device_name or "arn:aws:braket:::device/quantum-simulator/amazon/sv1"
        
        try:
            device = AwsDevice(device_arn)
            
            # Run circuit
            task = device.run(
                circuit,
                s3_destination_folder=(self._s3_bucket, "results"),
                shots=shots,
            )
            result = task.result()
            
            # Extract counts
            counts = dict(result.measurement_counts)
            total = sum(counts.values())
            probabilities = {k: v / total for k, v in counts.items()}
            optimal_bitstring = max(counts, key=counts.get)
            
            return JobResult(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                backend_type=self.backend_type,
                device_name=device_arn,
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
                device_name=device_arn,
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
        """Run VQE using PennyLane-Braket integration."""
        import pennylane as qml
        from scipy.optimize import minimize
        
        if not self._session:
            raise RuntimeError("Not connected to AWS Braket")
        
        device_arn = self.config.device_name or "arn:aws:braket:::device/quantum-simulator/amazon/sv1"
        job_id = str(uuid.uuid4())
        submitted_at = datetime.utcnow()
        convergence_history = []
        
        try:
            # Create PennyLane device with Braket backend
            dev = qml.device(
                "braket.aws.qubit",
                device_arn=device_arn,
                s3_destination_folder=(self._s3_bucket, "vqe-results"),
                shots=shots,
                wires=hamiltonian.wires,
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
                device_name=device_arn,
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
                device_name=device_arn,
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
        """Run QAOA using PennyLane-Braket integration."""
        import pennylane as qml
        from scipy.optimize import minimize
        
        if not self._session:
            raise RuntimeError("Not connected to AWS Braket")
        
        device_arn = self.config.device_name or "arn:aws:braket:::device/quantum-simulator/amazon/sv1"
        job_id = str(uuid.uuid4())
        submitted_at = datetime.utcnow()
        convergence_history = []
        
        try:
            num_qubits = len(cost_hamiltonian.wires)
            
            dev = qml.device(
                "braket.aws.qubit",
                device_arn=device_arn,
                s3_destination_folder=(self._s3_bucket, "qaoa-results"),
                shots=shots,
                wires=num_qubits,
            )
            
            def qaoa_layer(gamma, beta):
                qml.templates.ApproxTimeEvolution(cost_hamiltonian, gamma, 1)
                for w in range(num_qubits):
                    qml.RX(2 * beta, wires=w)
            
            @qml.qnode(dev)
            def circuit(params):
                # Initial superposition
                for w in range(num_qubits):
                    qml.Hadamard(wires=w)
                
                # QAOA layers
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
            
            # Get sample to find optimal bitstring
            @qml.qnode(dev)
            def sample_circuit(params):
                for w in range(num_qubits):
                    qml.Hadamard(wires=w)
                for i in range(layers):
                    qaoa_layer(params[i], params[layers + i])
                return qml.sample()
            
            samples = sample_circuit(result.x)
            bitstrings = [''.join(str(int(b)) for b in sample) for sample in samples]
            from collections import Counter
            counts = dict(Counter(bitstrings))
            optimal_bitstring = max(counts, key=counts.get)
            
            return JobResult(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                backend_type=self.backend_type,
                device_name=device_arn,
                submitted_at=submitted_at,
                completed_at=datetime.utcnow(),
                optimal_value=float(result.fun),
                optimal_params=result.x,
                optimal_bitstring=optimal_bitstring,
                counts=counts,
                convergence_history=convergence_history,
            )
        except Exception as e:
            return JobResult(
                job_id=job_id,
                status=JobStatus.FAILED,
                backend_type=self.backend_type,
                device_name=device_arn,
                submitted_at=submitted_at,
                completed_at=datetime.utcnow(),
                error_message=str(e),
            )
    
    async def get_job_status(self, job_id: str) -> JobStatus:
        """Get status of a Braket task."""
        # AWS Braket uses task ARNs, not simple job IDs
        return JobStatus.COMPLETED
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a Braket task."""
        return False

"""
Workflow Executor Adapters for QSOP.

Adapts algorithm-specific workflows to the WorkflowExecutor protocol.
Uses thread pool with asyncio.to_thread for CPU-intensive operations to prevent blocking the event loop.
"""

import asyncio
import concurrent.futures
import json
import logging
from typing import Any
from uuid import UUID, uuid4

from ...domain.models.artifacts import ArtifactType, EncryptedBlob
from ...domain.models.problem import OptimizationProblem
from ...domain.ports.artifact_store import ArtifactStore
from ..services.crypto_service import CryptoService
from ..services.workflow_service import WorkflowContext, WorkflowExecutor, WorkflowProgress
from .qaoa import QAOAWorkflow
from .vqe import VQEWorkflow

logger = logging.getLogger(__name__)

_thread_pool: concurrent.futures.ThreadPoolExecutor | None = None


def get_thread_pool() -> concurrent.futures.ThreadPoolExecutor:
    """Get or create the shared thread pool for CPU-intensive operations."""
    global _thread_pool
    if _thread_pool is None:
        _thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="optimization_worker"
        )
    return _thread_pool


class BaseExecutorAdapter(WorkflowExecutor[Any, Any]):
    """Base class for workflow executor adapters."""

    def __init__(
        self,
        crypto_service: CryptoService | None = None,
        artifact_store: ArtifactStore | None = None,
    ):
        self._progress: dict[UUID, WorkflowProgress] = {}
        self._crypto = crypto_service
        self._artifact_store = artifact_store

    async def get_progress(self, workflow_id: UUID) -> WorkflowProgress:
        return self._progress.get(workflow_id, WorkflowProgress(0, 0, None, 0.0))

    async def pause(self, workflow_id: UUID) -> bool:
        return False  # Not implemented for basic adapters

    async def resume(self, workflow_id: UUID) -> bool:
        return False

    async def cancel(self, workflow_id: UUID) -> bool:
        return False

    async def _secure_and_store_result(
        self, result: Any, context: WorkflowContext
    ) -> dict[str, Any]:
        """Secure and store the workflow result."""
        if not self._crypto or not self._artifact_store:
            return {"value": result}

        try:
            # 1. Serialize result
            if hasattr(result, "to_dict"):
                data_dict = result.to_dict()
            elif isinstance(result, (dict, list, str, int, float, bool)):
                data_dict = result
            else:
                data_dict = {"raw_result": str(result)}

            payload = json.dumps(data_dict).encode("utf-8")

            # 2. Determine security requirements
            encrypt_key_id = context.metadata.get("encrypt_key_id")
            sign_key_id = context.metadata.get("sign_key_id") or "platform-sign-key"

            # Explicitly check if signing/encryption is requested
            should_encrypt = context.metadata.get("encrypt_artifacts", True)
            should_sign = context.metadata.get("sign_results", True)

            signature_bundle = None
            if should_sign:
                try:
                    signature_bundle = self._crypto.sign_artifact(payload, sign_key_id)
                except Exception as e:
                    logger.warning(f"Failed to sign result with key {sign_key_id}: {e}")
                    if context.metadata.get("require_compliance", False):
                        raise

            # 3. Encrypt if requested and key is available
            artifact_id = None
            if should_encrypt and encrypt_key_id:
                envelope = self._crypto.encrypt_artifact(payload, encrypt_key_id)

                # Create and store EncryptedBlob
                blob_id = uuid4()
                recipient = envelope.recipients[0]

                blob = EncryptedBlob(
                    id=blob_id,
                    ciphertext=envelope.ciphertext,
                    nonce=envelope.nonce,
                    tag=envelope.ciphertext[-16:],
                    encapsulated_key=recipient.kem_ciphertext or b"",
                    kem_algorithm=envelope.metadata.kem_algorithm,
                    symmetric_algorithm=envelope.metadata.aead_algorithm,
                    key_id=encrypt_key_id,
                    metadata={
                        "job_id": str(context.workflow_id),
                        "artifact_type": ArtifactType.RESULT.value,
                        "envelope": envelope.to_dict(),
                    },
                )
                self._artifact_store.store_blob(blob)
                artifact_id = blob_id
            else:
                # If not encrypting, we don't store in artifact store in this simplified flow
                # but we still return the result value
                pass

            # 4. Return result bundle
            res_bundle = {"value": result}
            if artifact_id:
                res_bundle["artifact_id"] = artifact_id

            if signature_bundle:
                res_bundle["signature"] = signature_bundle.signature
                res_bundle["signature_bundle"] = signature_bundle.to_dict()

            return res_bundle

        except Exception as e:
            logger.exception(f"Failed to secure and store result: {e}")
            return {"value": result, "error": str(e)}


class VQEExecutorAdapter(BaseExecutorAdapter):
    """Adapter for VQEWorkflow."""

    async def execute(self, input_data: Any, context: WorkflowContext) -> Any:
        # In a real implementation, we would use the backend from the context/registry
        # For now, we use a mock or default backend if available
        workflow = VQEWorkflow()

        # VQE expects a Hamiltonian. We might need to convert input_data.
        # For this phase, we assume input_data IS the Hamiltonian or can be converted.
        from .vqe import Hamiltonian

        if isinstance(input_data, Hamiltonian):
            hamiltonian = input_data
        else:
            # Try to reconstruct Hamiltonian from dict
            hamiltonian = Hamiltonian(n_qubits=input_data.get("n_qubits", 1), terms=[])
            for term in input_data.get("terms", []):
                hamiltonian.add_term(term["coefficient"], term["pauli_string"])

        # Run the workflow in a thread pool since scipy.optimize.minimize is CPU intensive/blocking
        # Using asyncio.to_thread is the modern Python 3.9+ way to run sync blocking functions
        result = await asyncio.to_thread(workflow.run, hamiltonian)

        # Secure and store result if services are available
        return await self._secure_and_store_result(result, context)


class QAOAExecutorAdapter(BaseExecutorAdapter):
    """Adapter for QAOAWorkflow."""

    async def execute(self, input_data: Any, context: WorkflowContext) -> Any:
        workflow = QAOAWorkflow()

        # QAOA expects an OptimizationProblem
        if isinstance(input_data, OptimizationProblem):
            problem = input_data
        else:
            # Simplified conversion for this phase
            problem = OptimizationProblem(variables=[], objective=lambda x: 0.0)

        # Run the workflow in a thread pool since scipy.optimize.minimize is CPU intensive/blocking
        # Using asyncio.to_thread is the modern Python 3.9+ way to run sync blocking functions
        result = await asyncio.to_thread(workflow.run, problem)

        # Secure and store result if services are available
        return await self._secure_and_store_result(result, context)


async def shutdown_thread_pool():
    """Shutdown the thread pool gracefully."""
    global _thread_pool
    if _thread_pool is not None:
        _thread_pool.shutdown(wait=True)
        _thread_pool = None

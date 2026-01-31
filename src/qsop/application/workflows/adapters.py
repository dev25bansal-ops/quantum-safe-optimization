"""
Workflow Executor Adapters for QSOP.

Adapts algorithm-specific workflows to the WorkflowExecutor protocol.
"""

from typing import Any, Dict, Optional
from uuid import UUID
import asyncio

from .vqe import VQEWorkflow, VQEWorkflowConfig
from .qaoa import QAOAWorkflow, QAOAWorkflowConfig
from ..services.workflow_service import (
    WorkflowExecutor, 
    WorkflowContext, 
    WorkflowProgress,
    WorkflowStep,
    StepStatus
)
from ...domain.models.problem import OptimizationProblem


from typing import Any, Dict, Optional, Tuple, Union
from uuid import UUID, uuid4
import asyncio
import json
import logging

from .vqe import VQEWorkflow, VQEWorkflowConfig
from .qaoa import QAOAWorkflow, QAOAWorkflowConfig
from ..services.workflow_service import (
    WorkflowExecutor, 
    WorkflowContext, 
    WorkflowProgress,
    WorkflowStep,
    StepStatus
)
from ..services.crypto_service import CryptoService
from ...domain.ports.artifact_store import ArtifactStore
from ...domain.models.artifacts import EncryptedBlob, ArtifactType
from ...domain.models.problem import OptimizationProblem

logger = logging.getLogger(__name__)


class BaseExecutorAdapter(WorkflowExecutor[Any, Any]):
    """Base class for workflow executor adapters."""
    
    def __init__(
        self, 
        crypto_service: Optional[CryptoService] = None, 
        artifact_store: Optional[ArtifactStore] = None
    ):
        self._progress: Dict[UUID, WorkflowProgress] = {}
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

    async def _secure_and_store_result(self, result: Any, context: WorkflowContext) -> Dict[str, Any]:
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
                        "envelope": envelope.to_dict()
                    }
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
            hamiltonian = Hamiltonian(
                n_qubits=input_data.get("n_qubits", 1),
                terms=[]
            )
            for term in input_data.get("terms", []):
                hamiltonian.add_term(term["coefficient"], term["pauli_string"])
        
        # Run the workflow in a thread pool since it might be CPU intensive/blocking
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, workflow.run, hamiltonian)
        
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
            problem = OptimizationProblem(
                variables=[],
                objective=lambda x: 0.0
            )
        
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, workflow.run, problem)
        
        # Secure and store result if services are available
        return await self._secure_and_store_result(result, context)

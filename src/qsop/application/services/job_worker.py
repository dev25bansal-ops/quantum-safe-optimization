"""
Job Worker for QSOP.

Consumes job.created events and orchestrates workflow execution.
"""

import logging
from typing import Optional
from uuid import UUID

from qsop.domain.models.job import JobResult, JobStatus
from qsop.domain.ports.artifact_store import ArtifactStore
from qsop.domain.ports.event_bus import DomainEvent, EventBus, EventTypes
from qsop.domain.ports.job_store import JobStore

from ..workflows.registry import WorkflowRegistry
from .crypto_service import CryptoService
from .workflow_service import WorkflowContext, WorkflowService

logger = logging.getLogger(__name__)


class JobWorker:
    """
    Background worker that listens for new jobs and triggers their execution.
    """

    def __init__(
        self,
        event_bus: EventBus,
        job_store: JobStore,
        workflow_service: WorkflowService,
        registry: WorkflowRegistry,
        crypto_service: Optional[CryptoService] = None,
        artifact_store: Optional[ArtifactStore] = None,
    ):
        self._event_bus = event_bus
        self._job_store = job_store
        self._workflow_service = workflow_service
        self._registry = registry
        self._crypto = crypto_service
        self._artifact_store = artifact_store
        self._is_running = False

    async def start(self):
        """Start the worker."""
        if self._is_running:
            return

        logger.info("Starting JobWorker...")
        self._event_bus.subscribe(EventTypes.JOB_CREATED, self._handle_job_created)
        self._is_running = True

    async def stop(self):
        """Stop the worker."""
        if not self._is_running:
            return

        logger.info("Stopping JobWorker...")
        self._event_bus.unsubscribe(EventTypes.JOB_CREATED, self._handle_job_created)
        self._is_running = False

    async def _handle_job_created(self, event: DomainEvent):
        """Handle job.created event."""
        job_id_str = event.payload.get("job_id")
        if not job_id_str:
            logger.error("Received job.created event without job_id")
            return

        job_id = UUID(job_id_str)
        tenant_id = event.payload.get("tenant_id", "default")
        algorithm_name = event.payload.get("algorithm")

        logger.info(f"Processing job {job_id} for algorithm {algorithm_name}")

        try:
            # 1. Retrieve job spec
            spec = await self._job_store.get_spec(job_id)

            # 2. Get workflow components from registry
            workflow_components = self._registry.get(algorithm_name)
            if not workflow_components:
                logger.error(f"No workflow registered for algorithm: {algorithm_name}")
                await self._job_store.update_status(job_id, JobStatus.FAILED)
                return

            definition, executor_cls = workflow_components

            # 3. Update status to QUEUED then RUNNING
            await self._job_store.update_status(job_id, JobStatus.RUNNING)

            # 4. Prepare workflow context
            context = WorkflowContext(
                workflow_id=job_id,  # Reusing job_id as workflow_id for simplicity
                tenant_id=tenant_id,
                parameters=spec.algorithm.algorithm_params,
                metadata={
                    "job_id": str(job_id),
                    "backend": spec.backend.backend_name if spec.backend else "classical",
                    "encrypt_key_id": spec.crypto.key_id if spec.crypto else None,
                    "sign_key_id": "platform-sign-key",  # Default platform signing key for now
                    "encrypt_artifacts": spec.crypto.encrypt_artifacts if spec.crypto else True,
                    "sign_results": spec.crypto.sign_results if spec.crypto else True,
                    "require_compliance": True,  # Enforce compliance by default
                },
            )

            # 5. Execute workflow
            # Note: In a production system, this might be handled by a separate process or task queue.
            # Here we bridge it directly.
            executor = executor_cls(
                crypto_service=self._crypto, artifact_store=self._artifact_store
            )

            # We start the workflow and wait for completion
            # In start_workflow, it creates an internal task
            await self._workflow_service.start_workflow(definition, context, executor)

            # Wait for completion
            result = await self._workflow_service.wait_for_completion(job_id)

            if result and result.success:
                # 6. Update JobStore with success
                # The executor result now contains artifact info if secured
                res_val = result.value
                artifact_id = None
                signature = None
                metadata = {"workflow_result": str(res_val)}

                if isinstance(res_val, dict):
                    artifact_id = res_val.get("artifact_id")
                    signature = res_val.get("signature")
                    if "value" in res_val:
                        metadata["workflow_result"] = str(res_val["value"])
                    if "signature_bundle" in res_val:
                        metadata["signature_bundle"] = res_val["signature_bundle"]

                job_result = JobResult(
                    job_id=job_id,
                    status=JobStatus.COMPLETED,
                    result_artifact_id=artifact_id,
                    signature=signature,
                    execution_time_seconds=result.execution_time_seconds,
                    metadata=metadata,
                )
                await self._job_store.update_result(job_id, job_result)
                await self._job_store.update_status(job_id, JobStatus.COMPLETED)
                logger.info(f"Job {job_id} completed successfully with artifact {artifact_id}")
            else:
                # 7. Update JobStore with failure
                error_msg = result.error if result else "Unknown error"
                await self._job_store.update_status(job_id, JobStatus.FAILED)
                logger.error(f"Job {job_id} failed: {error_msg}")

        except Exception as e:
            logger.exception(f"Error processing job {job_id}: {e}")
            await self._job_store.update_status(job_id, JobStatus.FAILED)

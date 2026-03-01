"""
Artifact Cleanup Service for QSOP.

Provides automated removal of job artifacts based on retention policies.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from qsop.domain.models.job import JobStatus
from qsop.domain.ports.artifact_store import ArtifactStore
from qsop.domain.ports.job_store import JobStore

logger = logging.getLogger(__name__)


class ArtifactCleanupService:
    """
    Service for automated cleanup of job artifacts.

    Periodically identifies terminal jobs that have exceeded their retention
    period and removes all associated artifacts from storage.
    """

    def __init__(
        self,
        job_store: JobStore,
        artifact_store: ArtifactStore,
        retention_days: int = 30,
        cleanup_interval_seconds: int = 3600,
    ):
        self._job_store = job_store
        self._artifact_store = artifact_store
        self._retention_days = retention_days
        self._cleanup_interval = cleanup_interval_seconds
        self._is_running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self):
        """Start the cleanup background task."""
        if self._is_running:
            return

        self._is_running = True
        self._task = asyncio.create_task(self._run_cleanup_loop())
        logger.info(f"ArtifactCleanupService started (retention: {self._retention_days} days)")

    async def stop(self):
        """Stop the cleanup background task."""
        if not self._is_running:
            return

        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("ArtifactCleanupService stopped")

    async def _run_cleanup_loop(self):
        """Main cleanup loop."""
        while self._is_running:
            try:
                await self.cleanup_expired_artifacts()
            except Exception as e:
                logger.exception(f"Error during artifact cleanup: {e}")

            # Wait for next interval
            try:
                await asyncio.sleep(self._cleanup_interval)
            except asyncio.CancelledError:
                break

    async def cleanup_expired_artifacts(self) -> int:
        """
        Identify and delete artifacts for jobs that have passed retention period.

        Returns:
            Total number of artifacts deleted.
        """
        expiry_date = datetime.now(UTC) - timedelta(days=self._retention_days)
        logger.info(f"Running artifact cleanup for jobs older than {expiry_date}")

        deleted_total = 0

        # Process terminal jobs in batches
        terminal_statuses = [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]

        for status in terminal_statuses:
            # Note: In a real implementation, we would use a more efficient query
            # if the JobStore supports it (e.g. filter by completed_at)
            jobs = await self._job_store.list_jobs(
                status=status, created_before=expiry_date, limit=100
            )

            for job in jobs:
                try:
                    # Check if artifacts exist before trying to delete
                    count = self._artifact_store.delete_job_artifacts(job.id)
                    if count > 0:
                        logger.info(f"Cleaned up {count} artifacts for expired job {job.id}")
                        deleted_total += count
                except Exception as e:
                    logger.error(f"Failed to cleanup artifacts for job {job.id}: {e}")

        if deleted_total > 0:
            logger.info(f"Artifact cleanup completed. Total artifacts deleted: {deleted_total}")

        return deleted_total

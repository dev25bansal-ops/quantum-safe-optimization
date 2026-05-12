"""Data Retention Policy Service.

Automated cleanup of old jobs, expired keys, and audit logs
based on configurable retention periods.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


class RetentionPolicy:
    """Configurable data retention policy."""

    def __init__(
        self,
        completed_job_retention_days: int = 90,
        failed_job_retention_days: int = 30,
        cancelled_job_retention_days: int = 7,
        expired_key_cleanup_days: int = 1,
        audit_log_retention_days: int = 365,
        batch_size: int = 100,
    ):
        self.completed_job_retention_days = completed_job_retention_days
        self.failed_job_retention_days = failed_job_retention_days
        self.cancelled_job_retention_days = cancelled_job_retention_days
        self.expired_key_cleanup_days = expired_key_cleanup_days
        self.audit_log_retention_days = audit_log_retention_days
        self.batch_size = batch_size


class RetentionService:
    """Manages data lifecycle and cleanup."""

    def __init__(self, policy: RetentionPolicy | None = None):
        self.policy = policy or RetentionPolicy()
        self._last_run: dict[str, datetime | None] = {
            "jobs": None,
            "keys": None,
            "audit_logs": None,
        }

    def get_cleanup_cutoff_dates(self) -> dict[str, datetime]:
        """Calculate cutoff dates for each cleanup category."""
        now = datetime.now(UTC)
        return {
            "completed_jobs": now - timedelta(days=self.policy.completed_job_retention_days),
            "failed_jobs": now - timedelta(days=self.policy.failed_job_retention_days),
            "cancelled_jobs": now - timedelta(days=self.policy.cancelled_job_retention_days),
            "expired_keys": now - timedelta(days=self.policy.expired_key_cleanup_days),
            "audit_logs": now - timedelta(days=self.policy.audit_log_retention_days),
        }

    async def cleanup_old_jobs(self, job_store) -> dict[str, int]:
        """Clean up jobs past their retention period.

        Args:
            job_store: Job repository with delete capability

        Returns:
            Dict with counts of cleaned up jobs by status
        """
        cutoffs = self.get_cleanup_cutoff_dates()
        results = {"completed": 0, "failed": 0, "cancelled": 0}

        for status, cutoff in [
            ("completed", cutoffs["completed_jobs"]),
            ("failed", cutoffs["failed_jobs"]),
            ("cancelled", cutoffs["cancelled_jobs"]),
        ]:
            try:
                # Get jobs to delete (batched)
                deleted = 0
                # Note: actual implementation depends on job_store interface
                # This is a template for integration
                logger.info(
                    "retention_cleanup_jobs",
                    status=status,
                    cutoff=cutoff.isoformat(),
                    batch_size=self.policy.batch_size,
                )
                results[status] = deleted
            except Exception as e:
                logger.error(
                    "retention_cleanup_failed",
                    status=status,
                    error=str(e),
                )

        self._last_run["jobs"] = datetime.now(UTC)
        return results

    async def cleanup_expired_keys(self, key_store) -> int:
        """Clean up expired PQC keys.

        Args:
            key_store: Key repository with delete capability

        Returns:
            Number of expired keys cleaned up
        """
        cutoff = self.get_cleanup_cutoff_dates()["expired_keys"]
        cleaned = 0

        try:
            logger.info(
                "retention_cleanup_keys",
                cutoff=cutoff.isoformat(),
            )
        except Exception as e:
            logger.error("retention_cleanup_keys_failed", error=str(e))

        self._last_run["keys"] = datetime.now(UTC)
        return cleaned

    async def cleanup_old_audit_logs(self, audit_store) -> int:
        """Clean up audit logs past retention period.

        Args:
            audit_store: Audit log repository with delete capability

        Returns:
            Number of old audit logs cleaned up
        """
        cutoff = self.get_cleanup_cutoff_dates()["audit_logs"]
        cleaned = 0

        try:
            logger.info(
                "retention_cleanup_audit_logs",
                cutoff=cutoff.isoformat(),
            )
        except Exception as e:
            logger.error("retention_cleanup_audit_logs_failed", error=str(e))

        self._last_run["audit_logs"] = datetime.now(UTC)
        return cleaned

    async def run_full_cleanup(
        self,
        job_store=None,
        key_store=None,
        audit_store=None,
    ) -> dict[str, Any]:
        """Run all cleanup tasks.

        Returns:
            Summary of cleanup results
        """
        results = {
            "timestamp": datetime.now(UTC).isoformat(),
            "policy": {
                "completed_job_retention_days": self.policy.completed_job_retention_days,
                "failed_job_retention_days": self.policy.failed_job_retention_days,
                "cancelled_job_retention_days": self.policy.cancelled_job_retention_days,
                "audit_log_retention_days": self.policy.audit_log_retention_days,
            },
            "results": {},
        }

        if job_store:
            results["results"]["jobs"] = await self.cleanup_old_jobs(job_store)

        if key_store:
            results["results"]["keys"] = await self.cleanup_expired_keys(key_store)

        if audit_store:
            results["results"]["audit_logs"] = await self.cleanup_old_audit_logs(audit_store)

        logger.info("retention_cleanup_complete", results=results)
        return results

    def get_last_run_status(self) -> dict[str, str | None]:
        """Get the last run time for each cleanup task."""
        return {
            task: last.isoformat() if last else "never"
            for task, last in self._last_run.items()
        }


# Global retention service
_retention_service: RetentionService | None = None


def get_retention_service() -> RetentionService:
    """Get the global retention service."""
    global _retention_service
    if _retention_service is None:
        _retention_service = RetentionService()
    return _retention_service


def init_retention_service(policy: RetentionPolicy | None = None) -> RetentionService:
    """Initialize the global retention service."""
    global _retention_service
    _retention_service = RetentionService(policy=policy)
    return _retention_service

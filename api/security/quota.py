"""Resource Quota Management for Multi-Tenant QSOP Platform.

Provides per-user and per-tenant resource limits for:
- Maximum concurrent jobs
- Monthly qubit-second budget
- Storage limits (job history)
- API rate limits (complementary to global rate limiter)
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class QuotaLimits:
    """Resource limits for a user or tenant."""

    max_concurrent_jobs: int = 10
    max_jobs_per_day: int = 100
    max_qubit_seconds_per_month: float = 3600.0  # 1 hour
    max_storage_jobs: int = 1000  # Maximum jobs stored
    max_priority_level: int = 8  # Max priority (1-10, admin can use 9-10)


@dataclass
class QuotaUsage:
    """Current resource usage."""

    concurrent_jobs: int = 0
    jobs_today: int = 0
    qubit_seconds_this_month: float = 0.0
    total_stored_jobs: int = 0


@dataclass
class QuotaState:
    """Combined quota limits and usage."""

    limits: QuotaLimits
    usage: QuotaUsage

    def can_submit_job(self) -> tuple[bool, str]:
        """Check if user can submit a new job."""
        if self.usage.concurrent_jobs >= self.limits.max_concurrent_jobs:
            return False, f"Concurrent job limit reached ({self.limits.max_concurrent_jobs})"
        if self.usage.jobs_today >= self.limits.max_jobs_per_day:
            return False, f"Daily job limit reached ({self.limits.max_jobs_per_day})"
        if self.usage.total_stored_jobs >= self.limits.max_storage_jobs:
            return False, f"Storage limit reached ({self.limits.max_storage_jobs} jobs)"
        return True, "OK"

    def can_use_priority(self, priority: int) -> tuple[bool, str]:
        """Check if user can use the requested priority level."""
        if priority > self.limits.max_priority_level:
            return False, f"Priority level {priority} exceeds limit ({self.limits.max_priority_level})"
        return True, "OK"


# Default quotas by role
DEFAULT_QUOTAS = {
    "user": QuotaLimits(
        max_concurrent_jobs=5,
        max_jobs_per_day=50,
        max_qubit_seconds_per_month=1800.0,
        max_storage_jobs=500,
        max_priority_level=7,
    ),
    "premium": QuotaLimits(
        max_concurrent_jobs=20,
        max_jobs_per_day=500,
        max_qubit_seconds_per_month=36000.0,
        max_storage_jobs=5000,
        max_priority_level=9,
    ),
    "admin": QuotaLimits(
        max_concurrent_jobs=100,
        max_jobs_per_day=10000,
        max_qubit_seconds_per_month=float("inf"),
        max_storage_jobs=100000,
        max_priority_level=10,
    ),
}


class QuotaService:
    """Manages resource quotas for users and tenants."""

    def __init__(self, store=None):
        """Initialize quota service.

        Args:
            store: Optional persistent store for quota data.
                   Uses in-memory dict if not provided.
        """
        self._store = store
        self._quotas: dict[str, QuotaLimits] = {}  # user_id -> limits
        self._usage: dict[str, QuotaUsage] = {}  # user_id -> usage

    def get_limits(self, user_id: str, roles: list[str] | None = None) -> QuotaLimits:
        """Get quota limits for a user based on their role."""
        # Check for custom quotas first
        if user_id in self._quotas:
            return self._quotas[user_id]

        # Use role-based defaults
        if roles:
            for role in ["admin", "premium", "user"]:
                if role in roles:
                    return DEFAULT_QUOTAS[role]

        return DEFAULT_QUOTAS["user"]

    async def get_usage(self, user_id: str) -> QuotaUsage:
        """Get current resource usage for a user."""
        if user_id in self._usage:
            return self._usage[user_id]

        usage = QuotaUsage()
        self._usage[user_id] = usage
        return usage

    async def check_quota(
        self, user_id: str, roles: list[str] | None = None, priority: int = 5
    ) -> tuple[bool, str]:
        """Check if user has quota to submit a job.

        Returns:
            (allowed, reason) tuple
        """
        limits = self.get_limits(user_id, roles)
        usage = await self.get_usage(user_id)
        state = QuotaState(limits=limits, usage=usage)

        allowed, reason = state.can_submit_job()
        if not allowed:
            return False, reason

        allowed, reason = state.can_use_priority(priority)
        if not allowed:
            return False, reason

        return True, "OK"

    async def record_job_submission(self, user_id: str):
        """Record a job submission for quota tracking."""
        usage = await self.get_usage(user_id)
        usage.concurrent_jobs += 1
        usage.jobs_today += 1
        usage.total_stored_jobs += 1

    async def record_job_completion(self, user_id: str, qubit_seconds: float = 0.0):
        """Record job completion and update usage."""
        usage = await self.get_usage(user_id)
        usage.concurrent_jobs = max(0, usage.concurrent_jobs - 1)
        usage.qubit_seconds_this_month += qubit_seconds

    async def record_job_cancellation(self, user_id: str):
        """Record job cancellation - free up concurrent slot."""
        usage = await self.get_usage(user_id)
        usage.concurrent_jobs = max(0, usage.concurrent_jobs - 1)

    def reset_daily_usage(self, user_id: str):
        """Reset daily usage counters (called by scheduler at midnight)."""
        if user_id in self._usage:
            self._usage[user_id].jobs_today = 0

    def reset_monthly_usage(self, user_id: str):
        """Reset monthly usage counters."""
        if user_id in self._usage:
            self._usage[user_id].qubit_seconds_this_month = 0.0

    def get_quota_status(self, user_id: str, roles: list[str] | None = None) -> dict[str, Any]:
        """Get detailed quota status for a user."""
        limits = self.get_limits(user_id, roles)
        usage = self._usage.get(user_id, QuotaUsage())

        return {
            "user_id": user_id,
            "limits": {
                "max_concurrent_jobs": limits.max_concurrent_jobs,
                "max_jobs_per_day": limits.max_jobs_per_day,
                "max_qubit_seconds_per_month": limits.max_qubit_seconds_per_month,
                "max_storage_jobs": limits.max_storage_jobs,
                "max_priority_level": limits.max_priority_level,
            },
            "usage": {
                "concurrent_jobs": usage.concurrent_jobs,
                "jobs_today": usage.jobs_today,
                "qubit_seconds_this_month": usage.qubit_seconds_this_month,
                "total_stored_jobs": usage.total_stored_jobs,
            },
            "remaining": {
                "concurrent_jobs": max(0, limits.max_concurrent_jobs - usage.concurrent_jobs),
                "jobs_today": max(0, limits.max_jobs_per_day - usage.jobs_today),
                "qubit_seconds": max(0.0, limits.max_qubit_seconds_per_month - usage.qubit_seconds_this_month),
                "storage_jobs": max(0, limits.max_storage_jobs - usage.total_stored_jobs),
            },
        }

    def set_custom_quota(self, user_id: str, limits: QuotaLimits):
        """Set custom quota limits for a specific user (admin operation)."""
        self._quotas[user_id] = limits


# Global quota service instance
_quota_service: QuotaService | None = None


def get_quota_service() -> QuotaService:
    """Get the global quota service instance."""
    global _quota_service
    if _quota_service is None:
        _quota_service = QuotaService()
    return _quota_service


def init_quota_service(store=None) -> QuotaService:
    """Initialize the global quota service."""
    global _quota_service
    _quota_service = QuotaService(store=store)
    return _quota_service

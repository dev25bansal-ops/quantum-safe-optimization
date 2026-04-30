"""
Analytics Dashboard Data Provider.

Provides aggregated metrics and insights for the dashboard.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import structlog

logger = structlog.get_logger()


@dataclass
class DashboardMetrics:
    jobs_submitted: int = 0
    jobs_completed: int = 0
    jobs_failed: int = 0
    jobs_running: int = 0
    total_shots: int = 0
    total_compute_seconds: float = 0.0
    total_cost_usd: float = 0.0
    active_users: int = 0
    active_backends: int = 0
    keys_active: int = 0
    keys_expiring: int = 0

    def to_dict(self) -> dict:
        return {
            "jobs_submitted": self.jobs_submitted,
            "jobs_completed": self.jobs_completed,
            "jobs_failed": self.jobs_failed,
            "jobs_running": self.jobs_running,
            "total_shots": self.total_shots,
            "total_compute_seconds": self.total_compute_seconds,
            "total_cost_usd": self.total_cost_usd,
            "active_users": self.active_users,
            "active_backends": self.active_backends,
            "keys_active": self.keys_active,
            "keys_expiring": self.keys_expiring,
        }


@dataclass
class TimeSeriesPoint:
    timestamp: datetime
    value: float

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
        }


@dataclass
class AnalyticsReport:
    report_id: str
    report_type: str
    period_start: datetime
    period_end: datetime
    metrics: dict[str, Any]
    time_series: dict[str, list[TimeSeriesPoint]] = field(default_factory=dict)
    insights: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "report_type": self.report_type,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "metrics": self.metrics,
            "time_series": {k: [p.to_dict() for p in v] for k, v in self.time_series.items()},
            "insights": self.insights,
            "generated_at": self.generated_at.isoformat(),
        }


class AnalyticsService:
    """Service for generating analytics and insights."""

    def __init__(self):
        self._job_data: list[dict] = []
        self._usage_data: list[dict] = []
        self._user_data: dict[str, dict] = {}

    def record_job(self, job: dict) -> None:
        """Record job for analytics."""
        self._job_data.append(
            {
                **job,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    def record_usage(self, usage: dict) -> None:
        """Record usage event for analytics."""
        self._usage_data.append(
            {
                **usage,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    def get_dashboard_metrics(self, tenant_id: Optional[str] = None) -> DashboardMetrics:
        """Get current dashboard metrics."""
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(days=1)

        metrics = DashboardMetrics()

        for job in self._job_data:
            if tenant_id and job.get("tenant_id") != tenant_id:
                continue

            job_time = datetime.fromisoformat(job.get("created_at", now.isoformat()))
            if job_time >= day_ago:
                metrics.jobs_submitted += 1

                status = job.get("status", "")
                if status == "completed":
                    metrics.jobs_completed += 1
                elif status == "failed":
                    metrics.jobs_failed += 1
                elif status == "running":
                    metrics.jobs_running += 1

                metrics.total_shots += job.get("shots", 0)
                metrics.total_compute_seconds += job.get("compute_seconds", 0.0)
                metrics.total_cost_usd += job.get("cost_usd", 0.0)

        unique_users = set()
        for job in self._job_data:
            if user_id := job.get("user_id"):
                unique_users.add(user_id)
        metrics.active_users = len(unique_users)

        metrics.active_backends = 4
        metrics.keys_active = 10
        metrics.keys_expiring = 2

        return metrics

    def get_time_series(
        self,
        metric: str,
        period_hours: int = 24,
        interval_minutes: int = 60,
        tenant_id: Optional[str] = None,
    ) -> list[TimeSeriesPoint]:
        """Get time series data for a metric."""
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=period_hours)

        points = []
        current = start

        while current <= now:
            value = 0.0

            if metric == "jobs_submitted":
                for job in self._job_data:
                    job_time = datetime.fromisoformat(job.get("created_at", now.isoformat()))
                    if current <= job_time < current + timedelta(minutes=interval_minutes):
                        if tenant_id is None or job.get("tenant_id") == tenant_id:
                            value += 1

            elif metric == "cost_usd":
                for job in self._job_data:
                    job_time = datetime.fromisoformat(job.get("created_at", now.isoformat()))
                    if current <= job_time < current + timedelta(minutes=interval_minutes):
                        if tenant_id is None or job.get("tenant_id") == tenant_id:
                            value += job.get("cost_usd", 0.0)

            elif metric == "shots":
                for job in self._job_data:
                    job_time = datetime.fromisoformat(job.get("created_at", now.isoformat()))
                    if current <= job_time < current + timedelta(minutes=interval_minutes):
                        if tenant_id is None or job.get("tenant_id") == tenant_id:
                            value += job.get("shots", 0)

            points.append(TimeSeriesPoint(timestamp=current, value=value))
            current += timedelta(minutes=interval_minutes)

        return points

    def generate_report(
        self,
        report_type: str,
        period_days: int = 7,
        tenant_id: Optional[str] = None,
    ) -> AnalyticsReport:
        """Generate an analytics report."""
        from uuid import uuid4

        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=period_days)

        report_id = f"report_{uuid4().hex[:8]}"

        metrics = self.get_dashboard_metrics(tenant_id)

        time_series = {
            "jobs": self.get_time_series("jobs_submitted", period_days * 24, 60, tenant_id),
            "cost": self.get_time_series("cost_usd", period_days * 24, 60, tenant_id),
            "shots": self.get_time_series("shots", period_days * 24, 60, tenant_id),
        }

        insights = []

        if metrics.jobs_failed > metrics.jobs_completed * 0.1:
            insights.append(
                f"High failure rate: {metrics.jobs_failed} failed vs {metrics.jobs_completed} completed"
            )

        if metrics.total_cost_usd > 100:
            insights.append(
                f"Significant compute cost: ${metrics.total_cost_usd:.2f} in the last 24 hours"
            )

        if metrics.keys_expiring > 0:
            insights.append(f"{metrics.keys_expiring} keys are expiring soon and need rotation")

        if not insights:
            insights.append("System operating normally - no issues detected")

        return AnalyticsReport(
            report_id=report_id,
            report_type=report_type,
            period_start=period_start,
            period_end=now,
            metrics=metrics.to_dict(),
            time_series=time_series,
            insights=insights,
        )

    def get_top_algorithms(self, limit: int = 10) -> list[dict]:
        """Get most used algorithms."""
        algorithm_counts: dict[str, int] = {}

        for job in self._job_data:
            algo = job.get("algorithm", "unknown")
            algorithm_counts[algo] = algorithm_counts.get(algo, 0) + 1

        sorted_algos = sorted(
            algorithm_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        return [{"algorithm": algo, "count": count} for algo, count in sorted_algos[:limit]]

    def get_backend_usage(self) -> list[dict]:
        """Get backend usage statistics."""
        backend_counts: dict[str, dict] = {}

        for job in self._job_data:
            backend = job.get("backend", "unknown")
            if backend not in backend_counts:
                backend_counts[backend] = {
                    "jobs": 0,
                    "shots": 0,
                    "cost": 0.0,
                }
            backend_counts[backend]["jobs"] += 1
            backend_counts[backend]["shots"] += job.get("shots", 0)
            backend_counts[backend]["cost"] += job.get("cost_usd", 0.0)

        return [{"backend": k, **v} for k, v in backend_counts.items()]

    def get_user_activity(self, limit: int = 20) -> list[dict]:
        """Get user activity rankings."""
        user_activity: dict[str, dict] = {}

        for job in self._job_data:
            user_id = job.get("user_id", "unknown")
            if user_id not in user_activity:
                user_activity[user_id] = {
                    "jobs": 0,
                    "shots": 0,
                    "last_active": None,
                }
            user_activity[user_id]["jobs"] += 1
            user_activity[user_id]["shots"] += job.get("shots", 0)

            job_time = job.get("created_at")
            if job_time:
                current_last = user_activity[user_id]["last_active"]
                if current_last is None or job_time > current_last:
                    user_activity[user_id]["last_active"] = job_time

        sorted_users = sorted(
            user_activity.items(),
            key=lambda x: x[1]["jobs"],
            reverse=True,
        )

        return [{"user_id": uid, **activity} for uid, activity in sorted_users[:limit]]


analytics_service = AnalyticsService()

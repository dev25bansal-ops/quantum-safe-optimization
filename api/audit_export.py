"""
Audit log export service.

Provides export and analysis capabilities for audit logs.
"""

import csv
import io
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from fastapi import Response
from fastapi.responses import StreamingResponse


class AuditLogExporter:
    """Export audit logs in various formats."""

    def __init__(self, logs: list[dict[str, Any]] | None = None):
        self.logs = logs or []

    def filter_by_date(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> "AuditLogExporter":
        """Filter logs by date range."""
        filtered = []

        for log in self.logs:
            log_time = log.get("created_at")
            if isinstance(log_time, str):
                log_time = datetime.fromisoformat(log_time.replace("Z", "+00:00"))

            if start and log_time and log_time < start:
                continue
            if end and log_time and log_time > end:
                continue

            filtered.append(log)

        return AuditLogExporter(filtered)

    def filter_by_user(self, user_id: str) -> "AuditLogExporter":
        """Filter logs by user."""
        filtered = [log for log in self.logs if log.get("user_id") == user_id]
        return AuditLogExporter(filtered)

    def filter_by_action(self, action: str) -> "AuditLogExporter":
        """Filter logs by action type."""
        filtered = [log for log in self.logs if log.get("action") == action]
        return AuditLogExporter(filtered)

    def to_json(self) -> str:
        """Export logs as JSON."""
        return json.dumps(self.logs, indent=2, default=str)

    def to_csv(self) -> str:
        """Export logs as CSV."""
        if not self.logs:
            return ""

        output = io.StringIO()
        fieldnames = [
            "id",
            "user_id",
            "action",
            "resource_type",
            "resource_id",
            "ip_address",
            "created_at",
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for log in self.logs:
            row = {k: str(v) if v is not None else "" for k, v in log.items() if k in fieldnames}
            writer.writerow(row)

        return output.getvalue()

    def to_summary(self) -> dict[str, Any]:
        """Generate a summary of audit logs."""
        actions: dict[str, int] = {}
        users: dict[str, int] = {}
        resources: dict[str, int] = {}

        for log in self.logs:
            action = log.get("action", "unknown")
            actions[action] = actions.get(action, 0) + 1

            user = log.get("user_id", "anonymous")
            users[user] = users.get(user, 0) + 1

            resource = log.get("resource_type", "unknown")
            resources[resource] = resources.get(resource, 0) + 1

        return {
            "total_events": len(self.logs),
            "unique_users": len(users),
            "unique_actions": len(actions),
            "by_action": actions,
            "by_user": dict(sorted(users.items(), key=lambda x: x[1], reverse=True)[:10]),
            "by_resource_type": resources,
            "time_range": {
                "start": min(log.get("created_at") for log in self.logs) if self.logs else None,
                "end": max(log.get("created_at") for log in self.logs) if self.logs else None,
            },
        }

    def streaming_csv(self) -> StreamingResponse:
        """Return a streaming CSV response."""

        def generate() -> Iterator[str]:
            if not self.logs:
                yield ""
                return

            fieldnames = [
                "id",
                "user_id",
                "action",
                "resource_type",
                "resource_id",
                "ip_address",
                "created_at",
            ]
            yield ",".join(fieldnames) + "\n"

            for log in self.logs:
                values = [str(log.get(k, "")) if log.get(k) is not None else "" for k in fieldnames]
                yield ",".join(values) + "\n"

        return StreamingResponse(
            generate(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            },
        )

    def streaming_json(self) -> StreamingResponse:
        """Return a streaming JSON response."""

        def generate() -> Iterator[str]:
            yield "["
            for i, log in enumerate(self.logs):
                if i > 0:
                    yield ","
                yield json.dumps(log, default=str)
            yield "]"

        return StreamingResponse(
            generate(),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            },
        )


def export_audit_logs(
    format: str = "json",
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    user_id: str | None = None,
    action: str | None = None,
    logs: list[dict[str, Any]] | None = None,
) -> str | StreamingResponse:
    """Export audit logs in the specified format."""
    exporter = AuditLogExporter(logs)

    if start_date or end_date:
        exporter = exporter.filter_by_date(start_date, end_date)

    if user_id:
        exporter = exporter.filter_by_user(user_id)

    if action:
        exporter = exporter.filter_by_action(action)

    if format == "csv":
        return exporter.streaming_csv()
    elif format == "summary":
        return exporter.to_summary()
    else:
        return exporter.streaming_json()

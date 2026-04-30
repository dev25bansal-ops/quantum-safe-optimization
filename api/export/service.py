"""
Data Export Service.

Provides export capabilities for jobs, results, and usage data.
"""

import csv
import io
import json
import time
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

import structlog

logger = structlog.get_logger()


class ExportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"


class ExportType(str, Enum):
    JOBS = "jobs"
    RESULTS = "results"
    USAGE = "usage"
    INVOICES = "invoices"
    AUDIT_LOGS = "audit_logs"
    ALGORITHMS = "algorithms"
    KEYS = "keys"


class DataExporter:
    """Service for exporting data in various formats."""

    def export(
        self,
        export_type: ExportType,
        data: list[dict[str, Any]],
        format: ExportFormat = ExportFormat.JSON,
        include_metadata: bool = True,
    ) -> tuple[bytes, str]:
        """Export data to specified format."""
        start_time = time.perf_counter()
        export_id = f"export_{uuid4().hex[:8]}"

        if format == ExportFormat.JSON:
            content, filename = self._export_json(export_type, data, export_id, include_metadata)
        elif format == ExportFormat.CSV:
            content, filename = self._export_csv(export_type, data, export_id)
        elif format == ExportFormat.PDF:
            content, filename = self._export_pdf(export_type, data, export_id)
        else:
            raise ValueError(f"Unsupported format: {format}")

        duration_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "data_exported",
            export_id=export_id,
            export_type=export_type.value,
            format=format.value,
            records=len(data),
            duration_ms=duration_ms,
        )

        return content, filename

    def _export_json(
        self,
        export_type: ExportType,
        data: list[dict[str, Any]],
        export_id: str,
        include_metadata: bool,
    ) -> tuple[bytes, str]:
        """Export to JSON format."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{export_type.value}_{timestamp}.json"

        if include_metadata:
            export_data = {
                "export_id": export_id,
                "export_type": export_type.value,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "record_count": len(data),
                "data": data,
            }
        else:
            export_data = data

        content = json.dumps(export_data, indent=2, default=str).encode("utf-8")
        return content, filename

    def _export_csv(
        self,
        export_type: ExportType,
        data: list[dict[str, Any]],
        export_id: str,
    ) -> tuple[bytes, str]:
        """Export to CSV format."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{export_type.value}_{timestamp}.csv"

        if not data:
            return b"", filename

        output = io.StringIO()
        writer = csv.writer(output)

        all_keys = set()
        for row in data:
            all_keys.update(row.keys())
        headers = sorted(all_keys)

        writer.writerow(headers)

        for row in data:
            csv_row = []
            for key in headers:
                value = row.get(key, "")
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                elif value is None:
                    value = ""
                else:
                    value = str(value)
                csv_row.append(value)
            writer.writerow(csv_row)

        content = output.getvalue().encode("utf-8")
        return content, filename

    def _export_pdf(
        self,
        export_type: ExportType,
        data: list[dict[str, Any]],
        export_id: str,
    ) -> tuple[bytes, str]:
        """Export to PDF format (simplified text-based PDF)."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{export_type.value}_{timestamp}.pdf"

        lines = [
            f"Export Report: {export_type.value}",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            f"Total Records: {len(data)}",
            "",
            "-" * 80,
            "",
        ]

        for i, record in enumerate(data, 1):
            lines.append(f"Record {i}:")
            for key, value in record.items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                lines.append(f"  {key}: {value}")
            lines.append("")

        content = "\n".join(lines).encode("utf-8")
        return content, filename

    def export_jobs(
        self,
        jobs: list[dict[str, Any]],
        format: ExportFormat = ExportFormat.JSON,
    ) -> tuple[bytes, str]:
        """Export job data."""
        return self.export(ExportType.JOBS, jobs, format)

    def export_results(
        self,
        results: list[dict[str, Any]],
        format: ExportFormat = ExportFormat.JSON,
    ) -> tuple[bytes, str]:
        """Export optimization results."""
        return self.export(ExportType.RESULTS, results, format)

    def export_usage(
        self,
        usage: list[dict[str, Any]],
        format: ExportFormat = ExportFormat.CSV,
    ) -> tuple[bytes, str]:
        """Export usage data."""
        return self.export(ExportType.USAGE, usage, format)

    def export_audit_logs(
        self,
        logs: list[dict[str, Any]],
        format: ExportFormat = ExportFormat.JSON,
    ) -> tuple[bytes, str]:
        """Export audit logs."""
        return self.export(ExportType.AUDIT_LOGS, logs, format)


data_exporter = DataExporter()

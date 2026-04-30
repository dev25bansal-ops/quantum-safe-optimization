"""
Real-time Performance Dashboard API Endpoints.

Provides endpoints for:
- System metrics (CPU, memory, disk, network)
- Request metrics (RPS, latency percentiles, error rate)
- WebSocket streaming for real-time updates
- Process information
- GC statistics
"""

import asyncio
import gc
import logging
import os
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


@dataclass
class SystemMetrics:
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    network_bytes_sent: int
    network_bytes_recv: int
    open_files: int
    threads: int
    gc_objects: int
    timestamp: str


@dataclass
class RequestMetrics:
    requests_per_second: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    error_rate: float
    active_connections: int


@dataclass
class PerformanceDashboard:
    system: SystemMetrics
    requests: RequestMetrics
    uptime_seconds: float
    timestamp: str


_request_times: deque = deque(maxlen=1000)
_error_count: int = 0
_total_requests: int = 0
_start_time: datetime = datetime.now(UTC)


def _get_system_metrics() -> SystemMetrics:
    if not PSUTIL_AVAILABLE:
        return SystemMetrics(
            cpu_percent=0.0,
            memory_percent=0.0,
            memory_used_mb=0.0,
            memory_total_mb=0.0,
            disk_percent=0.0,
            disk_used_gb=0.0,
            disk_total_gb=0.0,
            network_bytes_sent=0,
            network_bytes_recv=0,
            open_files=0,
            threads=0,
            gc_objects=len(gc.get_objects()),
            timestamp=datetime.now(UTC).isoformat(),
        )

    process = psutil.Process(os.getpid())
    net_io = psutil.net_io_counters()

    try:
        disk_io = psutil.disk_usage("/")
    except Exception:
        disk_io = None

    return SystemMetrics(
        cpu_percent=process.cpu_percent(interval=0.1),
        memory_percent=process.memory_percent(),
        memory_used_mb=process.memory_info().rss / 1024 / 1024,
        memory_total_mb=psutil.virtual_memory().total / 1024 / 1024,
        disk_percent=disk_io.percent if disk_io else 0.0,
        disk_used_gb=disk_io.used / 1024 / 1024 / 1024 if disk_io else 0.0,
        disk_total_gb=disk_io.total / 1024 / 1024 / 1024 if disk_io else 0.0,
        network_bytes_sent=net_io.bytes_sent,
        network_bytes_recv=net_io.bytes_recv,
        open_files=len(process.open_files()) if hasattr(process, "open_files") else 0,
        threads=process.num_threads(),
        gc_objects=len(gc.get_objects()),
        timestamp=datetime.now(UTC).isoformat(),
    )


def _get_request_metrics() -> RequestMetrics:
    global _request_times, _error_count, _total_requests

    if not _request_times:
        return RequestMetrics(
            requests_per_second=0.0,
            avg_latency_ms=0.0,
            p50_latency_ms=0.0,
            p95_latency_ms=0.0,
            p99_latency_ms=0.0,
            error_rate=0.0,
            active_connections=0,
        )

    times = sorted(_request_times)
    now = datetime.now(UTC)
    recent_requests = [
        t for t in times if (now - datetime.fromtimestamp(t[0], UTC)).total_seconds() < 60
    ]
    rps = len(recent_requests) / 60.0 if recent_requests else 0.0

    latencies = [t[1] for t in times]
    error_rate = _error_count / _total_requests if _total_requests > 0 else 0.0

    return RequestMetrics(
        requests_per_second=rps,
        avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
        p50_latency_ms=latencies[int(len(latencies) * 0.5)] if latencies else 0.0,
        p95_latency_ms=latencies[int(len(latencies) * 0.95)] if latencies else 0.0,
        p99_latency_ms=latencies[int(len(latencies) * 0.99)] if latencies else 0.0,
        error_rate=error_rate,
        active_connections=len(
            [t for t in times if (now - datetime.fromtimestamp(t[0], UTC)).total_seconds() < 5]
        ),
    )


@router.get("/")
async def get_performance_dashboard() -> dict[str, Any]:
    """Get real-time performance dashboard metrics."""
    uptime = (datetime.now(UTC) - _start_time).total_seconds()

    dashboard = PerformanceDashboard(
        system=_get_system_metrics(),
        requests=_get_request_metrics(),
        uptime_seconds=uptime,
        timestamp=datetime.now(UTC).isoformat(),
    )

    return asdict(dashboard)


@router.get("/stream")
async def stream_performance_metrics(interval: int = Query(default=5, ge=1, le=60)):
    """Stream performance metrics (Server-Sent Events simulation via JSON stream)."""
    from fastapi.responses import StreamingResponse
    import json

    async def generate():
        while True:
            metrics = {
                "system": asdict(_get_system_metrics()),
                "requests": asdict(_get_request_metrics()),
                "timestamp": datetime.now(UTC).isoformat(),
            }
            yield json.dumps(metrics) + "\n"
            await asyncio.sleep(interval)

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.websocket("/ws")
async def performance_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time performance metrics."""
    await websocket.accept()

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                interval = int(data) if data.isdigit() else 5
            except asyncio.TimeoutError:
                interval = 5

            metrics = {
                "system": asdict(_get_system_metrics()),
                "requests": asdict(_get_request_metrics()),
                "timestamp": datetime.now(UTC).isoformat(),
            }

            await websocket.send_json(metrics)
            await asyncio.sleep(interval)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("performance_websocket_error", error=str(e))


@router.get("/process")
async def get_process_info() -> dict[str, Any]:
    """Get detailed process information."""
    if not PSUTIL_AVAILABLE:
        return {"error": "psutil not available"}

    process = psutil.Process(os.getpid())

    return {
        "pid": process.pid,
        "ppid": process.ppid(),
        "name": process.name(),
        "exe": process.exe(),
        "cwd": process.cwd(),
        "cmdline": process.cmdline(),
        "status": process.status(),
        "create_time": datetime.fromtimestamp(process.create_time(), UTC).isoformat(),
        "cpu_times": {
            "user": process.cpu_times().user,
            "system": process.cpu_times().system,
        },
        "memory_info": {
            "rss": process.memory_info().rss,
            "vms": process.memory_info().vms,
        },
        "num_threads": process.num_threads(),
        "num_handles": process.num_handles() if hasattr(process, "num_handles") else 0,
        "num_ctx_switches": {
            "voluntary": process.num_ctx_switches().voluntary,
            "involuntary": process.num_ctx_switches().involuntary,
        },
    }


@router.get("/gc")
async def get_gc_stats() -> dict[str, Any]:
    """Get garbage collection statistics."""
    gc_stats = gc.get_stats()

    return {
        "enabled": gc.isenabled(),
        "threshold": gc.get_threshold(),
        "count": gc.get_count(),
        "stats": [
            {
                "collections": stat.collections,
                "collected": stat.collected,
                "uncollectable": stat.uncollectable,
            }
            for stat in gc_stats
        ],
        "objects": len(gc.get_objects()),
    }


@router.post("/gc/collect")
async def trigger_gc_collect(generation: int = Query(default=2, ge=0, le=2)) -> dict[str, Any]:
    """Trigger garbage collection for a specific generation."""
    collected = gc.collect(generation)

    return {
        "generation": generation,
        "collected": collected,
        "count": gc.get_count(),
        "timestamp": datetime.now(UTC).isoformat(),
    }


def record_request(latency_ms: float, is_error: bool = False) -> None:
    """Record a request for metrics tracking."""
    global _request_times, _error_count, _total_requests

    _request_times.append((time.time(), latency_ms))
    _total_requests += 1
    if is_error:
        _error_count += 1

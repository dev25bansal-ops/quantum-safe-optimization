"""
API Usage Analytics Endpoints.

Provides endpoints for:
- Endpoint usage statistics
- Request rate analytics
- Error tracking
- User activity metrics
- Performance trends
"""

import logging
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query, Request

logger = logging.getLogger(__name__)

router = APIRouter()


@dataclass
class EndpointStats:
    path: str
    method: str
    total_requests: int
    success_count: int
    error_count: int
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    last_accessed: str


@dataclass
class UsageAnalytics:
    total_requests: int
    unique_endpoints: int
    unique_users: int
    requests_per_hour: dict[str, int]
    top_endpoints: list[dict[str, Any]]
    error_rates: dict[str, float]
    latency_percentiles: dict[str, float]
    timestamp: str


_endpoint_stats: dict[str, dict[str, Any]] = defaultdict(
    lambda: {
        "total_requests": 0,
        "success_count": 0,
        "error_count": 0,
        "latencies": [],
        "last_accessed": None,
    }
)
_user_activity: dict[str, dict[str, Any]] = defaultdict(lambda: {"requests": 0, "last_seen": None})
_hourly_requests: dict[str, int] = defaultdict(int)
_start_time: datetime = datetime.now(UTC)


def _get_endpoint_key(method: str, path: str) -> str:
    normalized_path = path
    for segment in path.split("/"):
        if segment and segment.isdigit() or (segment and len(segment) == 36 and "-" in segment):
            normalized_path = normalized_path.replace(segment, "{id}")
    return f"{method}:{normalized_path}"


def record_api_call(
    method: str,
    path: str,
    latency_ms: float,
    status_code: int,
    user_id: str | None = None,
) -> None:
    key = _get_endpoint_key(method, path)
    stats = _endpoint_stats[key]

    stats["total_requests"] += 1
    stats["latencies"].append(latency_ms)
    stats["last_accessed"] = datetime.now(UTC).isoformat()

    if 200 <= status_code < 400:
        stats["success_count"] += 1
    else:
        stats["error_count"] += 1

    hour_key = datetime.now(UTC).strftime("%Y-%m-%d %H:00")
    _hourly_requests[hour_key] += 1

    if user_id:
        _user_activity[user_id]["requests"] += 1
        _user_activity[user_id]["last_seen"] = datetime.now(UTC).isoformat()

    if len(stats["latencies"]) > 10000:
        stats["latencies"] = stats["latencies"][-5000:]


@router.get("/")
async def get_usage_analytics(
    hours: int = Query(default=24, ge=1, le=168),
) -> dict[str, Any]:
    """Get comprehensive API usage analytics."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    recent_endpoints = {
        k: v
        for k, v in _endpoint_stats.items()
        if v["last_accessed"] and datetime.fromisoformat(v["last_accessed"]) > cutoff
    }

    top_endpoints = sorted(
        [
            {
                "endpoint": k,
                "total_requests": v["total_requests"],
                "error_rate": v["error_count"] / v["total_requests"]
                if v["total_requests"] > 0
                else 0,
                "avg_latency_ms": sum(v["latencies"]) / len(v["latencies"])
                if v["latencies"]
                else 0,
            }
            for k, v in recent_endpoints.items()
        ],
        key=lambda x: x["total_requests"],
        reverse=True,
    )[:10]

    all_latencies = []
    for v in recent_endpoints.values():
        all_latencies.extend(v["latencies"])

    all_latencies.sort()
    latency_percentiles = {}
    if all_latencies:
        latency_percentiles = {
            "p50": all_latencies[int(len(all_latencies) * 0.5)],
            "p90": all_latencies[int(len(all_latencies) * 0.9)],
            "p95": all_latencies[int(len(all_latencies) * 0.95)],
            "p99": all_latencies[int(len(all_latencies) * 0.99)],
        }

    error_rates = {}
    for k, v in recent_endpoints.items():
        if v["total_requests"] > 0:
            rate = v["error_count"] / v["total_requests"]
            if rate > 0.01:
                error_rates[k] = round(rate * 100, 2)

    recent_hours = {
        k: v
        for k, v in _hourly_requests.items()
        if datetime.strptime(k, "%Y-%m-%d %H:00").replace(tzinfo=UTC) > cutoff
    }

    return {
        "total_requests": sum(v["total_requests"] for v in recent_endpoints.values()),
        "unique_endpoints": len(recent_endpoints),
        "unique_users": len([u for u in _user_activity.values() if u["last_seen"]]),
        "requests_per_hour": dict(sorted(recent_hours.items())[-24:]),
        "top_endpoints": top_endpoints,
        "error_rates": error_rates,
        "latency_percentiles": latency_percentiles,
        "uptime_seconds": (datetime.now(UTC) - _start_time).total_seconds(),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/endpoints")
async def get_endpoint_statistics(
    hours: int = Query(default=24, ge=1, le=168),
    sort_by: str = Query(default="requests", pattern="^(requests|latency|errors)$"),
) -> list[dict[str, Any]]:
    """Get detailed statistics for all endpoints."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    endpoints = []
    for key, stats in _endpoint_stats.items():
        if stats["last_accessed"] and datetime.fromisoformat(stats["last_accessed"]) > cutoff:
            method, path = key.split(":", 1)
            latencies = stats["latencies"]

            endpoints.append(
                {
                    "path": path,
                    "method": method,
                    "total_requests": stats["total_requests"],
                    "success_count": stats["success_count"],
                    "error_count": stats["error_count"],
                    "error_rate": stats["error_count"] / stats["total_requests"]
                    if stats["total_requests"] > 0
                    else 0,
                    "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
                    "min_latency_ms": min(latencies) if latencies else 0,
                    "max_latency_ms": max(latencies) if latencies else 0,
                    "last_accessed": stats["last_accessed"],
                }
            )

    sort_keys = {
        "requests": lambda x: x["total_requests"],
        "latency": lambda x: x["avg_latency_ms"],
        "errors": lambda x: x["error_rate"],
    }

    return sorted(
        endpoints, key=sort_keys.get(sort_by, lambda x: x["total_requests"]), reverse=True
    )


@router.get("/errors")
async def get_error_analytics(
    hours: int = Query(default=24, ge=1, le=168),
) -> dict[str, Any]:
    """Get error analytics and patterns."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    error_endpoints = []
    total_errors = 0
    total_requests = 0

    for key, stats in _endpoint_stats.items():
        if stats["last_accessed"] and datetime.fromisoformat(stats["last_accessed"]) > cutoff:
            if stats["error_count"] > 0:
                method, path = key.split(":", 1)
                error_endpoints.append(
                    {
                        "path": path,
                        "method": method,
                        "error_count": stats["error_count"],
                        "total_requests": stats["total_requests"],
                        "error_rate": stats["error_count"] / stats["total_requests"],
                    }
                )
            total_errors += stats["error_count"]
            total_requests += stats["total_requests"]

    return {
        "total_errors": total_errors,
        "total_requests": total_requests,
        "overall_error_rate": total_errors / total_requests if total_requests > 0 else 0,
        "error_endpoints": sorted(error_endpoints, key=lambda x: x["error_count"], reverse=True)[
            :20
        ],
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/users")
async def get_user_activity(
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    """Get user activity statistics."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    active_users = [
        {"user_id": uid, "requests": data["requests"], "last_seen": data["last_seen"]}
        for uid, data in _user_activity.items()
        if data["last_seen"] and datetime.fromisoformat(data["last_seen"]) > cutoff
    ]

    return {
        "total_active_users": len(active_users),
        "top_users": sorted(active_users, key=lambda x: x["requests"], reverse=True)[:limit],
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/health")
async def get_analytics_health() -> dict[str, Any]:
    """Get health status of the analytics system."""
    return {
        "status": "healthy",
        "tracked_endpoints": len(_endpoint_stats),
        "tracked_users": len(_user_activity),
        "uptime_seconds": (datetime.now(UTC) - _start_time).total_seconds(),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.post("/reset")
async def reset_analytics() -> dict[str, str]:
    """Reset all analytics data."""
    global _endpoint_stats, _user_activity, _hourly_requests, _start_time

    _endpoint_stats.clear()
    _user_activity.clear()
    _hourly_requests.clear()
    _start_time = datetime.now(UTC)

    return {"status": "reset", "timestamp": datetime.now(UTC).isoformat()}


@router.get("/profiling")
async def get_profiling_stats() -> dict[str, Any]:
    """Get request profiling statistics."""
    from api.middleware.profiling import get_profiling_middleware

    middleware = get_profiling_middleware()
    if not middleware:
        return {
            "status": "disabled",
            "message": "Profiling middleware not configured",
            "timestamp": datetime.now(UTC).isoformat(),
        }

    stats = middleware.get_stats()
    return asdict(stats)


@router.get("/profiling/slow")
async def get_slow_requests(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    """Get slow request profiles."""
    from api.middleware.profiling import get_profiling_middleware

    middleware = get_profiling_middleware()
    if not middleware:
        return []

    return middleware.get_slow_requests(limit)


@router.get("/profiling/errors")
async def get_error_requests(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    """Get error request profiles."""
    from api.middleware.profiling import get_profiling_middleware

    middleware = get_profiling_middleware()
    if not middleware:
        return []

    return middleware.get_error_requests(limit)


@router.post("/profiling/reset")
async def reset_profiling() -> dict[str, str]:
    """Reset profiling data."""
    from api.middleware.profiling import get_profiling_middleware

    middleware = get_profiling_middleware()
    if middleware:
        middleware.reset()

    return {"status": "reset", "timestamp": datetime.now(UTC).isoformat()}

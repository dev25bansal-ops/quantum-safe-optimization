"""
Performance API Endpoints.

Provides endpoints for:
- Query optimization metrics
- WebSocket compression metrics
- Pagination helpers
- CDN status
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query

logger = logging.getLogger(__name__)

router = APIRouter()


def get_user_id() -> str:
    return "user_default"


# ============================================================================
# Query Optimization Endpoints
# ============================================================================


@router.get("/query-optimizer/metrics")
async def get_query_optimizer_metrics():
    """Get query optimization metrics."""
    from api.db.query_optimizer import get_query_optimizer

    optimizer = get_query_optimizer()
    return optimizer.get_metrics()


@router.post("/query-optimizer/clear-cache")
async def clear_query_cache(
    user_id: str = Depends(get_user_id),
):
    """Clear the query cache."""
    from api.db.query_optimizer import get_query_optimizer

    optimizer = get_query_optimizer()
    optimizer._cache.clear()

    return {"status": "cleared"}


@router.get("/query-optimizer/n-plus-one-warnings")
async def get_n_plus_one_warnings():
    """Get N+1 query warnings."""
    from api.db.query_optimizer import NPlusOneDetector

    return {
        "warnings": NPlusOneDetector.get_warnings(),
        "counts": dict(NPlusOneDetector._counts),
    }


# ============================================================================
# WebSocket Compression Endpoints
# ============================================================================


@router.get("/websocket/compression-metrics")
async def get_websocket_compression_metrics():
    """Get WebSocket compression metrics."""
    from api.websocket.compression import get_websocket_compressor

    compressor = get_websocket_compressor()
    return compressor.get_metrics()


@router.post("/websocket/compression/configure")
async def configure_websocket_compression(
    enabled: bool = True,
    threshold_bytes: int = Query(default=1024, ge=0, le=10240),
    level: int = Query(default=6, ge=1, le=9),
    user_id: str = Depends(get_user_id),
):
    """Configure WebSocket compression settings."""
    from api.websocket.compression import CompressionConfig, WebSocketCompressor

    config = CompressionConfig(
        enabled=enabled,
        threshold_bytes=threshold_bytes,
        level=level,
    )

    global _websocket_compressor
    from api.websocket import compression

    compression._websocket_compressor = WebSocketCompressor(config)

    return {
        "status": "configured",
        "enabled": enabled,
        "threshold_bytes": threshold_bytes,
        "level": level,
    }


# ============================================================================
# Pagination Endpoints
# ============================================================================


@router.get("/pagination/config")
async def get_pagination_config():
    """Get pagination configuration."""
    return {
        "default_page_size": 20,
        "max_page_size": 100,
        "max_offset": 10000,
        "cursor_pagination_enabled": True,
        "total_count_enabled": True,
    }


@router.get("/pagination/helpers")
async def get_pagination_helpers():
    """Get pagination helper functions documentation."""
    return {
        "offset_pagination": {
            "params": ["page", "page_size"],
            "defaults": {"page": 1, "page_size": 20},
            "example": "?page=2&page_size=50",
        },
        "cursor_pagination": {
            "params": ["cursor", "limit"],
            "defaults": {"limit": 20},
            "example": "?cursor=abc123&limit=50",
        },
        "response_headers": {
            "X-Total-Count": "Total number of items",
            "X-Page": "Current page number",
            "X-Page-Size": "Items per page",
            "X-Total-Pages": "Total number of pages",
            "Link": "Navigation links (next, prev, first, last)",
        },
    }


# ============================================================================
# Performance Status
# ============================================================================


@router.get("/status")
async def get_performance_status():
    """Get overall performance status."""
    from api.db.query_optimizer import get_query_optimizer
    from api.websocket.compression import get_websocket_compressor

    optimizer = get_query_optimizer()
    compressor = get_websocket_compressor()

    return {
        "query_optimizer": {
            "metrics": optimizer.get_metrics(),
        },
        "websocket_compression": {
            "metrics": compressor.get_metrics(),
        },
        "pagination": {
            "default_page_size": 20,
            "max_page_size": 100,
        },
        "cdn": {
            "enabled": True,
            "url": "https://quantum-cdn.azureedge.net",
        },
    }


# ============================================================================
# Connection Pool Status
# ============================================================================


@router.get("/connection-pool/status")
async def get_connection_pool_status():
    """Get database connection pool status."""
    try:
        from api.db.cosmos import cosmos_manager

        return {
            "cosmos_db": cosmos_manager.get_pool_stats(),
            "circuit_breaker": cosmos_manager.get_circuit_breaker_status(),
        }
    except Exception as e:
        return {
            "error": str(e),
            "status": "unavailable",
        }


@router.post("/connection-pool/reset-circuit-breaker")
async def reset_circuit_breaker(
    user_id: str = Depends(get_user_id),
):
    """Reset the Cosmos DB circuit breaker."""
    try:
        from api.db.cosmos import cosmos_manager

        await cosmos_manager.reset_circuit_breaker()
        return {"status": "reset"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

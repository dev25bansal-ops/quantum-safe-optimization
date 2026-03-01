"""Metrics middleware for recording API performance."""

from __future__ import annotations

import time
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from qsop.infrastructure.observability.metrics import get_metrics


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware that records API request metrics."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        start_time = time.time()

        # Process the request
        response = await call_next(request)

        # Record metrics
        duration = time.time() - start_time

        # Get labels
        method = request.method
        endpoint = request.url.path
        status_code = str(response.status_code)
        tenant_id = getattr(request.state, "tenant_id", "anonymous")

        metrics = get_metrics()

        # Record count
        metrics.api_requests.labels(
            method=method, endpoint=endpoint, status_code=status_code, tenant_id=tenant_id
        ).inc()

        # Record latency
        metrics.api_latency.labels(method=method, endpoint=endpoint, tenant_id=tenant_id).observe(
            duration
        )

        return response

"""Request ID middleware for request tracing."""

from __future__ import annotations

import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns a unique request ID to each request."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER)
        
        if not request_id:
            request_id = str(uuid.uuid4())
        
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        
        return response


def get_request_id(request: Request) -> str:
    """Get the request ID from the current request."""
    return getattr(request.state, "request_id", str(uuid.uuid4()))

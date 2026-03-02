"""
Production Security Middleware for FastAPI.

Features:
- Security headers (OWASP recommended)
- Request validation
- Audit logging
- Request ID tracking
- CORS hardening
- Content type validation
"""

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses.

    Implements OWASP security header recommendations.
    """

    # Default security headers
    DEFAULT_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma": "no-cache",
    }

    # CSP for API responses (relaxed for JSON APIs)
    API_CSP = "default-src 'none'; frame-ancestors 'none'"

    def __init__(
        self,
        app: ASGIApp,
        enable_hsts: bool = True,
        hsts_max_age: int = 31536000,
        custom_headers: dict[str, str] | None = None,
    ):
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.hsts_max_age = hsts_max_age
        self.custom_headers = custom_headers or {}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # Add default security headers
        for header, value in self.DEFAULT_HEADERS.items():
            response.headers[header] = value

        # Add CSP for API responses
        if request.url.path.startswith("/api/"):
            response.headers["Content-Security-Policy"] = self.API_CSP

        # Add HSTS if enabled and using HTTPS
        if self.enable_hsts and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; includeSubDomains; preload"
            )

        # Add custom headers
        for header, value in self.custom_headers.items():
            response.headers[header] = value

        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Add unique request ID to each request for tracing.
    """

    REQUEST_ID_HEADER = "X-Request-ID"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Get existing request ID or generate new one
        request_id = request.headers.get(self.REQUEST_ID_HEADER)
        if not request_id:
            request_id = str(uuid.uuid4())

        # Store in request state
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add request ID to response
        response.headers[self.REQUEST_ID_HEADER] = request_id

        return response


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log all requests for security audit trail.
    """

    # Paths to exclude from detailed logging
    EXCLUDE_PATHS = {"/health", "/metrics", "/favicon.ico"}

    # Sensitive headers to mask
    SENSITIVE_HEADERS = {"authorization", "x-api-key", "cookie"}

    def __init__(
        self,
        app: ASGIApp,
        logger: Any | None = None,
        log_request_body: bool = False,
        log_response_body: bool = False,
    ):
        super().__init__(app)
        self.logger = logger
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body

    def _mask_headers(self, headers: dict[str, str]) -> dict[str, str]:
        """Mask sensitive header values."""
        masked = {}
        for key, value in headers.items():
            if key.lower() in self.SENSITIVE_HEADERS:
                masked[key] = "***MASKED***"
            else:
                masked[key] = value
        return masked

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip excluded paths
        if request.url.path in self.EXCLUDE_PATHS:
            return await call_next(request)

        start_time = time.time()
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

        # Build audit log entry
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query": str(request.query_params),
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("user-agent", ""),
            "headers": self._mask_headers(dict(request.headers)),
        }

        # Get user from request state if available
        if hasattr(request.state, "user"):
            audit_entry["user_id"] = getattr(request.state.user, "id", None)
            audit_entry["username"] = getattr(request.state.user, "username", None)

        try:
            response = await call_next(request)

            # Add response info
            duration_ms = (time.time() - start_time) * 1000
            audit_entry["status_code"] = response.status_code
            audit_entry["duration_ms"] = round(duration_ms, 2)
            audit_entry["success"] = 200 <= response.status_code < 400

            # Log the audit entry
            if self.logger:
                log_method = self.logger.info if audit_entry["success"] else self.logger.warning
                log_method("api_request", **audit_entry)
            else:
                pass

            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            audit_entry["status_code"] = 500
            audit_entry["duration_ms"] = round(duration_ms, 2)
            audit_entry["success"] = False
            audit_entry["error"] = str(e)

            if self.logger:
                self.logger.error("api_request_error", **audit_entry)
            else:
                pass

            raise

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP, handling proxies."""
        # Check X-Forwarded-For header first
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to client host
        return request.client.host if request.client else "unknown"


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Validate incoming requests for security.
    """

    # Maximum content lengths by content type
    MAX_CONTENT_LENGTHS = {
        "application/json": 10 * 1024 * 1024,  # 10MB
        "multipart/form-data": 50 * 1024 * 1024,  # 50MB for file uploads
        "default": 1 * 1024 * 1024,  # 1MB default
    }

    # Allowed content types for POST/PUT/PATCH
    ALLOWED_CONTENT_TYPES = {
        "application/json",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    }

    # Blocked user agents (bots, scanners, etc.)
    BLOCKED_USER_AGENTS = {
        "sqlmap",
        "nikto",
        "nessus",
        "dirbuster",
        "gobuster",
    }

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Check user agent
        user_agent = request.headers.get("user-agent", "").lower()
        for blocked in self.BLOCKED_USER_AGENTS:
            if blocked in user_agent:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied",
                )

        # Validate content type for body requests
        if request.method in ("POST", "PUT", "PATCH"):
            content_type = request.headers.get("content-type", "")

            # Skip content type check for file uploads (multipart)
            if content_type and not any(
                allowed in content_type for allowed in self.ALLOWED_CONTENT_TYPES
            ):
                raise HTTPException(
                    status_code=415,
                    detail=f"Unsupported content type: {content_type}",
                )

            # Check content length
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    length = int(content_length)
                    max_length = self._get_max_length(content_type)
                    if length > max_length:
                        raise HTTPException(
                            status_code=413,
                            detail=f"Request too large. Max: {max_length} bytes",
                        )
                except ValueError:
                    pass

        return await call_next(request)

    def _get_max_length(self, content_type: str) -> int:
        """Get maximum content length for content type."""
        for ct, max_len in self.MAX_CONTENT_LENGTHS.items():
            if ct in content_type:
                return max_len
        return self.MAX_CONTENT_LENGTHS["default"]


class CORSConfig:
    """CORS configuration for production."""

    def __init__(
        self,
        allowed_origins: list[str] | None = None,
        allow_credentials: bool = True,
        allow_methods: list[str] | None = None,
        allow_headers: list[str] | None = None,
        max_age: int = 3600,
    ):
        self.allowed_origins = allowed_origins or self._get_default_origins()
        self.allow_credentials = allow_credentials
        self.allow_methods = allow_methods or ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
        self.allow_headers = allow_headers or [
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-API-Key",
        ]
        self.max_age = max_age

    def _get_default_origins(self) -> list[str]:
        """Get allowed origins from environment."""
        origins_str = os.getenv("CORS_ORIGINS", "http://localhost:3000")
        return [origin.strip() for origin in origins_str.split(",")]

    def apply(self, app: ASGIApp) -> None:
        """Apply CORS middleware to app."""
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self.allowed_origins,
            allow_credentials=self.allow_credentials,
            allow_methods=self.allow_methods,
            allow_headers=self.allow_headers,
            max_age=self.max_age,
        )


def configure_production_middleware(app: ASGIApp, logger: Any | None = None) -> None:
    """
    Configure all production security middleware.

    Order matters - middleware is applied in reverse order.
    """
    # Get environment
    env = os.getenv("APP_ENV", "development")
    is_production = env == "production"

    # 1. Request validation (innermost - runs first)
    app.add_middleware(RequestValidationMiddleware)

    # 2. Audit logging
    app.add_middleware(
        AuditLoggingMiddleware,
        logger=logger,
        log_request_body=not is_production,
        log_response_body=False,
    )

    # 3. Request ID tracking
    app.add_middleware(RequestIDMiddleware)

    # 4. Security headers (outermost - runs last)
    app.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=is_production,
    )

    # 5. CORS
    cors_config = CORSConfig()
    cors_config.apply(app)

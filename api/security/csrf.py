"""
CSRF (Cross-Site Request Forgery) Protection Middleware.

Provides CSRF token validation for state-changing operations.
"""

import hashlib
import hmac
import logging
import os
import secrets
from typing import Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send, Message

logger = logging.getLogger(__name__)

CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_COOKIE_NAME = "csrf_token"
CSRF_SECRET = os.getenv("CSRF_SECRET", secrets.token_hex(32))


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection middleware.

    Validates CSRF tokens on state-changing requests (POST, PUT, DELETE, PATCH).
    Generates and sets CSRF tokens for safe requests (GET, HEAD, OPTIONS).

    How it works:
    1. On GET requests, generates a CSRF token and sets it as a cookie
    2. Client must include this token in the X-CSRF-Token header for unsafe requests
    3. Middleware validates the token before allowing the request through

    Configuration:
    - CSRF_SECRET: Secret key for signing tokens (set via environment)
    - CSRF_HEADER_NAME: Header name for CSRF token (default: X-CSRF-Token)
    - CSRF_COOKIE_NAME: Cookie name for CSRF token (default: csrf_token)
    """

    UNSAFE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

    # Paths to exclude from CSRF protection
    EXCLUDE_PATHS = {
        "/health",
        "/health/",
        "/health/live",
        "/health/ready",
        "/health/detailed",
        "/metrics",
        "/api/v1/websocket",
        "/api/v1/ws",
        "/ws",
    }

    # Path prefixes to exclude
    EXCLUDE_PREFIXES = (
        "/api/v1/websocket",
        "/api/v1/ws",
        "/ws/",
        "/docs",
        "/redoc",
        "/openapi",
        "/static",
        "/css",
        "/js",
    )

    def __init__(
        self,
        app: ASGIApp,
        secret: str | None = None,
        header_name: str = CSRF_HEADER_NAME,
        cookie_name: str = CSRF_COOKIE_NAME,
        cookie_secure: bool = True,
        cookie_httponly: bool = False,  # Must be False so JS can read it
        cookie_samesite: str = "strict",
        enabled: bool = True,
    ):
        super().__init__(app)
        self.secret = secret or CSRF_SECRET
        self.header_name = header_name
        self.cookie_name = cookie_name
        self.cookie_secure = cookie_secure
        self.cookie_httponly = cookie_httponly
        self.cookie_samesite = cookie_samesite
        self.enabled = enabled

    def _generate_token(self) -> str:
        """Generate a new CSRF token."""
        random_bytes = secrets.token_bytes(32)
        signature = hmac.new(self.secret.encode(), random_bytes, hashlib.sha256).hexdigest()
        return f"{random_bytes.hex()}:{signature}"

    def _validate_token(self, token: str) -> bool:
        """Validate a CSRF token."""
        if not token or ":" not in token:
            return False

        try:
            random_hex, signature = token.split(":", 1)
            random_bytes = bytes.fromhex(random_hex)
            expected_signature = hmac.new(
                self.secret.encode(), random_bytes, hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(signature, expected_signature)
        except (ValueError, TypeError):
            return False

    def _is_excluded_path(self, path: str) -> bool:
        """Check if path is excluded from CSRF protection."""
        if path in self.EXCLUDE_PATHS:
            return True
        return any(path.startswith(prefix) for prefix in self.EXCLUDE_PREFIXES)

    def _get_cookie_token(self, request: Request) -> str | None:
        """Get CSRF token from cookie."""
        return request.cookies.get(self.cookie_name)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled:
            return await call_next(request)

        path = request.url.path

        # Skip excluded paths
        if self._is_excluded_path(path):
            return await call_next(request)

        # For unsafe methods, validate CSRF token
        if request.method in self.UNSAFE_METHODS:
            # Skip for API requests with Authorization header (token-based auth)
            # These are typically not vulnerable to CSRF
            auth_header = request.headers.get("Authorization", "")
            api_key_header = request.headers.get("X-API-Key", "")

            # If using token auth, CSRF protection is less critical
            # but we still validate if a CSRF token is provided
            cookie_token = self._get_cookie_token(request)
            header_token = request.headers.get(self.header_name)

            # If both cookie and header are present, validate them
            if cookie_token and header_token:
                if not self._validate_token(header_token) or header_token != cookie_token:
                    logger.warning(
                        "csrf_validation_failed",
                        path=path,
                        method=request.method,
                        client_ip=request.client.host if request.client else "unknown",
                    )
                    raise HTTPException(status_code=403, detail="CSRF token validation failed")
            # If using session auth (cookie but no Authorization), require CSRF
            elif not auth_header and not api_key_header:
                if not header_token:
                    raise HTTPException(
                        status_code=403, detail="CSRF token required for this request"
                    )
                if not self._validate_token(header_token):
                    raise HTTPException(status_code=403, detail="Invalid CSRF token")

        # Process the request
        response = await call_next(request)

        # For safe methods, set CSRF cookie if not already set
        if request.method not in self.UNSAFE_METHODS:
            existing_token = self._get_cookie_token(request)
            if not existing_token:
                token = self._generate_token()
                response.set_cookie(
                    key=self.cookie_name,
                    value=token,
                    secure=self.cookie_secure,
                    httponly=self.cookie_httponly,
                    samesite=self.cookie_samesite,
                    max_age=3600 * 24,  # 24 hours
                )

        return response


def get_csrf_token(request: Request) -> str:
    """Get CSRF token from request for use in templates."""
    token = request.cookies.get(CSRF_COOKIE_NAME)
    if not token:
        token = secrets.token_hex(32)
    return token

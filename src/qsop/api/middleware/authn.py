"""Authentication middleware for JWT and API key authentication."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

BEARER_PREFIX = "Bearer "
API_KEY_HEADER = "X-API-Key"
SKIP_AUTH_PATHS = {"/health", "/health/ready", "/health/live", "/docs", "/openapi.json"}


@dataclass
class AuthContext:
    """Authentication context for the current request."""

    tenant_id: str
    user_id: str | None
    scopes: list[str]
    auth_method: str  # "jwt" or "api_key"
    expires_at: int | None = None


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware that handles JWT and API key authentication."""

    def __init__(
        self,
        app,
        jwt_secret: str,
        jwt_algorithm: str = "HS256",
        api_key_validator: Callable[[str], AuthContext | None] | None = None,
    ) -> None:
        super().__init__(app)
        self.jwt_secret = jwt_secret
        self.jwt_algorithm = jwt_algorithm
        self.api_key_validator = api_key_validator or self._default_api_key_validator

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        if request.url.path in SKIP_AUTH_PATHS:
            request.state.auth_context = None
            request.state.tenant_id = "anonymous"
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        api_key = request.headers.get(API_KEY_HEADER)

        auth_context: AuthContext | None = None

        if auth_header.startswith(BEARER_PREFIX):
            token = auth_header[len(BEARER_PREFIX):]
            auth_context = self._validate_jwt(token)
        elif api_key:
            auth_context = await self._validate_api_key(api_key)

        if auth_context is None:
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "message": "Invalid or missing authentication"},
            )

        request.state.auth_context = auth_context
        request.state.tenant_id = auth_context.tenant_id
        request.state.user_id = auth_context.user_id

        return await call_next(request)

    def _validate_jwt(self, token: str) -> AuthContext | None:
        """Validate a JWT token and extract auth context."""
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm],
                options={"require": ["exp", "sub", "tenant_id"]},
            )

            if payload.get("exp", 0) < time.time():
                return None

            return AuthContext(
                tenant_id=payload["tenant_id"],
                user_id=payload.get("sub"),
                scopes=payload.get("scopes", []),
                auth_method="jwt",
                expires_at=payload.get("exp"),
            )
        except jwt.PyJWTError:
            return None

    async def _validate_api_key(self, api_key: str) -> AuthContext | None:
        """Validate an API key and extract auth context."""
        return self.api_key_validator(api_key)

    def _default_api_key_validator(self, api_key: str) -> AuthContext | None:
        """Default API key validator (for development only)."""
        if api_key.startswith("dev_"):
            parts = api_key.split("_")
            if len(parts) >= 2:
                return AuthContext(
                    tenant_id=parts[1] if len(parts) > 1 else "default",
                    user_id=None,
                    scopes=["read", "write"],
                    auth_method="api_key",
                )
        return None


def require_scope(scope: str):
    """Dependency that requires a specific scope."""
    def checker(request: Request) -> bool:
        auth_context: AuthContext | None = getattr(request.state, "auth_context", None)
        if auth_context is None:
            return False
        return scope in auth_context.scopes or "admin" in auth_context.scopes
    return checker


def get_auth_context(request: Request) -> AuthContext | None:
    """Get the authentication context from the request."""
    return getattr(request.state, "auth_context", None)

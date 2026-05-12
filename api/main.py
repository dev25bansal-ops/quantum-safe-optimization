"""
Quantum-Safe Secure Optimization Platform - FastAPI Backend

Thin wrapper around app_factory for development use.
For production, use api.app_factory directly with gunicorn.

Usage:
    uvicorn api.main:app --reload        # Development
    gunicorn api.app_factory:app ...     # Production
"""

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Delegate app creation to the factory
from api.app_factory import AppFactory
from api.logging_config import setup_logging

# Initialize structured logging
logger = setup_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_format=os.getenv("LOG_FORMAT", "json"),
    service_name="quantum-api",
)

# API Version
API_VERSION = "v1"


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    message: str
    request_id: str | None = None


# Create app via factory (API mode = full-featured)
_factory = AppFactory(
    mode="api",
    enable_frontend=True,
    enable_websockets=True,
    enable_rate_limiting=True,
    enable_security_middleware=True,
)
app: FastAPI = _factory.create_app()


# ============================================================================
# Exception handlers (main.py specific - not in factory)
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    request_id = request.headers.get("X-Request-ID") or getattr(request.state, "request_id", None)

    logger.exception(
        "unhandled_exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
        method=request.method,
        request_id=request_id,
    )

    is_dev = os.getenv("APP_ENV", "production") == "development"
    error_message = str(exc) if is_dev else "An internal error occurred"

    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="internal_server_error",
            message=error_message,
            request_id=request_id,
        ).model_dump(),
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 Not Found with structured response."""
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="not_found",
                message=f"Endpoint {request.method} {request.url.path} not found",
                request_id=request.headers.get("X-Request-ID"),
            ).model_dump(),
        )
    return JSONResponse(status_code=404, content={"error": "Not Found"})


def _sanitize_validation_errors(exc) -> list[dict]:
    """Remove request body echoes from validation errors to avoid leaking secrets."""
    if not hasattr(exc, "errors"):
        return [{"msg": "Validation failed"}]

    sanitized = []
    for error in exc.errors():
        item = {key: value for key, value in error.items() if key not in {"input", "ctx"}}
        sanitized.append(item)
    return sanitized


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with clearer messages."""
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Request validation failed. Check your request body and parameters.",
            "details": _sanitize_validation_errors(exc),
            "request_id": request.headers.get("X-Request-ID"),
        },
    )


@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc):
    """Handle status-code validation errors without echoing request payloads."""
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Request validation failed. Check your request body and parameters.",
            "details": _sanitize_validation_errors(exc),
            "request_id": request.headers.get("X-Request-ID"),
        },
    )


# ============================================================================
# Frontend static file serving (main.py specific)
# ============================================================================

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
    app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")

    @app.get("/manifest.json")
    async def serve_manifest():
        """Serve the PWA manifest with proper caching."""
        response = FileResponse(
            FRONTEND_DIR / "manifest.json",
            media_type="application/manifest+json",
        )
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response

    @app.get("/sw.js")
    async def serve_service_worker():
        """Serve the Service Worker with no-cache for instant updates."""
        response = FileResponse(
            FRONTEND_DIR / "sw.js",
            media_type="application/javascript",
        )
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Service-Worker-Allowed"] = "/"
        return response

    @app.get("/", response_class=FileResponse)
    async def serve_frontend():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/index.html", response_class=FileResponse)
    async def serve_index_html():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/dashboard", response_class=FileResponse)
    async def serve_dashboard():
        return FileResponse(FRONTEND_DIR / "dashboard.html")

    @app.get("/dashboard.html", response_class=FileResponse)
    async def serve_dashboard_html():
        return FileResponse(FRONTEND_DIR / "dashboard.html")
else:

    @app.get("/")
    async def root():
        """Root endpoint (API info when no frontend)."""
        return {
            "name": "Quantum-Safe Secure Optimization Platform",
            "version": "0.1.0",
            "api_version": API_VERSION,
            "status": "operational",
            "endpoints": {
                "api": f"/api/{API_VERSION}",
                "docs": "/docs",
                "health": "/health",
            },
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true",
    )

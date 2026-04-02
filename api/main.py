"""
Quantum-Safe Secure Optimization Platform - FastAPI Backend

Main application entry point with PQC-secured endpoints.
Features:
- Post-Quantum Cryptography (ML-KEM-768, ML-DSA-65)
- Celery task queue for distributed job processing
- WebSocket for real-time job progress streaming
- Connection pooling for Cosmos DB
- API versioning (/api/v1/)
- Structured logging with structlog
- Distributed tracing with OpenTelemetry
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.db.cosmos import close_cosmos, init_cosmos
from api.logging_config import setup_logging
from api.routers import auth, auth_demo, health, jobs
from api.routers.api_keys import router as api_keys_router
from api.routers.backends import router as backends_router
from api.routers.batch import router as batch_router
from api.routers.caching import router as caching_router
from api.routers.costs import router as costs_router
from api.routers.metrics import MetricsMiddleware
from api.routers.metrics import router as metrics_router
from api.routers.oauth import router as oauth_router
from api.routers.scheduling import router as scheduling_router, start_scheduler, stop_scheduler
from api.routers.websocket import close_websocket_manager, init_websocket_manager
from api.routers.websocket import router as websocket_router
from api.billing.router import router as billing_router
from api.tenant.router import router as tenant_router
from api.circuits.router import router as circuits_router
from api.marketplace.router import router as marketplace_router
from api.federation.router import router as federation_router
from api.security.enhanced.router import router as security_router
from api.security.middleware import (
    AuditLoggingMiddleware,
    RequestIDMiddleware,
    RequestValidationMiddleware,
    SecurityHeadersMiddleware,
)
from api.security.rate_limiter import limiter
from api.security.secrets_manager import close_secrets_manager, init_secrets_manager
from api.security.token_revocation import close_token_revocation, init_token_revocation
from api.telemetry import (
    TelemetryConfig,
    instrument_dependencies,
    instrument_fastapi,
    setup_telemetry,
)

# Initialize structured logging
logger = setup_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_format=os.getenv("LOG_FORMAT", "json"),
    service_name="quantum-api",
)

# Initialize OpenTelemetry tracing (disabled by default for local dev)
if os.getenv("OTEL_ENABLED", "false").lower() == "true":
    telemetry_config = TelemetryConfig(
        service_name=os.getenv("OTEL_SERVICE_NAME", "quantum-api"),
        service_version="0.1.0",
        environment=os.getenv("APP_ENV", "development"),
        otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
        sample_rate=float(os.getenv("OTEL_TRACES_SAMPLER_ARG", "1.0")),
        console_export=os.getenv("OTEL_CONSOLE_EXPORT", "false").lower() == "true",
    )
    setup_telemetry(telemetry_config)
    instrument_dependencies()
    logger.info("telemetry_initialized", endpoint=telemetry_config.otlp_endpoint)

# API Version
API_VERSION = "v1"


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    message: str
    request_id: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("application_starting", platform="Quantum-Safe Optimization Platform")
    logger.info("crypto_initializing", subsystem="PQC")

    # SECURITY: Check that real crypto is available in production
    app_env = os.getenv("APP_ENV", "development")
    if app_env == "production":
        try:
            from quantum_safe_crypto import is_crypto_production_ready, get_crypto_status

            if not is_crypto_production_ready():
                status = get_crypto_status()
                logger.critical(
                    "SECURITY CRITICAL: Production environment detected but using STUB crypto. "
                    f"Status: {status}. Refusing to start."
                )
                raise RuntimeError(
                    "SECURITY: Cannot start in production with stub cryptography. "
                    "Install liboqs and liboqs-python for real post-quantum cryptography."
                )
        except ImportError:
            logger.critical("SECURITY CRITICAL: quantum_safe_crypto module not found")
            raise RuntimeError("Cannot start without cryptography module")

    # Initialize Secrets Manager first (needed by other services)
    try:
        await init_secrets_manager()
        logger.info("secrets_manager_initialized")
    except Exception as e:
        logger.warning("secrets_manager_init_failed", error=str(e), fallback="environment")

    # Initialize Cosmos DB connection with pooling
    try:
        await init_cosmos()
        logger.info("cosmos_connected", feature="connection_pooling")
    except Exception as e:
        logger.warning("cosmos_init_failed", error=str(e), fallback="in-memory")

    # Initialize token revocation service
    try:
        await init_token_revocation()
        logger.info("token_revocation_initialized")
    except Exception as e:
        logger.warning("token_revocation_init_failed", error=str(e))

    # Initialize WebSocket manager for real-time updates
    try:
        await init_websocket_manager()
        logger.info("websocket_manager_initialized")
    except Exception as e:
        logger.warning("websocket_manager_init_failed", error=str(e))

    # Initialize job scheduler
    try:
        await start_scheduler()
        logger.info("job_scheduler_initialized")
    except Exception as e:
        logger.warning("job_scheduler_init_failed", error=str(e))

    # Initialize server signing key for PQC tokens
    from quantum_safe_crypto import SigningKeyPair

    app.state.signing_keypair = SigningKeyPair()
    logger.info("pqc_keys_initialized", algorithm="ML-DSA-65")

    # Check Celery status if enabled
    if os.getenv("USE_CELERY", "false").lower() == "true":
        try:
            from api.tasks.celery_app import get_celery_status

            status = get_celery_status()
            if status.get("status") == "connected":
                logger.info("celery_connected", workers=status.get("workers", []))
            else:
                logger.warning("celery_not_connected", fallback="sync_execution")
        except Exception as e:
            logger.warning("celery_status_check_failed", error=str(e))

    logger.info("application_started")
    yield

    # Shutdown
    logger.info("application_stopping")
    try:
        await stop_scheduler()
        logger.info("scheduler_stopped")
    except Exception as e:
        logger.warning("scheduler_stop_error", error=str(e))
    try:
        await close_websocket_manager()
        logger.info("websocket_manager_closed")
    except Exception as e:
        logger.warning("websocket_manager_close_error", error=str(e))
    try:
        await close_token_revocation()
        logger.info("token_revocation_closed")
    except Exception as e:
        logger.warning("token_revocation_close_error", error=str(e))
    try:
        await close_cosmos()
        logger.info("cosmos_connection_closed")
    except Exception as e:
        logger.warning("cosmos_close_error", error=str(e))

    try:
        await close_secrets_manager()
        logger.info("secrets_manager_closed")
    except Exception as e:
        logger.warning("secrets_manager_close_error", error=str(e))

    logger.info("application_stopped")


app = FastAPI(
    title="Quantum-Safe Secure Optimization Platform",
    description="""
    A production-ready platform integrating Post-Quantum Cryptography (PQC)
    with Quantum Optimization Algorithms.

    ## Features

    * **QAOA** - Quantum Approximate Optimization Algorithm for combinatorial problems
    * **VQE** - Variational Quantum Eigensolver for quantum chemistry
    * **Quantum Annealing** - D-Wave integration for QUBO problems
    * **PQC Security** - ML-KEM-768 encryption and ML-DSA-65 signatures

    ## Security

    All endpoints are secured with:
    - ML-DSA-65 signed JWT tokens
    - ML-KEM-768 encrypted payloads (optional)
    - Hybrid TLS (X25519 + ML-KEM)
    """,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Instrument FastAPI with OpenTelemetry
if os.getenv("OTEL_ENABLED", "false").lower() == "true":
    instrument_fastapi(app)

# Add production security middleware (order matters - outermost first)
is_production = os.getenv("APP_ENV") == "production"

# Security headers (always enabled)
app.add_middleware(SecurityHeadersMiddleware, enable_hsts=is_production)

# GZip compression for responses > 500 bytes
app.add_middleware(GZipMiddleware, minimum_size=500)

# Request ID tracking for distributed tracing
app.add_middleware(RequestIDMiddleware)

# Audit logging for security compliance
if os.getenv("ENABLE_AUDIT_LOGGING", "true").lower() == "true":
    app.add_middleware(AuditLoggingMiddleware, logger=logger)

# Request validation (content type, size limits, etc.)
app.add_middleware(RequestValidationMiddleware)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configuration - stricter in production
cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000,http://localhost:8001,http://127.0.0.1:8001,http://localhost:3000,http://localhost:8080",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-API-Key"],
    max_age=3600,
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    request_id = request.headers.get("X-Request-ID") or getattr(request.state, "request_id", None)

    # Log the exception with full context
    logger.exception(
        "unhandled_exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
        method=request.method,
        request_id=request_id,
    )

    # Add error to current trace span
    try:
        from api.telemetry import record_exception

        record_exception(exc)
    except Exception:
        logger.warning(f"Telemetry recording failed: {exc}")

    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="internal_server_error",
            message=str(exc) if os.getenv("DEBUG") else "An internal error occurred",
            request_id=request_id,
        ).model_dump(),
    )


# Structured 404 handler
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


# Structured 422 handler for validation errors
@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc):
    """Handle validation errors with clearer messages."""
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Request validation failed. Check your request body and parameters.",
            "details": exc.errors() if hasattr(exc, "errors") else str(exc),
            "request_id": request.headers.get("X-Request-ID"),
        },
    )


# Create versioned API router
api_v1_router = APIRouter(prefix=f"/api/{API_VERSION}")

# Include routers under versioned prefix
api_v1_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_v1_router.include_router(auth_demo.router, prefix="/auth", tags=["Authentication-Demo"])
api_v1_router.include_router(jobs.router, prefix="/jobs", tags=["Optimization Jobs"])
api_v1_router.include_router(websocket_router, prefix="/ws", tags=["WebSocket"])
api_v1_router.include_router(costs_router, tags=["Cost Estimation"])
api_v1_router.include_router(backends_router, tags=["Quantum Backends"])
api_v1_router.include_router(api_keys_router, tags=["API Keys"])
api_v1_router.include_router(oauth_router, tags=["OAuth / SSO"])
api_v1_router.include_router(scheduling_router, tags=["Job Scheduling"])
api_v1_router.include_router(caching_router, tags=["Caching"])
api_v1_router.include_router(batch_router, tags=["Batch Jobs"])
api_v1_router.include_router(billing_router, prefix="/billing", tags=["Billing & Usage"])
api_v1_router.include_router(tenant_router, tags=["Multi-Tenant"])
api_v1_router.include_router(circuits_router, prefix="/circuits", tags=["Circuit Visualization"])
api_v1_router.include_router(
    marketplace_router, prefix="/marketplace", tags=["Algorithm Marketplace"]
)
api_v1_router.include_router(
    federation_router, prefix="/federation", tags=["Federation & Multi-Region"]
)
api_v1_router.include_router(security_router, prefix="/security", tags=["Security & Audit"])

# Mount versioned API
app.include_router(api_v1_router)

# Metrics endpoint at root level (for Prometheus scraping)
app.include_router(metrics_router, tags=["Metrics"])

# Add metrics middleware for automatic request tracking
app.add_middleware(MetricsMiddleware)

# Health endpoints at root level (for load balancers/orchestrators)
app.include_router(health.router, tags=["Health"])

# Legacy routes (deprecated, will be removed in future versions)
# These mirror the v1 routes for backward compatibility
app.include_router(auth.router, prefix="/auth", tags=["Authentication (Legacy)"], deprecated=True)
app.include_router(
    jobs.router, prefix="/jobs", tags=["Optimization Jobs (Legacy)"], deprecated=True
)
app.include_router(websocket_router, prefix="/ws", tags=["WebSocket (Legacy)"], deprecated=True)
app.include_router(costs_router, tags=["Cost Estimation (Legacy)"], deprecated=True)


# Serve frontend static files
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    # Mount static assets (CSS, JS)
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
        """Serve the frontend landing page."""
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/index.html", response_class=FileResponse)
    async def serve_index_html():
        """Serve the frontend landing page (explicit .html)."""
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/dashboard", response_class=FileResponse)
    async def serve_dashboard():
        """Serve the dashboard page."""
        return FileResponse(FRONTEND_DIR / "dashboard.html")

    @app.get("/dashboard.html", response_class=FileResponse)
    async def serve_dashboard_html():
        """Serve the dashboard page (explicit .html)."""
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
            "deprecation_notice": "Root-level /auth and /jobs endpoints are deprecated. Use /api/v1/ prefix.",
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),  # noqa: S104 - Accepting connections from all interfaces
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true",
    )

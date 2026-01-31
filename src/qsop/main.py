"""FastAPI application entrypoint."""

import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from qsop import __version__
from qsop.settings import get_settings
from qsop.infrastructure.observability.metrics import get_metrics
from qsop.api.routers import create_api_router
from qsop.api.middleware.authn import AuthenticationMiddleware
from qsop.api.middleware.request_id import RequestIDMiddleware

settings = get_settings()

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        (
            structlog.processors.JSONRenderer()
            if settings.log_format.value == "json"
            else structlog.dev.ConsoleRenderer()
        ),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(structlog, settings.log_level.upper(), structlog.INFO)
    ),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    logger.info(
        "starting_application",
        version=__version__,
        env=settings.env.value,
        debug=settings.debug,
    )
    yield
    logger.info("shutting_down_application")


app = FastAPI(
    title=settings.api.title,
    version=settings.api.version,
    description="Quantum-Safe Secure Optimization Platform API",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.origins,
    allow_credentials=settings.cors.allow_credentials,
    allow_methods=settings.cors.allow_methods,
    allow_headers=settings.cors.allow_headers,
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    AuthenticationMiddleware,
    jwt_secret=settings.secret_key.get_secret_value(),
)

# Metrics Middleware (must be after Auth to have tenant_id)
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Collect request metrics."""
    import time

    start_time = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start_time

    endpoint = request.url.path
    tenant_id = getattr(request.state, "tenant_id", "anonymous")
    
    metrics = get_metrics()
    metrics.api_requests.labels(
        method=request.method,
        endpoint=endpoint,
        status_code=str(response.status_code),
        tenant_id=tenant_id
    ).inc()
    metrics.api_latency.labels(
        method=request.method,
        endpoint=endpoint,
        tenant_id=tenant_id
    ).observe(duration)

    return response


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Structured request logging."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=getattr(request.state, "request_id", ""),
        method=request.method,
        path=request.url.path,
        tenant_id=getattr(request.state, "tenant_id", "anonymous"),
    )

    response = await call_next(request)

    logger.info(
        "request_completed",
        status_code=response.status_code,
    )
    return response


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    logger.exception("unhandled_exception", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# Routers
app.include_router(create_api_router(), prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": __version__,
        "env": settings.env.value,
    }


@app.get("/ready", tags=["Health"])
async def readiness_check() -> dict:
    """Readiness probe endpoint."""
    return {"status": "ready"}


@app.get("/metrics", tags=["Observability"], include_in_schema=False)
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/api/v1/info", tags=["Info"])
async def api_info() -> dict:
    """API information endpoint."""
    return {
        "name": settings.api.title,
        "version": settings.api.version,
        "pqc_kem_algorithm": settings.crypto.kem_algorithm.value,
        "pqc_sig_algorithm": settings.crypto.sig_algorithm.value,
        "quantum_backend": settings.quantum.backend.value,
    }


def run() -> None:
    """Run the application."""
    uvicorn.run(
        "qsop.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.reload,
        workers=1 if settings.api.reload else settings.api.workers,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()

"""
Unified Application Factory for Quantum-Safe Secure Optimization Platform.

This module consolidates the dual entrypoints (api/main.py and src/qsop/main.py)
into a single, configurable application factory.

Features:
- Supports both legacy (api/) and modern (src/qsop/) configurations
- Feature flags for gradual migration
- Unified middleware stack
- Centralized router registration
- Environment-aware configuration
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

logger = logging.getLogger(__name__)


class AppFactory:
    """
    Factory for creating configured FastAPI application instances.
    
    Supports two modes:
    - 'api': Full-featured mode with all routers (legacy api/main.py)
    - 'qsop': Minimal mode with core routers (src/qsop/main.py)
    """
    
    def __init__(
        self,
        mode: str = "api",  # 'api' or 'qsop'
        enable_telemetry: bool = None,
        enable_websockets: bool = True,
        enable_frontend: bool = True,
        enable_demo_mode: bool = None,
        enable_rate_limiting: bool = True,
        enable_security_middleware: bool = True,
    ):
        """
        Initialize application factory.
        
        Args:
            mode: Application mode ('api' for full, 'qsop' for minimal)
            enable_telemetry: Enable OpenTelemetry (default: based on env)
            enable_websockets: Enable WebSocket support
            enable_frontend: Serve static frontend files
            enable_demo_mode: Enable demo mode for development
            enable_rate_limiting: Enable rate limiting
            enable_security_middleware: Enable security middleware
        """
        self.mode = mode
        self.is_api_mode = mode == "api"
        self.is_qsop_mode = mode == "qsop"
        
        # Environment detection
        self.is_production = os.getenv("APP_ENV", "development") == "production"
        self.is_development = not self.is_production
        
        # Feature flags
        self.enable_telemetry = enable_telemetry if enable_telemetry is not None else (
            os.getenv("OTEL_ENABLED", "false" if self.is_development else "true").lower() == "true"
        )
        self.enable_websockets = enable_websockets
        self.enable_frontend = enable_frontend
        self.enable_demo_mode = enable_demo_mode if enable_demo_mode is not None else self.is_development
        self.enable_rate_limiting = enable_rate_limiting
        self.enable_security_middleware = enable_security_middleware
        
        # Track initialized components
        self._cosmos_initialized = False
        self._redis_initialized = False
        self._websocket_initialized = False
        self._scheduler_initialized = False
        self._key_rotation_initialized = False
    
    def create_app(self) -> FastAPI:
        """
        Create and configure FastAPI application.
        
        Returns:
            Configured FastAPI application instance
        """
        # Create lifespan manager
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """Application lifespan handler."""
            await self._on_startup(app)
            yield
            await self._on_shutdown(app)
        
        # Create app instance
        app = FastAPI(
            title="Quantum-Safe Secure Optimization Platform",
            description=self._get_description(),
            version=os.getenv("APP_VERSION", "0.1.0"),
            docs_url="/docs" if self.is_development else None,
            redoc_url="/redoc" if self.is_development else None,
            openapi_url="/openapi.json" if self.is_development else None,
            lifespan=lifespan,
        )
        
        # Configure middleware
        self._setup_middleware(app)
        
        # Register routers
        self._register_routers(app)
        
        # Add health and metrics endpoints
        self._add_core_endpoints(app)
        
        # Mount frontend if enabled
        if self.enable_frontend:
            self._mount_frontend(app)
        
        return app
    
    async def _on_startup(self, app: FastAPI):
        """Startup tasks."""
        logger.info("application_starting", mode=self.mode, env="production" if self.is_production else "development")
        
        # Initialize services based on mode
        if self.is_api_mode:
            # Full initialization for API mode
            await self._init_cosmos_db(app)
            await self._init_secrets_manager(app)
            await self._init_token_revocation(app)
            await self._init_websocket_manager(app)
            await self._init_scheduler(app)
            await self._init_key_rotation(app)
        else:
            # Minimal initialization for qsop mode
            logger.info("qsop_mode_minimal_startup")
        
        logger.info("application_started")
    
    async def _on_shutdown(self, app: FastAPI):
        """Shutdown tasks."""
        logger.info("application_stopping")
        
        if self.is_api_mode:
            await self._shutdown_scheduler(app)
            await self._shutdown_websocket_manager(app)
            await self._shutdown_token_revocation(app)
            await self._shutdown_cosmos_db(app)
            await self._shutdown_secrets_manager(app)
            await self._shutdown_key_rotation(app)
        
        logger.info("application_stopped")
    
    def _setup_middleware(self, app: FastAPI):
        """Configure middleware stack."""
        # CORS (always enabled)
        cors_origins = os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000"
        )
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[o.strip() for o in cors_origins.split(",")],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-API-Key"],
        )
        
        # GZip compression
        app.add_middleware(GZipMiddleware, minimum_size=500)
        
        # Security middleware (if enabled)
        if self.enable_security_middleware and self.is_api_mode:
            try:
                from api.security.middleware import (
                    SecurityHeadersMiddleware,
                    RequestIDMiddleware,
                    RequestValidationMiddleware,
                    AuditLoggingMiddleware,
                )
                
                app.add_middleware(SecurityHeadersMiddleware, enable_hsts=self.is_production)
                app.add_middleware(RequestIDMiddleware)
                app.add_middleware(RequestValidationMiddleware)
                
                if os.getenv("ENABLE_AUDIT_LOGGING", "true").lower() == "true":
                    app.add_middleware(AuditLoggingMiddleware)
            except ImportError:
                logger.warning("security_middleware_not_available")
        
        # Rate limiting (if enabled)
        if self.enable_rate_limiting and self.is_api_mode:
            try:
                from slowapi import _rate_limit_exceeded_handler
                from slowapi.errors import RateLimitExceeded
                from api.security.rate_limiter import limiter
                
                app.state.limiter = limiter
                app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
            except ImportError:
                logger.warning("rate_limiting_not_available")
        
        # Metrics middleware
        try:
            from api.routers.metrics import MetricsMiddleware
            app.add_middleware(MetricsMiddleware)
        except ImportError:
            pass
    
    def _register_routers(self, app: FastAPI):
        """Register API routers."""
        # Create versioned API router
        api_v1_router = APIRouter(prefix="/api/v1")
        
        if self.is_api_mode:
            # Full router registration (legacy api/main.py)
            self._register_api_mode_routers(api_v1_router)
        else:
            # Minimal router registration (qsop mode)
            self._register_qsup_mode_routers(api_v1_router)
        
        # Include versioned router
        app.include_router(api_v1_router)
        
        # Root-level routers
        if self.is_api_mode:
            try:
                from api.routers.health import router as health_router
                app.include_router(health_router, tags=["Health"])
                
                from api.routers.metrics import router as metrics_router
                app.include_router(metrics_router, tags=["Metrics"])
            except ImportError:
                pass
    
    def _register_api_mode_routers(self, router: APIRouter):
        """Register full set of routers (api mode)."""
        # Core routers
        try:
            from api.routers import auth, auth_demo, jobs
            router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
            router.include_router(auth_demo.router, prefix="/auth", tags=["Authentication-Demo"])
            router.include_router(jobs.router, prefix="/jobs", tags=["Optimization Jobs"])
        except ImportError as e:
            logger.warning("core_router_import_failed", error=str(e))
        
        # WebSocket router
        if self.enable_websockets:
            try:
                from api.routers.websocket import router as websocket_router
                router.include_router(websocket_router, prefix="/ws", tags=["WebSocket"])
            except ImportError:
                pass
        
        # Feature routers
        feature_routers = [
            ("api.routers.backends", "/backends", "Quantum Backends"),
            ("api.routers.costs", "/costs", "Cost Estimation"),
            ("api.routers.api_keys", "/keys", "API Keys"),
            ("api.routers.oauth", "/oauth", "OAuth / SSO"),
            ("api.routers.scheduling", "/scheduling", "Job Scheduling"),
            ("api.routers.caching", "/caching", "Caching"),
            ("api.routers.batch", "/batch", "Batch Jobs"),
            ("api.routers.billing", "/billing", "Billing & Usage"),
            ("api.routers.tenant", "/tenant", "Multi-Tenant"),
            ("api.routers.circuits", "/circuits", "Circuit Visualization"),
            ("api.routers.marketplace", "/marketplace", "Algorithm Marketplace"),
            ("api.routers.federation", "/federation", "Federation & Multi-Region"),
            ("api.routers.security", "/security", "Security & Audit"),
            ("api.routers.performance", "/performance", "Performance & Optimization"),
            ("api.routers.demo_mode", "/demo", "Demo Mode"),
            ("api.routers.anomaly", "/anomaly", "Anomaly Detection"),
            ("api.routers.analytics", "/analytics", "API Analytics"),
            ("api.routers.health_aggregation", "/health/aggregated", "Health Aggregation"),
            ("api.routers.performance_dashboard", "/performance/dashboard", "Performance Dashboard"),
            ("api.webhooks", "/webhooks", "Webhooks"),
            ("api.alerts", "/alerts", "Alerts"),
            ("api.templates", "/templates", "Job Templates"),
        ]
        
        for module_path, prefix, tags in feature_routers:
            try:
                module = __import__(module_path, fromlist=["router"])
                router.include_router(module.router, prefix=prefix, tags=[tags])
            except (ImportError, AttributeError) as e:
                logger.debug("router_import_failed", module=module_path, error=str(e))
        
        # GraphQL (optional)
        try:
            from api.graphql import graphql_router, GRAPHQL_AVAILABLE
            if GRAPHQL_AVAILABLE and graphql_router:
                router.include_router(graphql_router, tags=["GraphQL"])
        except ImportError:
            pass
    
    def _register_qsup_mode_routers(self, router: APIRouter):
        """Register minimal set of routers (qsop mode)."""
        # Core routers only
        try:
            from qsop.api.routers import auth_router, create_api_router
            router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
            router.include_router(create_api_router(), tags=["API"])
        except ImportError:
            logger.warning("qsop_routers_not_available")
    
    def _add_core_endpoints(self, app: FastAPI):
        """Add core endpoints (health, metrics, info)."""
        @app.get("/health", tags=["Health"])
        async def health_check():
            return {
                "status": "healthy",
                "version": os.getenv("APP_VERSION", "0.1.0"),
                "environment": "production" if self.is_production else "development",
                "mode": self.mode,
            }
        
        @app.get("/ready", tags=["Health"])
        async def readiness_check():
            return {"status": "ready"}
        
        @app.get("/metrics", tags=["Observability"], include_in_schema=False)
        async def metrics_endpoint():
            return Response(
                content=generate_latest(),
                media_type=CONTENT_TYPE_LATEST,
            )
        
        @app.get("/api/v1/info", tags=["Info"])
        async def api_info():
            return {
                "name": "Quantum-Safe Secure Optimization Platform",
                "version": os.getenv("APP_VERSION", "0.1.0"),
                "mode": self.mode,
                "features": {
                    "telemetry": self.enable_telemetry,
                    "websockets": self.enable_websockets,
                    "frontend": self.enable_frontend,
                    "demo_mode": self.enable_demo_mode,
                    "rate_limiting": self.enable_rate_limiting,
                },
            }
        
        # WebSocket endpoint
        if self.enable_websockets:
            @app.websocket("/ws/{client_id}")
            async def websocket_endpoint(websocket: WebSocket, client_id: str):
                await websocket.accept()
                try:
                    while True:
                        await websocket.receive_text()
                except Exception:
                    pass
    
    def _mount_frontend(self, app: FastAPI):
        """Mount static frontend files."""
        frontend_dir = Path(__file__).parent.parent / "frontend"
        if not frontend_dir.exists():
            return
        
        app.mount("/css", StaticFiles(directory=frontend_dir / "css"), name="css")
        app.mount("/js", StaticFiles(directory=frontend_dir / "js"), name="js")
        
        @app.get("/manifest.json")
        async def serve_manifest():
            return FileResponse(
                frontend_dir / "manifest.json",
                media_type="application/manifest+json",
            )
        
        @app.get("/sw.js")
        async def serve_service_worker():
            response = FileResponse(
                frontend_dir / "sw.js",
                media_type="application/javascript",
            )
            response.headers["Cache-Control"] = "no-cache"
            return response
        
        @app.get("/")
        async def serve_index():
            return FileResponse(frontend_dir / "index.html")
    
    async def _init_cosmos_db(self, app):
        """Initialize Cosmos DB connection."""
        try:
            from api.db.cosmos import init_cosmos
            await init_cosmos()
            self._cosmos_initialized = True
            logger.info("cosmos_db_initialized")
        except Exception as e:
            logger.warning("cosmos_db_init_failed", error=str(e))
    
    async def _init_secrets_manager(self, app):
        """Initialize secrets manager."""
        try:
            from api.security.secrets_manager import init_secrets_manager
            await init_secrets_manager()
            logger.info("secrets_manager_initialized")
        except Exception as e:
            logger.warning("secrets_manager_init_failed", error=str(e))
    
    async def _init_token_revocation(self, app):
        """Initialize token revocation service."""
        try:
            from api.security.token_revocation import init_token_revocation
            await init_token_revocation()
            logger.info("token_revocation_initialized")
        except Exception as e:
            logger.warning("token_revocation_init_failed", error=str(e))
    
    async def _init_websocket_manager(self, app):
        """Initialize WebSocket manager."""
        if not self.enable_websockets:
            return
        try:
            from api.routers.websocket import init_websocket_manager
            await init_websocket_manager()
            self._websocket_initialized = True
            logger.info("websocket_manager_initialized")
        except Exception as e:
            logger.warning("websocket_manager_init_failed", error=str(e))
    
    async def _init_scheduler(self, app):
        """Initialize job scheduler."""
        try:
            from api.routers.scheduling import start_scheduler
            await start_scheduler()
            self._scheduler_initialized = True
            logger.info("scheduler_initialized")
        except Exception as e:
            logger.warning("scheduler_init_failed", error=str(e))
    
    async def _init_key_rotation(self, app):
        """Initialize PQC key rotation service with persistent storage."""
        try:
            from api.key_rotation import KeyRotationService, RotationPolicy
            from quantum_safe_crypto import SigningKeyPair
            
            # Initialize persistent key store
            from api.stores.persistent_key_store import init_persistent_key_store
            redis_url = os.getenv("QSOP_REDIS_URL") or os.getenv("REDIS_URL")
            persistent_store = await init_persistent_key_store(redis_url)
            
            rotation_policy = RotationPolicy(
                max_age_days=int(os.getenv("PQC_KEY_MAX_AGE_DAYS", "90")),
                rotate_before_days=int(os.getenv("PQC_KEY_ROTATE_BEFORE_DAYS", "7")),
            )
            app.state.key_rotation_service = KeyRotationService(
                rotation_policy=rotation_policy,
                store=persistent_store,  # Now wired up!
            )
            
            signing_key_meta = await app.state.key_rotation_service.generate_key(
                key_type="signing",
                security_level=3,
            )
            app.state.signing_keypair = SigningKeyPair()
            app.state.signing_key_id = signing_key_meta.key_id
            
            await app.state.key_rotation_service.start_rotation_scheduler(interval_hours=24)
            self._key_rotation_initialized = True
            logger.info("key_rotation_initialized", key_id=signing_key_meta.key_id)
        except Exception as e:
            logger.warning("key_rotation_init_failed", error=str(e))
    
    async def _shutdown_scheduler(self, app):
        """Shutdown job scheduler."""
        if self._scheduler_initialized:
            try:
                from api.routers.scheduling import stop_scheduler
                await stop_scheduler()
                logger.info("scheduler_stopped")
            except Exception as e:
                logger.warning("scheduler_shutdown_failed", error=str(e))
    
    async def _shutdown_websocket_manager(self, app):
        """Shutdown WebSocket manager."""
        if self._websocket_initialized:
            try:
                from api.routers.websocket import close_websocket_manager
                await close_websocket_manager()
                logger.info("websocket_manager_closed")
            except Exception as e:
                logger.warning("websocket_manager_shutdown_failed", error=str(e))
    
    async def _shutdown_token_revocation(self, app):
        """Shutdown token revocation service."""
        try:
            from api.security.token_revocation import close_token_revocation
            await close_token_revocation()
            logger.info("token_revocation_closed")
        except Exception as e:
            logger.warning("token_revocation_shutdown_failed", error=str(e))
    
    async def _shutdown_cosmos_db(self, app):
        """Shutdown Cosmos DB connection."""
        if self._cosmos_initialized:
            try:
                from api.db.cosmos import close_cosmos
                await close_cosmos()
                logger.info("cosmos_db_closed")
            except Exception as e:
                logger.warning("cosmos_db_shutdown_failed", error=str(e))
    
    async def _shutdown_secrets_manager(self, app):
        """Shutdown secrets manager."""
        try:
            from api.security.secrets_manager import close_secrets_manager
            await close_secrets_manager()
            logger.info("secrets_manager_closed")
        except Exception as e:
            logger.warning("secrets_manager_shutdown_failed", error=str(e))
    
    async def _shutdown_key_rotation(self, app):
        """Shutdown key rotation service."""
        if self._key_rotation_initialized:
            try:
                await app.state.key_rotation_service.stop_rotation_scheduler()
                logger.info("key_rotation_stopped")
            except Exception as e:
                logger.warning("key_rotation_shutdown_failed", error=str(e))
    
    def _get_description(self) -> str:
        """Get API description based on mode."""
        if self.is_api_mode:
            return """
            A production-ready platform integrating Post-Quantum Cryptography (PQC)
            with Quantum Optimization Algorithms.
            
            ## Features
            
            * **QAOA** - Quantum Approximate Optimization Algorithm
            * **VQE** - Variational Quantum Eigensolver
            * **Quantum Annealing** - D-Wave integration
            * **PQC Security** - ML-KEM-768 encryption and ML-DSA-65 signatures
            * **Celery Workers** - Distributed job processing
            * **WebSocket** - Real-time updates
            
            ## Security
            
            All endpoints secured with:
            - ML-DSA-65 signed JWT tokens
            - ML-KEM-768 encrypted payloads (optional)
            - Hybrid TLS (X25519 + ML-KEM)
            """
        else:
            return "Quantum-Safe Secure Optimization Platform API (Minimal Mode)"


# Factory instances for easy import
api_mode_factory = AppFactory(mode="api")
qsop_mode_factory = AppFactory(mode="qsop")

# Default app instance (API mode for backward compatibility)
app = api_mode_factory.create_app()


def create_api_app(**kwargs) -> FastAPI:
    """Create API mode application (full-featured)."""
    factory = AppFactory(mode="api", **kwargs)
    return factory.create_app()


def create_qsup_app(**kwargs) -> FastAPI:
    """Create QSOP mode application (minimal)."""
    factory = AppFactory(mode="qsop", **kwargs)
    return factory.create_app()


def run(host: str = "0.0.0.0", port: int = 8000, reload: bool = None, workers: int = 1):
    """Run the application with uvicorn."""
    if reload is None:
        reload = os.getenv("APP_ENV", "development") == "development"
    
    import uvicorn
    uvicorn.run(
        "api.app_factory:app",
        host=host,
        port=port,
        reload=reload,
        workers=1 if reload else workers,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    run()

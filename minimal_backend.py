"""
Minimal QSOP backend for development.

SECURITY WARNING: This backend is for DEVELOPMENT ONLY.
For production, use the full api/main.py with proper security.
"""

import os
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_ENV = os.environ.get("APP_ENV", "development")

JOBS_STORE: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("starting_application")
    if APP_ENV == "production":
        logger.warning("SECURITY: minimal_backend.py is NOT for production use!")
    yield
    logger.info("shutting_down_application")


app = FastAPI(
    title="Quantum-Safe Optimization Platform (Development)",
    version="0.1.0",
    description="Minimal development backend - DO NOT USE IN PRODUCTION",
    lifespan=lifespan,
)

CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:8080,http://localhost:8000,http://127.0.0.1:3000",
)

if APP_ENV == "production":
    cors_origins_list = [origin.strip() for origin in CORS_ORIGINS.split(",")]
    logger.info(f"Production CORS origins: {cors_origins_list}")
else:
    cors_origins_list = ["*"]
    logger.warning("DEVELOPMENT MODE: CORS allows all origins - NOT FOR PRODUCTION")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list,
    allow_credentials=True if APP_ENV != "production" else False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)


@app.get("/", include_in_schema=False)
async def root() -> dict:
    """Root endpoint - serves frontend if available, otherwise API info."""
    if FRONTEND_DIR.exists():
        return FileResponse(FRONTEND_DIR / "index.html")
    return {
        "message": "Quantum-Safe Optimization Platform API",
        "version": "0.1.0",
        "status": "operational",
    }


@app.get("/health")
async def health_check(detailed: bool = False) -> dict:
    """Health check endpoint."""
    if detailed:
        return {
            "status": "healthy",
            "version": "0.1.0",
            "env": "development",
            "database": "connected",
            "quantum_backend": "aer_simulator",
            "crypto_provider": "liboqs",
        }
    return {"status": "healthy", "version": "0.1.0", "env": "development"}


@app.get("/health/crypto")
async def health_crypto() -> dict:
    """Crypto provider health check."""
    return {
        "status": "healthy",
        "liboqs_version": "0.10.0",
        "algorithms_supported": ["Kyber512", "Kyber768", "Dilithium2", "Dilithium3", "SPHINCS+"],
    }


@app.get("/ready")
async def readiness_check() -> dict:
    """Readiness check endpoint."""
    return {"status": "ready"}


@app.get("/api/v1/info")
async def api_info() -> dict:
    """API information endpoint."""
    return {
        "name": "Quantum-Safe Optimization Platform",
        "version": "0.1.0",
        "pqc_kem_algorithm": "Kyber512",
        "pqc_sig_algorithm": "Dilithium2",
        "quantum_backend": "aer_simulator",
    }


# Job management endpoints with in-memory store
@app.get("/api/v1/jobs")
async def list_jobs(limit: int = 10, offset: int = 0, status: str = None, type: str = None) -> dict:
    """List jobs with optional filtering."""
    jobs = list(JOBS_STORE.values())
    if status and status != "all":
        jobs = [j for j in jobs if j["status"] == status]
    if type and type != "all":
        jobs = [j for j in jobs if j.get("problem_type", "").lower() == type.lower()]
    jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)
    total = len(jobs)
    return {"jobs": jobs[offset : offset + limit], "total": total, "limit": limit, "offset": offset}


@app.post("/api/v1/jobs")
async def create_job(request: Request) -> dict:
    """Create a new optimization job."""
    body = await request.json()
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    job = {
        "id": job_id,
        "status": "completed",
        "problem_type": body.get("problem_type", "QAOA"),
        "backend": body.get("backend", "local_simulator"),
        "config": body.get("config", {}),
        "encrypted": body.get("encrypted", False),
        "signed": body.get("signed", False),
        "created_at": now,
        "updated_at": now,
        "result": {
            "optimal_value": -3.42,
            "optimal_params": [0.35, 1.21, 0.78, 2.05],
            "convergence_history": [-1.2, -2.1, -2.8, -3.1, -3.3, -3.42],
            "num_iterations": 6,
            "execution_time_ms": 1234,
        },
    }
    JOBS_STORE[job_id] = job
    return job


@app.get("/api/v1/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    """Get job details."""
    if job_id in JOBS_STORE:
        return JOBS_STORE[job_id]
    return {
        "id": job_id,
        "status": "completed",
        "problem_type": "QAOA",
        "backend": "local_simulator",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": {"optimal_value": -3.42, "optimal_params": [0.35, 1.21]},
    }


@app.delete("/api/v1/jobs/{job_id}")
async def delete_job(job_id: str) -> dict:
    """Delete a job."""
    JOBS_STORE.pop(job_id, None)
    return {"message": f"Job {job_id} deleted"}


@app.post("/api/v1/jobs/{job_id}/retry")
async def retry_job(job_id: str) -> dict:
    """Retry a failed job."""
    if job_id in JOBS_STORE:
        JOBS_STORE[job_id]["status"] = "pending"
        return JOBS_STORE[job_id]
    return {"id": job_id, "status": "pending", "message": "Job resubmitted"}


# Stub authentication endpoints
@app.post("/api/v1/auth/register")
async def register() -> dict:
    """Register user."""
    return {"message": "User registered successfully", "user_id": "user_001"}


@app.post("/api/v1/auth/login")
async def login() -> dict:
    """Login user."""
    return {"access_token": "sample_token", "token_type": "bearer"}


@app.get("/api/v1/auth/me")
async def me() -> dict:
    """Get current user."""
    return {
        "user_id": "user_001",
        "username": "demo_user",
        "email": "demo@example.com",
        "created_at": "2024-01-01T00:00:00Z",
    }


@app.post("/api/v1/auth/logout")
async def logout() -> dict:
    """Logout user."""
    return {"message": "Logged out successfully"}


@app.post("/api/v1/auth/keys/generate")
async def keys_generate() -> dict:
    """Generate cryptographic keys."""
    return {
        "message": "Keys generated successfully",
        "kem_key_id": "kem_key_001",
        "sig_key_id": "sig_key_001",
    }


@app.post("/api/v1/auth/keys/register")
async def keys_register() -> dict:
    """Register cryptographic keys."""
    return {"message": "Keys registered successfully"}


@app.get("/api/v1/auth/keys")
async def keys() -> dict:
    """List registered keys."""
    return {
        "keys": [
            {"key_id": "kem_key_001", "type": "Kyber512", "created_at": "2024-01-01"},
            {"key_id": "sig_key_001", "type": "Dilithium2", "created_at": "2024-01-01"},
        ]
    }


# Cloud credentials endpoints
@app.get("/api/v1/credentials")
async def list_credentials() -> dict:
    """List cloud credentials."""
    return {"credentials": [], "total": 0}


@app.post("/api/v1/credentials")
async def create_credentials() -> dict:
    """Create cloud credentials."""
    return {"message": "Credentials created successfully", "cred_id": "cred_001"}


@app.delete("/api/v1/credentials/{cred_id}")
async def delete_credentials(cred_id: str) -> dict:
    """Delete cloud credentials."""
    return {"message": f"Credentials {cred_id} deleted"}


# Cryptographic endpoints
@app.post("/api/v1/crypto/kem/test")
async def crypto_kem_test() -> dict:
    """Test KEM functionality."""
    return {"status": "success", "algorithm": "Kyber512", "test_result": "PASSED", "time_ms": 1.23}


@app.post("/api/v1/crypto/kem/keygen")
async def crypto_kem_keygen() -> dict:
    """Generate KEM key pair."""
    return {
        "key_id": "kem_key_new_001",
        "public_key": "base64_encoded_public_key",
        "algorithm": "Kyber512",
    }


@app.post("/api/v1/crypto/sign/test")
async def crypto_sign_test() -> dict:
    """Test signature functionality."""
    return {
        "status": "success",
        "algorithm": "Dilithium2",
        "test_result": "PASSED",
        "time_ms": 2.45,
    }


@app.post("/api/v1/crypto/sign/keygen")
async def crypto_sign_keygen() -> dict:
    """Generate signature key pair."""
    return {
        "key_id": "sig_key_new_001",
        "public_key": "base64_encoded_public_key",
        "algorithm": "Dilithium2",
    }


@app.post("/api/v1/crypto/encrypt/test")
async def crypto_encrypt_test() -> dict:
    """Test encryption functionality."""
    return {"status": "success", "algorithm": "AES-GCM", "test_result": "PASSED", "time_ms": 0.87}


# Workers endpoints
@app.get("/api/v1/workers")
async def list_workers() -> dict:
    """List workers."""
    return {
        "workers": [
            {
                "worker_id": "worker_001",
                "name": "Quantum Worker 1",
                "status": "active",
                "jobs_completed": 42,
            },
            {
                "worker_id": "worker_002",
                "name": "Quantum Worker 2",
                "status": "idle",
                "jobs_completed": 15,
            },
        ],
        "total": 2,
    }


# Webhooks endpoints
@app.get("/api/v1/webhooks/stats")
async def webhook_stats() -> dict:
    """Get webhook statistics."""
    return {
        "total_webhooks": 10,
        "successful_calls": 142,
        "failed_calls": 3,
        "recent_deliveries": [
            {
                "event": "job.completed",
                "url": "https://example.com/webhook",
                "status": "200",
                "timestamp": "2024-01-01T12:00:00Z",
            }
        ],
    }


# WebSocket status endpoint (stub)
@app.get("/api/v1/ws/status")
async def ws_status() -> dict:
    """Get WebSocket status."""
    return {
        "websocket": "available",
        "connections": 0,
        "demo_mode": True,
        "endpoints": {
            "job_updates": "/api/v1/ws/jobs/{job_id}",
            "all_jobs": "/api/v1/ws/jobs",
        },
    }


# Connectivity check endpoint for dashboard
@app.get("/api/v1/connectivity")
async def connectivity_check() -> dict:
    """Check connectivity to all services."""
    return {
        "api": {"status": "healthy", "latency_ms": 1},
        "cosmos_db": {"status": "healthy", "latency_ms": 5, "demo_mode": True},
        "redis": {"status": "healthy", "latency_ms": 2, "demo_mode": True},
        "pqc_crypto": {"status": "healthy", "latency_ms": 1, "provider": "fallback"},
        "secrets_manager": {"status": "healthy", "latency_ms": 1, "demo_mode": True},
        "websocket": {"status": "available", "connections": 0},
    }


# PQC Security status
@app.get("/api/v1/security/pqc/status")
async def pqc_status() -> dict:
    """Get PQC algorithm status."""
    return {
        "kem": {"algorithm": "ML-KEM-768", "enabled": True, "nist_level": 3},
        "dsa": {"algorithm": "ML-DSA-65", "enabled": True, "nist_level": 3},
        "cipher": {"algorithm": "AES-256-GCM", "enabled": True},
    }


# AI suggestions
@app.post("/api/v1/ai/suggestions")
async def ai_suggestions(request: Request) -> dict:
    """Get AI-powered optimization suggestions."""
    body = await request.json()
    problem_type = body.get("problem_type", "QAOA")
    return {
        "suggestions": [
            {
                "title": f"Optimized {problem_type} Parameters",
                "description": f"Based on problem analysis, consider increasing circuit depth for better convergence.",
                "confidence": 0.85,
                "impact": "high",
            },
            {
                "title": "Backend Recommendation",
                "description": "Local simulator is optimal for this problem size.",
                "confidence": 0.92,
                "impact": "medium",
            },
        ]
    }


# Cost estimation
@app.post("/api/v1/costs/estimate")
async def cost_estimate(request: Request) -> dict:
    """Estimate job execution cost."""
    body = await request.json()
    backend = body.get("backend", "local_simulator")
    is_free = backend in ("local_simulator", "advanced_simulator")
    return {
        "credits": 0 if is_free else 10,
        "estimated_time_seconds": 5 if is_free else 120,
        "backend": backend,
        "breakdown": {
            "computation": "Free (simulator)" if is_free else "10 credits",
            "storage": "Free",
            "crypto": "Free",
        },
    }


# Activity feed
@app.get("/api/v1/activity/recent")
async def recent_activity() -> dict:
    """Get recent activity."""
    return {
        "activities": [
            {
                "type": "job_completed",
                "message": "QAOA job completed successfully",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            {
                "type": "system",
                "message": "PQC crypto provider initialized",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        ]
    }


# Webhooks management
@app.get("/api/v1/webhooks")
async def list_webhooks() -> dict:
    """List webhooks."""
    return {"webhooks": [], "total": 0}


@app.post("/api/v1/webhooks")
async def create_webhook(request: Request) -> dict:
    """Create a webhook."""
    body = await request.json()
    return {
        "id": f"wh_{uuid.uuid4().hex[:8]}",
        "url": body.get("url", ""),
        "events": body.get("events", []),
        "active": True,
    }


# Keys management
@app.get("/api/v1/keys")
async def list_keys() -> dict:
    """List cryptographic keys."""
    return {
        "keys": [
            {
                "id": "kem_key_001",
                "type": "ML-KEM-768",
                "algorithm": "Kyber768",
                "created_at": "2024-01-01T00:00:00Z",
                "status": "active",
            },
            {
                "id": "sig_key_001",
                "type": "ML-DSA-65",
                "algorithm": "Dilithium3",
                "created_at": "2024-01-01T00:00:00Z",
                "status": "active",
            },
        ],
        "total": 2,
    }


@app.post("/api/v1/keys/generate")
async def generate_keys(request: Request) -> dict:
    """Generate new cryptographic keys."""
    return {
        "key_id": f"key_{uuid.uuid4().hex[:8]}",
        "public_key": "base64_encoded_public_key_demo",
        "private_key": "base64_encoded_private_key_demo",
        "algorithm": "ML-KEM-768",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/v1/keys/{key_id}/rotate")
async def rotate_key(key_id: str) -> dict:
    """Rotate a cryptographic key."""
    return {
        "message": f"Key {key_id} rotated successfully",
        "new_key_id": f"key_{uuid.uuid4().hex[:8]}",
    }


@app.delete("/api/v1/keys/{key_id}")
async def delete_key(key_id: str) -> dict:
    """Delete a cryptographic key."""
    return {"message": f"Key {key_id} deleted"}


@app.get("/api/v1/auth/tokens")
async def list_tokens() -> list:
    """List API tokens."""
    return [
        {
            "id": "tok_001",
            "name": "Default Token",
            "prefix": "qso_",
            "last4": "a1b2",
            "created_at": "2024-01-01T00:00:00Z",
            "expires_at": None,
            "last_used": "2024-01-15T12:00:00Z",
            "permissions": ["read", "write"],
        },
    ]


@app.post("/api/v1/auth/tokens")
async def create_token(body: dict) -> dict:
    """Create a new API token."""
    return {
        "id": f"tok_{uuid.uuid4().hex[:8]}",
        "name": body.get("name", "New Token"),
        "token": f"qsop_{uuid.uuid4().hex}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": None,
        "permissions": body.get("permissions", ["read"]),
    }


@app.post("/api/v1/webhooks/config")
async def save_webhook_config(body: dict) -> dict:
    """Save webhook configuration."""
    return {"message": "Webhook configuration saved", "config": body}


@app.post("/api/v1/webhooks/test")
async def test_webhook(body: dict) -> dict:
    """Send a test webhook event."""
    return {"message": "Test webhook sent successfully", "status": "delivered"}


@app.get("/api/v1/webhooks/export")
async def export_webhooks(format: str = "json") -> dict:
    """Export webhook configuration."""
    return {"webhooks": [], "format": format, "exported_at": datetime.now(timezone.utc).isoformat()}


@app.get("/api/v1/webhooks/history")
async def webhook_history(
    status: str = "all", event: str = "all", range_period: str = Query("7d", alias="range")
) -> list:
    """Get webhook delivery history."""
    return []


@app.post("/api/v1/users/settings")
async def save_user_settings(body: dict) -> dict:
    """Save user settings/preferences."""
    return {"message": "Settings saved", "settings": body}


@app.get("/api/v1/users/usage")
async def get_user_usage(period: str = "30d") -> dict:
    """Get user usage statistics."""
    return {
        "jobs_submitted": 47,
        "jobs_completed": 42,
        "compute_time_hours": 2.3,
        "qubits_used": 1280,
        "api_requests": 3420,
        "quota": {"jobs_limit": 100, "hours_limit": 10, "requests_limit": 10000},
        "daily": [
            {"date": datetime.now(timezone.utc).isoformat(), "jobs": 3},
        ],
    }


# Serve frontend static files
FRONTEND_DIR = Path(__file__).parent / "frontend"
if FRONTEND_DIR.exists():
    # Mount static assets
    app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
    app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")
    if (FRONTEND_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/manifest.json")
    async def serve_manifest():
        return FileResponse(FRONTEND_DIR / "manifest.json", media_type="application/manifest+json")

    @app.get("/sw.js")
    async def serve_service_worker():
        response = FileResponse(FRONTEND_DIR / "sw.js", media_type="application/javascript")
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Service-Worker-Allowed"] = "/"
        return response

    @app.get("/dashboard")
    async def serve_dashboard():
        return FileResponse(FRONTEND_DIR / "dashboard.html")

    @app.get("/dashboard.html")
    async def serve_dashboard_html():
        return FileResponse(FRONTEND_DIR / "dashboard.html")

    @app.get("/index.html")
    async def serve_index_html():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/research-demo.html")
    async def serve_research_demo():
        return FileResponse(FRONTEND_DIR / "research-demo.html")

    # Override root to serve the landing page
    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(FRONTEND_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)

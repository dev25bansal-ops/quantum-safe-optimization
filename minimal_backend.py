"""
Minimal QSOP backend for development.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    logger.info("starting_application")
    yield
    logger.info("shutting_down_application")


app = FastAPI(
    title="Quantum-Safe Optimization Platform",
    version="0.1.0",
    description="Minimal development backend",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
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


# Stub endpoints for job management
@app.get("/api/v1/jobs")
async def list_jobs() -> dict:
    """List jobs."""
    return {"jobs": [], "total": 0, "limit": 10, "offset": 0}


@app.post("/api/v1/jobs")
async def create_job() -> dict:
    """Create a job."""
    return {"id": "job_001", "status": "pending", "message": "Job created successfully"}


@app.get("/api/v1/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    """Get job details."""
    return {"id": job_id, "status": "completed", "result": "Sample result"}


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)

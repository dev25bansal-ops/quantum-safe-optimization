"""
Vercel Serverless API Handler - Demo Mode

Lightweight FastAPI application providing demo API endpoints for the
Quantum-Safe Optimization Platform when deployed on Vercel.
"""

import base64
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="Quantum-Safe Optimization Platform",
    description="Demo API - Vercel Deployment",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory demo storage (resets on cold start – expected for serverless)
# ---------------------------------------------------------------------------

demo_users: dict[str, dict] = {
    "admin": {
        "id": "user_admin",
        "username": "admin",
        "email": "admin@example.com",
        "password_hash": hashlib.sha256("admin123!".encode()).hexdigest(),
        "role": "admin",
    }
}

demo_jobs: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Token helpers (simple base64 tokens – fine for demo)
# ---------------------------------------------------------------------------

DEMO_SECRET = "quantum-safe-demo-vercel"


def _generate_token(username: str) -> str:
    payload = {
        "sub": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + 86400,
        "iss": "quantum-safe-demo",
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"demo.{encoded}"


def _verify_token(token: str) -> dict | None:
    try:
        if not token or not token.startswith("demo."):
            return None
        b64 = token[5:]
        b64 += "=" * (4 - len(b64) % 4) if len(b64) % 4 else ""
        payload = json.loads(base64.urlsafe_b64decode(b64))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def _get_current_user(authorization: str | None) -> dict | None:
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "")
    payload = _verify_token(token)
    if not payload:
        return None
    return demo_users.get(payload.get("sub"))


# ───────────────────────────── Auth ──────────────────────────────


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    username: str = ""
    email: str = ""
    password: str


class DemoModeRequest(BaseModel):
    email: str = "demo@quantum.dev"


@app.post("/api/v1/auth/register")
async def register(req: RegisterRequest):
    if req.username in demo_users:
        raise HTTPException(status_code=400, detail="Username already exists")
    user_id = f"user_{uuid.uuid4().hex[:8]}"
    demo_users[req.username] = {
        "id": user_id,
        "username": req.username,
        "email": req.email,
        "password_hash": hashlib.sha256(req.password.encode()).hexdigest(),
        "role": "user",
    }
    token = _generate_token(req.username)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "username": req.username,
            "email": req.email,
            "role": "user",
        },
    }


@app.post("/api/v1/auth/login")
async def login(req: LoginRequest):
    username = req.username or (req.email.split("@")[0] if req.email else "")
    user = demo_users.get(username)
    if not user or user["password_hash"] != hashlib.sha256(req.password.encode()).hexdigest():
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _generate_token(username)
    return {"access_token": token, "token_type": "bearer"}


@app.post("/api/v1/auth/demo-mode")
async def demo_mode(req: DemoModeRequest):
    username = "demo_user"
    if username not in demo_users:
        demo_users[username] = {
            "id": "user_demo",
            "username": username,
            "email": req.email,
            "password_hash": "",
            "role": "user",
        }
    token = _generate_token(username)
    return {"access_token": token, "token_type": "bearer", "demo": True}


@app.get("/api/v1/auth/me")
async def get_me(authorization: str = Header(None)):
    user = _get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "pqc_enabled": True,
        "signing_algorithm": "ML-DSA-65",
    }


@app.post("/api/v1/auth/logout")
async def logout():
    return {"message": "Logged out successfully"}


@app.put("/api/v1/auth/keys/encryption-key")
async def register_encryption_key(request: Request):
    return {"message": "Encryption key registered (demo)", "algorithm": "ML-KEM-768"}


# ───────────────────────────── Jobs ──────────────────────────────


class JobSubmission(BaseModel):
    problem_type: str = "maxcut"
    problem_config: dict = {}
    parameters: dict = {}
    backend: str = "local_simulator"
    encrypted: bool = False
    signed: bool = False
    priority: int = 5


@app.post("/api/v1/jobs", status_code=202)
async def create_job(req: JobSubmission, authorization: str = Header(None)):
    user = _get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    if req.encrypted:
        raise HTTPException(
            status_code=400,
            detail="No ML-KEM public key registered. Use PUT /auth/keys/encryption-key first.",
        )

    job_id = f"job_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    job = {
        "job_id": job_id,
        "status": "completed",
        "problem_type": req.problem_type,
        "backend": req.backend,
        "created_at": now,
        "updated_at": now,
        "encrypted": req.encrypted,
        "signed": req.signed,
        "priority": req.priority,
        "result": {
            "optimal_value": -3.72,
            "optimal_params": [0.42, 1.13, 0.87, 2.01],
            "iterations": 150,
            "convergence": True,
        },
        "user_id": user["id"],
    }
    demo_jobs[job_id] = job
    return job


@app.get("/api/v1/jobs")
async def list_jobs(
    authorization: str = Header(None),
    page: int = 1,
    page_size: int = 10,
    status: str = None,
    problem_type: str = None,
):
    user = _get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    user_jobs = [j for j in demo_jobs.values() if j.get("user_id") == user["id"]]
    if status:
        user_jobs = [j for j in user_jobs if j["status"] == status]
    if problem_type:
        user_jobs = [j for j in user_jobs if j["problem_type"] == problem_type]
    return {
        "jobs": user_jobs[(page - 1) * page_size : page * page_size],
        "total": len(user_jobs),
        "page": page,
        "page_size": page_size,
    }


@app.get("/api/v1/jobs/{job_id}")
async def get_job(job_id: str, authorization: str = Header(None)):
    user = _get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    job = demo_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ───────────────────────────── Backends ──────────────────────────


@app.get("/api/v1/backends/status")
async def backends_status():
    return {
        "backends": [
            {"name": "local_simulator", "status": "available", "queue_depth": 0, "provider": "Qiskit Aer"},
            {"name": "ibm_quantum", "status": "available", "queue_depth": 12, "provider": "IBM Quantum"},
            {"name": "aws_braket", "status": "available", "queue_depth": 3, "provider": "Amazon Braket"},
        ]
    }


# ───────────────────────────── Cost Estimation ───────────────────


class CostRequest(BaseModel):
    algorithm: str = "qaoa"
    num_qubits: int = 4
    shots: int = 1000
    backend: str = "local_simulator"


@app.post("/api/v1/costs/estimate")
async def estimate_cost(req: CostRequest):
    cost_map = {
        "local_simulator": 0.0,
        "ibm_quantum": round(1.60 * req.num_qubits * (req.shots / 1000), 2),
        "aws_braket": round(0.30 * req.num_qubits * (req.shots / 1000), 2),
    }
    return {
        "algorithm": req.algorithm,
        "num_qubits": req.num_qubits,
        "shots": req.shots,
        "backend": req.backend,
        "estimated_cost_usd": cost_map.get(req.backend, 0.0),
        "estimated_time_seconds": req.num_qubits * 2 + req.shots // 100,
    }


# ───────────────────────────── Health ────────────────────────────


@app.get("/health")
@app.get("/api/v1/health")
async def health():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "demo_mode": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "api": "operational",
            "database": "demo_mode",
            "crypto": "demo_mode",
        },
    }


# ───────────────────────────── WebSocket stub ────────────────────


@app.get("/api/v1/ws/status")
async def ws_status():
    return {"websocket": "not_available_on_vercel", "demo_mode": True}


# ───────────────────────────── Catch-all ─────────────────────────


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def catch_all(path: str):
    return {
        "status": "demo_mode",
        "message": f"Endpoint /api/{path} is available in the full deployment.",
        "demo": True,
    }

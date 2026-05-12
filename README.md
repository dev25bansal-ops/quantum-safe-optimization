# Quantum-Safe Secure Optimization Platform

A production-ready platform integrating **Post-Quantum Cryptography (PQC)** with **Quantum Optimization Algorithms** (QAOA, VQE, Quantum Annealing).

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Client Applications                         │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTPS (TLS 1.3 + ML-KEM hybrid)
┌─────────────────────────▼───────────────────────────────────────┐
│                    API Gateway (FastAPI)                        │
│  • PQC Authentication (ML-DSA signed JWTs)                      │
│  • Rate Limiting • Request Validation                           │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│               Optimization Service Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ QAOA Runner  │  │ VQE Runner   │  │ Annealing Runner     │  │
│  │ (MaxCut,     │  │ (Molecular   │  │ (QUBO, D-Wave)       │  │
│  │  Portfolio)  │  │  Hamiltonians│  │                      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│             Quantum Backend Abstraction Layer                   │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────┐ │
│  │IBM Quantum │ │AWS Braket  │ │Azure       │ │D-Wave Leap   │ │
│  │ (Qiskit)   │ │            │ │Quantum     │ │              │ │
│  └────────────┘ └────────────┘ └────────────┘ └──────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## 🔐 Security Features

- **ML-KEM-768**: NIST FIPS 203 key encapsulation for data encryption
- **ML-DSA-65**: NIST FIPS 204 digital signatures for authentication
- **Hybrid TLS**: X25519 + ML-KEM for defense-in-depth
- **Encrypted Storage**: AES-256-GCM with PQC key wrapping
- **Argon2id** password hashing (memory-hard, resistant to GPU attacks)
- **CSRF Protection**: HMAC-signed tokens with configurable secret
- **Rate Limiting**: Per-IP and per-user rate limits via Redis
- **Resource Quotas**: Per-user/per-tenant limits on jobs, storage, and compute
- **Data Retention**: Automated cleanup of old jobs, keys, and audit logs
- **PQC Key Rotation**: Persistent key store with automatic rotation

See [Security Model](docs/SECURITY_MODEL.md) for the complete security architecture.

## ✨ Advanced Features

### Problem Auto-Selector
Automatically recommends the best solving approach (classical, quantum, or hybrid) based on problem characteristics, hardware capabilities, and error rates.

```bash
curl -X POST http://localhost:8000/api/v1/problems/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "problem_type": "maxcut",
    "num_variables": 50,
    "connectivity": "sparse",
    "precision_required": 0.95
  }'
```

### Adaptive Shot Allocation
Dynamically adjusts the number of quantum shots based on convergence rate, reducing hardware costs by up to 60% for well-converging problems.

### Resource Quota Management
Enforce per-user limits on:
- Concurrent jobs
- Total qubit-seconds per month
- Storage usage
- API request rate

### Data Retention Policies
Automated cleanup of stale data:
- Completed jobs: 90 days
- Failed jobs: 30 days
- Audit logs: 365 days
- Expired encryption keys: immediate

### Multi-Database Support
Deploy with either **Azure Cosmos DB** (default) or **PostgreSQL** (self-hosted). Configure via `DATABASE_TYPE` env var.

## 📁 Project Structure

```
quantum-safe-optimization/
├── crypto/                    # Rust PQC cryptography core
│   ├── Cargo.toml
│   ├── src/
│   │   ├── lib.rs            # Main library exports
│   │   ├── kem.rs            # ML-KEM key encapsulation
│   │   ├── signatures.rs     # ML-DSA digital signatures
│   │   └── encryption.rs     # Hybrid encryption utilities
│   └── python/               # PyO3 Python bindings
│
├── optimization/             # Quantum optimization algorithms
│   ├── pyproject.toml
│   └── src/
│       ├── backends/         # Quantum backend abstractions
│       ├── qaoa/             # QAOA implementations
│       ├── vqe/              # VQE implementations
│       └── annealing/        # Quantum annealing (D-Wave)
│
├── api/                      # FastAPI REST service
│   ├── main.py
│   ├── routers/
│   ├── models/
│   └── auth/
│
├── infrastructure/           # Deployment configurations
│   ├── terraform/
│   └── docker/
│
└── tests/                    # Test suites
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Rust 1.75+ (for crypto module)
- Docker & Docker Compose
- Azure subscription (for Cosmos DB)

### Installation

```bash
# Clone repository
git clone https://github.com/your-org/quantum-safe-optimization.git
cd quantum-safe-optimization

# Set up Python environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ./optimization
pip install -r api/requirements.txt

# Build Rust crypto module
cd crypto
cargo build --release
maturin develop  # Install Python bindings

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Start services
docker-compose up -d redis
uvicorn api.main:app --reload
```

## 📖 API Usage

### Submit Optimization Job

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Authorization: Bearer <pqc-signed-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "problem_type": "QAOA",
    "problem_config": {
      "type": "maxcut",
      "graph": {"edges": [[0,1], [1,2], [2,0]], "weights": [1,1,1]}
    },
    "parameters": {
      "layers": 3,
      "optimizer": "COBYLA",
      "shots": 1000,
      "backend": "ibm_quantum"
    }
  }'
```

### Check Job Status

```bash
curl http://localhost:8000/api/v1/jobs/{job_id} \
  -H "Authorization: Bearer <pqc-signed-jwt>"
```

## 🔧 Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENV` | Environment (development/production) | `development` |
| `JWT_SECRET` | JWT signing secret (required in production) | — |
| `CSRF_SECRET` | CSRF token secret (required in production) | — |
| `DATABASE_TYPE` | Database backend (`cosmos` or `postgres`) | `cosmos` |
| `COSMOS_ENDPOINT` | Azure Cosmos DB endpoint | `https://localhost:8081` |
| `COSMOS_KEY` | Cosmos DB key | — |
| `DATABASE_URL` | PostgreSQL connection URL (if using postgres) | — |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `RATE_LIMIT_REQUESTS` | Max requests per window | `100` |
| `RATE_LIMIT_WINDOW` | Rate limit window (seconds) | `60` |

See [`.env.example`](.env.example) for the complete configuration template.

## 📊 Supported Problem Types

### QAOA
- MaxCut
- Portfolio Optimization
- Traveling Salesman (TSP)
- Graph Coloring

### VQE
- Molecular Ground State Energy
- Electronic Structure Calculations

### Quantum Annealing
- QUBO (Quadratic Unconstrained Binary Optimization)
- Ising Model

## 📚 Documentation

| Document | Description |
|---|---|
| [Security Model](docs/SECURITY_MODEL.md) | Complete security architecture, threat model, and controls |
| [API Versioning](docs/API_VERSIONING.md) | Versioning policy, deprecation timeline, migration guides |
| [API Reference](docs/API.md) | Full API endpoint documentation |
| [Deployment Guide](docs/DEPLOYMENT.md) | Production deployment instructions |
| [Disaster Recovery](docs/DISASTER_RECOVERY.md) | Backup and recovery procedures |
| [Architecture Decisions](docs/adrs/) | ADRs documenting key architectural decisions |

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

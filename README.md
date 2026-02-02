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
| `COSMOS_DB_URI` | Azure Cosmos DB connection string | - |
| `COSMOS_DB_DATABASE` | Database name | `quantum_optimization` |
| `IBM_QUANTUM_TOKEN` | IBM Quantum API token | - |
| `AWS_BRAKET_REGION` | AWS Braket region | `us-east-1` |
| `DWAVE_API_TOKEN` | D-Wave Leap API token | - |
| `PQC_KEY_PATH` | Path to PQC key files | `./keys` |

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

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

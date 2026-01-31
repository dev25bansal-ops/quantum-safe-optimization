# Quantum-Safe Secure Optimization Platform (QSOP)

A production-ready platform for quantum-safe cryptography and quantum-inspired optimization algorithms.

## Overview

QSOP provides:

- **Post-Quantum Cryptography**: CRYSTALS-Kyber, CRYSTALS-Dilithium, and other NIST-approved algorithms via liboqs
- **Quantum Optimization**: QAOA, VQE, and quantum annealing simulations via Qiskit
- **Hybrid Algorithms**: Classical-quantum hybrid solvers for combinatorial optimization
- **Enterprise Security**: End-to-end encryption with quantum-resistant key exchange

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      API Gateway                             │
│                   (FastAPI + ASGI)                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Crypto    │  │ Optimization│  │    Observability    │  │
│  │   Service   │  │   Engine    │  │  (OTEL + Prometheus)│  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   liboqs    │  │   Qiskit    │  │       Redis         │  │
│  │  (PQC Lib)  │  │  (Quantum)  │  │      (Cache)        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    PostgreSQL / SQLite                       │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (optional)
- Redis (for caching)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/quantum-secure-opt.git
cd quantum-secure-opt

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows

# Install dependencies
pip install -e ".[dev]"

# Copy environment config
cp .env.example .env

# Run the development server
uvicorn qsop.main:app --reload
```

### Using Docker

```bash
docker-compose up -d
```

The API will be available at `http://localhost:8000`.

## Configuration

All configuration is managed via environment variables. See `.env.example` for all options.

| Variable | Description | Default |
|----------|-------------|---------|
| `QSOP_ENV` | Environment (dev/staging/prod) | `dev` |
| `QSOP_DEBUG` | Enable debug mode | `false` |
| `QSOP_API_HOST` | API bind host | `0.0.0.0` |
| `QSOP_API_PORT` | API bind port | `8000` |
| `QSOP_PQC_ALGORITHM` | Default PQC algorithm | `Kyber512` |
| `QSOP_DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///./qsop.db` |

## API Endpoints

### Health & Status

- `GET /health` - Health check
- `GET /ready` - Readiness probe
- `GET /metrics` - Prometheus metrics

### Cryptography

- `POST /api/v1/crypto/keygen` - Generate quantum-safe keypair
- `POST /api/v1/crypto/encrypt` - Encrypt data with PQC
- `POST /api/v1/crypto/decrypt` - Decrypt data
- `POST /api/v1/crypto/sign` - Digital signature
- `POST /api/v1/crypto/verify` - Verify signature

### Optimization

- `POST /api/v1/optimize/qaoa` - QAOA optimization
- `POST /api/v1/optimize/vqe` - VQE solver
- `POST /api/v1/optimize/classical` - Classical fallback

## Development

### Running Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src/qsop --cov-report=html

# Run specific test file
pytest tests/test_crypto.py -v
```

### Code Quality

```bash
# Format code
black src tests

# Lint
ruff check src tests

# Type checking
mypy src
```

### Pre-commit Hooks

```bash
pre-commit install
pre-commit run --all-files
```

## Security

### Post-Quantum Algorithms

| Algorithm | Type | Security Level |
|-----------|------|----------------|
| Kyber512 | KEM | NIST Level 1 |
| Kyber768 | KEM | NIST Level 3 |
| Kyber1024 | KEM | NIST Level 5 |
| Dilithium2 | Signature | NIST Level 2 |
| Dilithium3 | Signature | NIST Level 3 |
| Dilithium5 | Signature | NIST Level 5 |

### Security Best Practices

- All secrets are managed via environment variables
- TLS 1.3 required in production
- Rate limiting enabled by default
- Audit logging for all cryptographic operations

## Deployment

### Production Checklist

- [ ] Set `QSOP_ENV=prod`
- [ ] Disable debug mode
- [ ] Configure proper database URL
- [ ] Set up Redis cluster
- [ ] Enable TLS termination
- [ ] Configure log aggregation
- [ ] Set up monitoring dashboards

### Kubernetes

Helm charts are available in the `deploy/helm` directory.

```bash
helm install qsop ./deploy/helm/qsop -f values.prod.yaml
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

# Quantum-Safe Secure Optimization Platform

## Project Overview

This is a production-ready quantum-safe secure optimization platform that integrates post-quantum cryptographic schemes with quantum and classical optimization algorithms.

## Build & Test Commands

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run specific test categories
pytest tests/unit/ -v
pytest tests/integration/ -v

# Type checking
mypy src/

# Linting
ruff check src/
ruff format src/

# Build
python -m build
```

## Project Structure

```
src/qsop/
├── api/                    # FastAPI REST API layer
│   ├── routers/           # API endpoints (jobs, algorithms, keys)
│   ├── middleware/        # Auth, rate limiting, request tracking
│   └── schemas/           # Pydantic request/response models
├── application/           # Business logic and orchestration
│   ├── services/          # Job, workflow, crypto, policy services
│   └── workflows/         # Hybrid loop, QAOA, VQE workflows
├── backends/              # Quantum backend implementations
│   ├── simulators/        # Qiskit Aer, statevector simulator
│   └── providers/         # IBM Quantum, AWS Braket
├── crypto/                # Post-quantum cryptography
│   ├── pqc/              # Kyber, Dilithium, SPHINCS+ implementations
│   ├── symmetric/        # AES-GCM, ChaCha20-Poly1305
│   ├── envelopes/        # Envelope encryption
│   └── signing/          # Digital signatures
├── domain/               # Core domain models
│   ├── models/           # Problem, Job, Result, Artifacts
│   └── ports/            # Interface protocols
├── infrastructure/       # External integrations
│   ├── keystore/         # Vault, local dev keystores
│   ├── artifact_store/   # S3, filesystem storage
│   ├── persistence/      # SQLAlchemy models
│   └── observability/    # Logging, metrics, tracing
├── optimizers/           # Optimization algorithms
│   ├── classical/        # GA, DE, PSO, SA, gradient descent
│   ├── quantum/          # QAOA, VQE, Grover
│   └── hybrid/           # Hybrid quantum-classical optimizers
└── security/             # Security & compliance
    ├── authz.py          # Authorization
    ├── audit.py          # Audit logging
    └── compliance.py     # NIST compliance checking
```

## Key Technologies

- **Post-Quantum Crypto**: Kyber (KEM), Dilithium & SPHINCS+ (signatures) via liboqs
- **Quantum Computing**: Qiskit, Qiskit Aer, IBM Quantum Runtime
- **Web Framework**: FastAPI with async support
- **Observability**: Prometheus metrics, OpenTelemetry tracing, structlog

## Code Conventions

- Use Python 3.11+ features (type hints, dataclasses, protocols)
- Follow domain-driven design with ports/adapters pattern
- All cryptographic operations use post-quantum algorithms by default
- Prefer composition over inheritance
- Use Pydantic for validation, dataclasses for domain models
- All public APIs should have docstrings

## Security Practices

- Never log secrets or private keys
- Use envelope encryption for data at rest
- Sign all job specifications and results
- Validate inputs at API boundaries
- Follow NIST security level 3 minimum by default

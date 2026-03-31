# Deployment Runbook - Quantum-Safe Optimization Platform

## Overview

This runbook provides step-by-step instructions for deploying QSOP to production.

## Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Azure subscription (Cosmos DB, Key Vault)
- Redis server
- SSL certificates

## Pre-Deployment Checklist

- [ ] All environment variables configured
- [ ] SSL certificates installed
- [ ] Redis server running
- [ ] Cosmos DB provisioned
- [ ] Key Vault configured
- [ ] PQC keys generated
- [ ] Admin credentials set (NOT default)

## Environment Variables

### Required Variables

```bash
# Application
APP_ENV=production
LOG_LEVEL=INFO
DEBUG=false

# Database
COSMOS_ENDPOINT=https://your-account.documents.azure.com:443/
COSMOS_DATABASE=quantum_optimization

# Authentication
ADMIN_USERNAME=<secure-admin-username>
ADMIN_PASSWORD=<secure-admin-password>
JWT_SECRET=<256-bit-secret>

# Redis
REDIS_URL=redis://your-redis:6379/0

# Quantum Backends
IBM_QUANTUM_TOKEN=<your-token>
```

### Security Variables

```bash
# Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# CORS
CORS_ORIGINS=https://your-domain.com

# Webhooks
WEBHOOK_SECRET=<secure-secret>
WEBHOOK_REQUIRE_HTTPS=true
```

## Deployment Steps

### 1. Build Docker Image

```bash
docker build -t qsop:latest .
```

### 2. Run Database Migrations

```bash
alembic upgrade head
```

### 3. Generate PQC Keys

```bash
python -c "
from quantum_safe_crypto import KemKeyPair, SigningKeyPair
kem = KemKeyPair(security_level=3)
sig = SigningKeyPair(security_level=3)
print('KEM Public Key:', kem.public_key)
print('SIG Public Key:', sig.public_key)
"
```

Store keys in Azure Key Vault.

### 4. Start Services

```bash
docker-compose up -d
```

### 5. Verify Deployment

```bash
# Health check
curl https://your-domain.com/health

# Crypto status
curl https://your-domain.com/health/crypto

# API docs
curl https://your-domain.com/docs
```

## Rollback Procedure

### Quick Rollback

```bash
# Stop current deployment
docker-compose down

# Restore previous image
docker tag qsop:previous qsop:latest

# Restart services
docker-compose up -d
```

### Database Rollback

```bash
# Rollback to previous migration
alembic downgrade -1
```

## Monitoring

### Health Endpoints

| Endpoint         | Purpose                |
| ---------------- | ---------------------- |
| `/health`        | Basic health check     |
| `/health/crypto` | Crypto provider status |
| `/ready`         | Readiness probe        |

### Key Metrics

- Request latency (p50, p95, p99)
- Error rate (4xx, 5xx)
- Job queue depth
- Crypto operations/sec

### Alerts

- 5xx error rate > 1%
- P99 latency > 2s
- Job queue > 100 pending
- Crypto operations failing

## Troubleshooting

### Common Issues

#### 1. Crypto Not Available

```
Error: liboqs not available
```

Solution: Install liboqs library or use Python fallback (not recommended for production).

#### 2. Database Connection Failed

```
Error: Cannot connect to Cosmos DB
```

Solution: Check COSMOS_ENDPOINT, firewall rules, and managed identity.

#### 3. Rate Limiting Not Working

```
Warning: Using memory storage for rate limiting
```

Solution: Ensure REDIS_URL is set and Redis is running.

## Security Checklist

- [ ] No hardcoded secrets in code
- [ ] All secrets in Key Vault
- [ ] HTTPS enforced
- [ ] CORS configured correctly
- [ ] Rate limiting enabled
- [ ] Audit logging enabled
- [ ] PQC keys rotated quarterly

## Contacts

- On-call: security@your-domain.com
- Escalation: ops-lead@your-domain.com

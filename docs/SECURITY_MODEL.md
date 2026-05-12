# Security Model

## Overview

The Quantum-Safe Secure Optimization Platform implements defense-in-depth security with Post-Quantum Cryptography (PQC) at every layer.

## Threat Model

### Assets Protected
- User credentials and authentication tokens
- Quantum optimization job data and results
- PQC cryptographic keys
- Audit logs and compliance data

### Threat Actors
- External attackers (network-level, application-level)
- Malicious users (privilege escalation, data exfiltration)
- Quantum computers (future threat to classical crypto)

## Security Layers

### 1. Network Layer
- **Hybrid TLS**: X25519 + ML-KEM key exchange
- **HSTS**: Strict transport security with preload
- **CSP**: Content Security Policy for API and frontend

### 2. Authentication Layer
- **ML-DSA-65 Signed JWTs**: Post-quantum digital signatures on all auth tokens
- **Argon2id Password Hashing**: Memory-hard password hashing
- **Token Revocation**: Immediate token invalidation on logout/security events
- **MFA Support**: Extensible multi-factor authentication framework

### 3. Authorization Layer
- **Role-Based Access Control**: user, premium, admin roles
- **Resource Quotas**: Per-user limits on jobs, storage, priority
- **Tenant Isolation**: Database partitioning by user_id

### 4. Application Layer
- **Input Validation**: Pydantic models with strict type checking
- **Rate Limiting**: Redis-backed rate limits (5/min login, 10/min job submit)
- **CSRF Protection**: Signed tokens for session-based auth
- **SSRF Protection**: Webhook URL validation
- **Request Signing**: Optional ML-DSA request payload signatures

### 5. Data Layer
- **ML-KEM-768 Encryption**: Hybrid encryption for job results
- **AES-256-GCM**: Symmetric encryption with PQC key wrapping
- **Encrypted Storage**: Sensitive data encrypted at rest
- **Key Rotation**: Automated PQC key rotation (90-day cycle)

### 6. Audit Layer
- **Audit Logging**: All authenticated requests logged
- **Event Sourcing**: Immutable audit trail
- **Audit Integrity**: Cryptographic hash chaining

## PQC Implementation

| Component | Algorithm | Standard | Purpose |
|-----------|-----------|----------|---------|
| Key Encapsulation | ML-KEM-768 | NIST FIPS 203 | Data encryption |
| Digital Signatures | ML-DSA-65 | NIST FIPS 204 | Token/request signing |
| Hybrid TLS | X25519 + ML-KEM | RFC draft | Transport security |

## Security Controls

### Production Requirements
- All secrets via environment variables (no hardcoded defaults)
- JWT_SECRET, CSRF_SECRET, COSMOS_KEY required
- Demo mode blocked
- Celery workers enabled
- Debug mode disabled
- Real liboqs crypto required (stubs rejected)

### Rate Limits
| Endpoint | Limit | Purpose |
|----------|-------|---------|
| Login | 5/minute | Brute force prevention |
| Register | 3/minute | Account spam prevention |
| Job Submit | 10/minute | Resource protection |
| Key Generation | 5/minute | CPU cost protection |
| General Read | 100/minute | API abuse prevention |

## Incident Response

1. **Token Compromise**: Revoke all user tokens via `/auth/revoke-all-tokens`
2. **Key Compromise**: Trigger immediate key rotation
3. **Breach Detection**: Review audit logs, check anomaly detection alerts

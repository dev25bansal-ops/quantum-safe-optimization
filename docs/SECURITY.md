# Security Documentation - Quantum-Safe Optimization Platform

## Overview

QSOP implements NIST-standardized post-quantum cryptography (PQC) for security against quantum computer attacks.

## Cryptographic Algorithms

### ML-KEM (Kyber) - Key Encapsulation

| Security Level | Algorithm   | Key Size   | Use Case           |
| -------------- | ----------- | ---------- | ------------------ |
| 1              | ML-KEM-512  | 800 bytes  | Low-security, fast |
| 3              | ML-KEM-768  | 1184 bytes | **Recommended**    |
| 5              | ML-KEM-1024 | 1568 bytes | Maximum security   |

**Usage**: Encrypting symmetric keys, establishing secure channels

### ML-DSA (Dilithium) - Digital Signatures

| Security Level | Algorithm | Signature Size | Use Case                 |
| -------------- | --------- | -------------- | ------------------------ |
| 2              | ML-DSA-44 | 2420 bytes     | Constrained environments |
| 3              | ML-DSA-65 | 3293 bytes     | **Recommended**          |
| 5              | ML-DSA-87 | 4595 bytes     | Maximum security         |

**Usage**: JWT tokens, API request signing, result verification

## Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Application                       │
│                  (ML-KEM public key registered)             │
└─────────────────────────────┬───────────────────────────────┘
                              │ HTTPS + PQC
┌─────────────────────────────▼───────────────────────────────┐
│                      API Gateway                             │
│  • ML-DSA token verification                                 │
│  • Rate limiting (Redis-backed)                              │
│  • Request validation                                        │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                    Application Layer                         │
│  • Job processing with encrypted results                     │
│  • PQC key management                                        │
│  • Audit logging                                             │
└─────────────────────────────────────────────────────────────┘
```

## Authentication Flow

### 1. User Registration

```
Client                          Server
  │                               │
  │── Register (username, password, KEM public key)
  │                               │
  │                         Store user
  │                         Store KEM key
  │                               │
  │◄── Success (user_id)         │
```

### 2. Login

```
Client                          Server
  │                               │
  │── Login (username, password)  │
  │                               │
  │                         Verify password (Argon2id)
  │                         Generate JWT
  │                         Sign JWT with ML-DSA-65
  │                               │
  │◄── Token + PQC signature      │
```

### 3. API Request

```
Client                          Server
  │                               │
  │── Request + Bearer token      │
  │                               │
  │                         Verify ML-DSA signature
  │                         Validate token claims
  │                         Check token revocation
  │                               │
  │◄── Response (encrypted)       │
```

## Key Management

### Key Generation

```python
from quantum_safe_crypto import KemKeyPair, SigningKeyPair

# Generate KEM key pair (Level 3 - Recommended)
kem = KemKeyPair(security_level=3)

# Generate signing key pair (Level 3 - Recommended)
sig = SigningKeyPair(security_level=3)
```

### Key Storage

- **Public keys**: Stored in database, sent to clients
- **Secret keys**: Encrypted with envelope encryption, stored in Key Vault
- **Key rotation**: Every 90 days recommended

### Envelope Encryption

```
1. Generate data encryption key (DEK)
2. Encrypt data with DEK using AES-256-GCM
3. Encrypt DEK with recipient's ML-KEM public key
4. Store ciphertext + encrypted DEK + nonce
```

## Security Headers

All API responses include:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Content-Security-Policy: default-src 'self'
X-XSS-Protection: 1; mode=block
```

## Rate Limiting

| Endpoint Type  | Limit | Window |
| -------------- | ----- | ------ |
| Login          | 5     | minute |
| Register       | 3     | minute |
| Key generation | 5     | minute |
| Job submit     | 10    | minute |
| General API    | 100   | minute |

Production uses Redis backend for distributed rate limiting.

## Audit Logging

All security-relevant events are logged:

- User registration/login/logout
- Key generation/rotation
- Job submission/completion
- Permission changes
- Failed authentication attempts

Logs include: timestamp, user_id, action, IP, user_agent

## Security Best Practices

### For Developers

1. **Never log secrets** - Passwords, tokens, private keys
2. **Use environment variables** - Not hardcoded secrets
3. **Validate all inputs** - Use Pydantic models
4. **Check permissions** - Before any operation
5. **Encrypt sensitive data** - Use envelope encryption
6. **Sign results** - Use ML-DSA signatures

### For Operations

1. **Enable HTTPS** - Required for production
2. **Configure CORS** - Whitelist specific origins
3. **Use Redis** - For rate limiting, not memory
4. **Monitor logs** - Set up alerts for failures
5. **Rotate keys** - Quarterly at minimum
6. **Backup keys** - Secure offline storage

## Compliance

- **NIST FIPS 203**: ML-KEM (Kyber)
- **NIST FIPS 204**: ML-DSA (Dilithium)
- **NIST SP 800-57**: Security levels 1, 3, 5

## Incident Response

### Key Compromise

1. Revoke compromised key immediately
2. Generate new key pair
3. Rotate all encrypted data
4. Audit access logs
5. Notify affected users

### Token Compromise

1. Add token to revocation list
2. Force user re-authentication
3. Audit token usage
4. Review authentication logs

## Security Contacts

- Security team: security@your-domain.com
- Bug bounty: https://your-domain.com/security
- PGP key: https://your-domain.com/security.pub

# ADR-0001: Use ML-KEM-768 and ML-DSA-65 as Primary Post-Quantum Algorithms

## Status

Accepted

## Context

With the NIST Post-Quantum Cryptography standardization complete, we need to select quantum-resistant cryptographic algorithms for our platform. The selection must balance:

- Security level (NIST Level 3)
- Performance characteristics
- Key/ciphertext sizes
- Implementation maturity

## Decision

We will use:

- **ML-KEM-768** (Kyber) for key encapsulation
- **ML-DSA-65** (Dilithium) for digital signatures

Both are NIST-approved (FIPS 203/204) at security level 3.

## Consequences

### Positive

- Strong quantum resistance
- Well-analyzed and standardized
- Reasonable key sizes (ML-KEM-768: 1184 bytes public key)
- Multiple implementations available (liboqs, CRYSTALS implementations)

### Negative

- Larger keys than classical algorithms (RSA-2048: 256 bytes)
- Computational overhead compared to classical algorithms
- Some integration complexity with existing PKI

### Mitigations

- Use hybrid encryption (ML-KEM + ECDH) during transition period
- Cache key pairs to reduce generation overhead
- Implement compression for storage and transmission

## Alternatives Considered

| Algorithm        | Pros                | Cons                   | Decision               |
| ---------------- | ------------------- | ---------------------- | ---------------------- |
| ML-KEM-1024      | Higher security     | Larger keys, slower    | Rejected (overkill)    |
| Classic McEliece | Conservative        | Very large keys        | Rejected (impractical) |
| Falcon           | Smaller signatures  | Complex implementation | Future consideration   |
| SPHINCS+         | Hash-based security | Large signatures       | Backup option          |

## Implementation

```python
# Key generation example
from quantum_safe_crypto import KemKeyPair, SecurityLevel

keypair = KemKeyPair.generate(SecurityLevel.LEVEL_3)  # ML-KEM-768
```

## References

- [NIST FIPS 203](https://csrc.nist.gov/pubs/fips/203/final)
- [NIST FIPS 204](https://csrc.nist.gov/pubs/fips/204/final)
- [liboqs Documentation](https://openquantumsafe.org/liboqs/)

## Date

2024-01-15

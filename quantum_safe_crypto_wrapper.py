"""
Quantum-Safe Cryptography - Production Wrapper.

This module provides a unified interface that uses the Rust PQC module when available,
with a Python fallback for development environments.

Production Usage:
    - Install liboqs: https://github.com/open-quantum-safe/liboqs
    - Install wheel: pip install quantum_safe_crypto-*.whl

The Rust module provides REAL NIST FIPS 203/204 algorithms.
"""

import warnings

try:
    # Try to import the Rust module first
    from quantum_safe_crypto import (
        KemKeyPair,
        SigningKeyPair,
        SecurityLevel,
        EncryptedEnvelope,
        py_kem_generate,
        py_kem_generate_with_level,
        py_kem_encapsulate,
        py_kem_encapsulate_with_level,
        py_kem_decapsulate,
        py_kem_decapsulate_with_level,
        py_sign,
        py_sign_with_level,
        py_verify,
        py_verify_with_level,
        py_encrypt,
        py_decrypt,
        py_get_supported_levels,
    )

    LIBOQS_AVAILABLE = True

except ImportError:
    # Fall back to Python implementation
    from quantum_safe_crypto_fallback import (
        KemKeyPair,
        SigningKeyPair,
        SecurityLevel,
        EncryptedEnvelope,
        py_kem_generate,
        py_kem_generate_with_level,
        py_kem_encapsulate,
        py_kem_encapsulate_with_level,
        py_kem_decapsulate,
        py_kem_decapsulate_with_level,
        py_sign,
        py_sign_with_level,
        py_verify,
        py_verify_with_level,
        py_encrypt,
        py_decrypt,
        py_get_supported_levels,
    )

    LIBOQS_AVAILABLE = False

    warnings.warn(
        "liboqs not available. Using STUB implementation for development. "
        "Install liboqs-python with liboqs for production. "
        "See: https://github.com/open-quantum-safe/liboqs-python"
    )


def is_crypto_production_ready() -> bool:
    """Check if real PQC algorithms are available."""
    return LIBOQS_AVAILABLE


def get_crypto_status() -> dict:
    """Get current crypto implementation status."""
    return {
        "liboqs_available": LIBOQS_AVAILABLE,
        "implementation": "liboqs" if LIBOQS_AVAILABLE else "STUB",
        "security_warning": None
        if LIBOQS_AVAILABLE
        else "STUB IMPLEMENTATION - NOT FOR PRODUCTION",
    }


__all__ = [
    "KemKeyPair",
    "SigningKeyPair",
    "SecurityLevel",
    "EncryptedEnvelope",
    "py_kem_generate",
    "py_kem_generate_with_level",
    "py_kem_encapsulate",
    "py_kem_encapsulate_with_level",
    "py_kem_decapsulate",
    "py_kem_decapsulate_with_level",
    "py_sign",
    "py_sign_with_level",
    "py_verify",
    "py_verify_with_level",
    "py_encrypt",
    "py_decrypt",
    "py_get_supported_levels",
    "is_crypto_production_ready",
    "get_crypto_status",
    "LIBOQS_AVAILABLE",
]

"""Fallback provider for post-quantum cryptography.

SECURITY WARNING: This provider uses mock implementations and is NOT secure.
It exists ONLY for testing when liboqs is unavailable.
NEVER use in production.
"""

import hashlib
import hmac
import logging
import os
import warnings
from typing import TYPE_CHECKING

from qsop.crypto.pqc.algorithms import (
    KEMAlgorithm,
    SignatureAlgorithm,
    get_kem_parameters,
    get_signature_parameters,
)

if TYPE_CHECKING:
    from qsop.crypto.pqc import KEMKeyPair, SignatureKeyPair

logger = logging.getLogger(__name__)

_FALLBACK_WARNING = (
    "SECURITY WARNING: Using fallback PQC provider with MOCK implementations. "
    "This is NOT cryptographically secure and should ONLY be used for testing. "
    "Install liboqs-python for production use."
)


class FallbackKEMProvider:
    """Fallback KEM provider with mock implementations.

    SECURITY WARNING: NOT SECURE - FOR TESTING ONLY.
    """

    def __init__(self):
        warnings.warn(_FALLBACK_WARNING, SecurityWarning, stacklevel=2)
        logger.warning(_FALLBACK_WARNING)
        self._warned = True

    def generate_keypair(self, algorithm: KEMAlgorithm) -> "KEMKeyPair":
        """Generate a mock KEM key pair."""
        from qsop.crypto.pqc import KEMKeyPair

        params = get_kem_parameters(algorithm)
        seed = os.urandom(32)
        public_key = self._derive_bytes(seed, b"public_key", params.public_key_size)
        pk_hash = hashlib.sha256(public_key).digest()
        secret_key = seed + pk_hash + os.urandom(params.secret_key_size - 32 - 32)

        return KEMKeyPair(
            public_key=public_key,
            secret_key=secret_key[: params.secret_key_size],
            algorithm=algorithm,
        )

    def encapsulate(self, public_key: bytes, algorithm: KEMAlgorithm) -> tuple[bytes, bytes]:
        """Mock encapsulation."""
        params = get_kem_parameters(algorithm)

        if not isinstance(public_key, bytes):
            raise TypeError("public_key must be bytes")
        if len(public_key) != params.public_key_size:
            raise ValueError(
                f"Invalid public key size: expected {params.public_key_size}, got {len(public_key)}"
            )

        shared_secret = os.urandom(params.shared_secret_size)
        ct_seed = hashlib.sha256(public_key + shared_secret).digest()
        ciphertext = self._derive_bytes(ct_seed, b"ciphertext", params.ciphertext_size - 32)
        ciphertext = shared_secret + ciphertext

        return ciphertext[: params.ciphertext_size], shared_secret

    def decapsulate(self, secret_key: bytes, ciphertext: bytes, algorithm: KEMAlgorithm) -> bytes:
        """Mock decapsulation."""
        params = get_kem_parameters(algorithm)

        if not isinstance(secret_key, bytes):
            raise TypeError("secret_key must be bytes")
        if not isinstance(ciphertext, bytes):
            raise TypeError("ciphertext must be bytes")
        if len(secret_key) != params.secret_key_size:
            raise ValueError(
                f"Invalid secret key size: expected {params.secret_key_size}, got {len(secret_key)}"
            )
        if len(ciphertext) != params.ciphertext_size:
            raise ValueError(
                f"Invalid ciphertext size: expected {params.ciphertext_size}, got {len(ciphertext)}"
            )

        shared_secret = ciphertext[: params.shared_secret_size]
        return shared_secret

    def _derive_bytes(self, seed: bytes, context: bytes, length: int) -> bytes:
        """Derive deterministic bytes from seed."""
        result = b""
        counter = 0
        while len(result) < length:
            h = hashlib.sha256(seed + context + counter.to_bytes(4, "big"))
            result += h.digest()
            counter += 1
        return result[:length]

    @property
    def is_production_ready(self) -> bool:
        """This provider is NOT production-ready."""
        return False


class FallbackSignatureProvider:
    """Fallback signature provider with mock implementations.

    SECURITY WARNING: NOT SECURE - FOR TESTING ONLY.
    """

    def __init__(self):
        warnings.warn(_FALLBACK_WARNING, SecurityWarning, stacklevel=2)
        logger.warning(_FALLBACK_WARNING)
        self._warned = True

    def generate_keypair(self, algorithm: SignatureAlgorithm) -> "SignatureKeyPair":
        """Generate a mock signature key pair."""
        from qsop.crypto.pqc import SignatureKeyPair

        params = get_signature_parameters(algorithm)
        seed = os.urandom(32)
        public_key = self._derive_bytes(seed, b"public_key", params.public_key_size)
        secret_key = seed + self._derive_bytes(seed, b"secret_key", params.secret_key_size - 32)

        return SignatureKeyPair(
            public_key=public_key,
            secret_key=secret_key[: params.secret_key_size],
            algorithm=algorithm,
        )

    def sign(self, secret_key: bytes, message: bytes, algorithm: SignatureAlgorithm) -> bytes:
        """Mock signing. Embeds message and public key hashes for verification."""
        params = get_signature_parameters(algorithm)

        if not isinstance(secret_key, bytes):
            raise TypeError("secret_key must be bytes")
        if not isinstance(message, bytes):
            raise TypeError("message must be bytes")
        if len(secret_key) != params.secret_key_size:
            raise ValueError(
                f"Invalid secret key size: expected {params.secret_key_size}, got {len(secret_key)}"
            )
        if len(message) == 0:
            raise ValueError("Message cannot be empty")

        seed = secret_key[:32]
        public_key = self._derive_bytes(seed, b"public_key", params.public_key_size)
        msg_hash = hashlib.sha256(message).digest()
        pk_hash = hashlib.sha256(public_key).digest()

        if algorithm.oqs_name.startswith("SPHINCS"):
            sig_core = hmac.new(seed, message, hashlib.sha256).digest()
            signature = msg_hash + pk_hash + sig_core + os.urandom(params.signature_size - 96)
        else:
            sig_core = hmac.new(seed, message, hashlib.sha256).digest()
            signature = (
                msg_hash
                + pk_hash
                + self._derive_bytes(sig_core, b"signature", params.signature_size - 64)
            )

        return signature

    def verify(
        self, public_key: bytes, message: bytes, signature: bytes, algorithm: SignatureAlgorithm
    ) -> bool:
        """Mock verification. Checks embedded message and public key hashes."""
        params = get_signature_parameters(algorithm)

        if not isinstance(public_key, bytes):
            raise TypeError("public_key must be bytes")
        if not isinstance(message, bytes):
            raise TypeError("message must be bytes")
        if not isinstance(signature, bytes):
            raise TypeError("signature must be bytes")
        if len(public_key) != params.public_key_size:
            raise ValueError(
                f"Invalid public key size: expected {params.public_key_size}, got {len(public_key)}"
            )
        if len(message) == 0:
            raise ValueError("Message cannot be empty")
        if len(signature) == 0:
            raise ValueError("Signature cannot be empty")

        if len(signature) != params.signature_size:
            return False

        expected_msg_hash = hashlib.sha256(message).digest()
        expected_pk_hash = hashlib.sha256(public_key).digest()
        sig_msg_hash = signature[:32]
        sig_pk_hash = signature[32:64]

        return expected_msg_hash == sig_msg_hash and expected_pk_hash == sig_pk_hash

    def _derive_bytes(self, seed: bytes, context: bytes, length: int) -> bytes:
        """Derive deterministic bytes from seed."""
        result = b""
        counter = 0
        while len(result) < length:
            h = hashlib.sha256(seed + context + counter.to_bytes(4, "big"))
            result += h.digest()
            counter += 1
        return result[:length]

    @property
    def is_production_ready(self) -> bool:
        """This provider is NOT production-ready."""
        return False


class SecurityWarning(UserWarning):
    """Warning for security-related issues."""

    pass


__all__ = [
    "FallbackKEMProvider",
    "FallbackSignatureProvider",
    "SecurityWarning",
]

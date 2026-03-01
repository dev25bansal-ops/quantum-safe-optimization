"""
OQS (Open Quantum Safe) provider for post-quantum cryptography.

Uses liboqs-python for production-ready PQC implementations.
"""

import logging
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

_oqs_available: bool | None = None
_oqs_module = None


def is_oqs_available() -> bool:
    """Check if liboqs-python is available."""
    global _oqs_available, _oqs_module

    if _oqs_available is not None:
        return _oqs_available

    try:
        import oqs

        _oqs_module = oqs
        _oqs_available = True
        logger.info("liboqs-python is available")
    except (ImportError, SystemExit, RuntimeError, Exception) as e:
        _oqs_available = False
        logger.warning(f"liboqs-python is not available or failed to initialize: {e}")

    return _oqs_available


def _get_oqs():
    """Get the oqs module, raising if unavailable."""
    if not is_oqs_available():
        raise RuntimeError(
            "liboqs-python is not installed. Install with: pip install liboqs-python"
        )
    return _oqs_module


class OQSKEMProvider:
    """KEM provider using liboqs."""

    def __init__(self):
        self._oqs = _get_oqs()
        self._validate_algorithms()

    def _validate_algorithms(self) -> None:
        """Validate that required algorithms are available."""
        enabled_kems = self._oqs.get_enabled_kem_mechanisms()
        for algo in KEMAlgorithm:
            if algo.oqs_name not in enabled_kems:
                logger.warning(f"KEM algorithm {algo.oqs_name} not available in liboqs")

    def generate_keypair(self, algorithm: KEMAlgorithm) -> "KEMKeyPair":
        """Generate a new KEM key pair."""
        from qsop.crypto.pqc import KEMKeyPair

        params = get_kem_parameters(algorithm)

        try:
            kem = self._oqs.KeyEncapsulation(algorithm.oqs_name)
            public_key = kem.generate_keypair()
            secret_key = kem.export_secret_key()

            if len(public_key) != params.public_key_size:
                raise ValueError(
                    f"Public key size mismatch: expected {params.public_key_size}, "
                    f"got {len(public_key)}"
                )
            if len(secret_key) != params.secret_key_size:
                raise ValueError(
                    f"Secret key size mismatch: expected {params.secret_key_size}, "
                    f"got {len(secret_key)}"
                )

            return KEMKeyPair(
                public_key=bytes(public_key),
                secret_key=bytes(secret_key),
                algorithm=algorithm,
            )
        except Exception as e:
            if "not enabled" in str(e).lower() or "not supported" in str(e).lower():
                raise RuntimeError(
                    f"KEM algorithm {algorithm.oqs_name} is not enabled in liboqs. "
                    "Rebuild liboqs with this algorithm enabled."
                ) from e
            raise

    def encapsulate(self, public_key: bytes, algorithm: KEMAlgorithm) -> tuple[bytes, bytes]:
        """
        Encapsulate a shared secret.

        Args:
            public_key: Recipient's public key.
            algorithm: KEM algorithm to use.

        Returns:
            Tuple of (ciphertext, shared_secret).
        """
        params = get_kem_parameters(algorithm)

        if not isinstance(public_key, bytes):
            raise TypeError("public_key must be bytes")
        if len(public_key) != params.public_key_size:
            raise ValueError(
                f"Invalid public key size: expected {params.public_key_size}, got {len(public_key)}"
            )

        try:
            kem = self._oqs.KeyEncapsulation(algorithm.oqs_name)
            ciphertext, shared_secret = kem.encap_secret(public_key)

            if len(ciphertext) != params.ciphertext_size:
                raise ValueError(
                    f"Ciphertext size mismatch: expected {params.ciphertext_size}, "
                    f"got {len(ciphertext)}"
                )
            if len(shared_secret) != params.shared_secret_size:
                raise ValueError(
                    f"Shared secret size mismatch: expected {params.shared_secret_size}, "
                    f"got {len(shared_secret)}"
                )

            return bytes(ciphertext), bytes(shared_secret)
        except Exception as e:
            if "invalid" in str(e).lower():
                raise ValueError(f"Invalid public key for {algorithm.oqs_name}") from e
            raise

    def decapsulate(self, secret_key: bytes, ciphertext: bytes, algorithm: KEMAlgorithm) -> bytes:
        """
        Decapsulate to recover the shared secret.

        Args:
            secret_key: Recipient's secret key.
            ciphertext: Encapsulated ciphertext.
            algorithm: KEM algorithm used.

        Returns:
            The shared secret.
        """
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

        try:
            kem = self._oqs.KeyEncapsulation(algorithm.oqs_name, secret_key)
            shared_secret = kem.decap_secret(ciphertext)

            if len(shared_secret) != params.shared_secret_size:
                raise ValueError(
                    f"Shared secret size mismatch: expected {params.shared_secret_size}, "
                    f"got {len(shared_secret)}"
                )

            return bytes(shared_secret)
        except Exception as e:
            if "decapsulation" in str(e).lower() or "invalid" in str(e).lower():
                raise ValueError("Decapsulation failed - invalid ciphertext or key") from e
            raise

    @property
    def is_production_ready(self) -> bool:
        """This provider is production-ready."""
        return True


class OQSSignatureProvider:
    """Signature provider using liboqs."""

    def __init__(self):
        self._oqs = _get_oqs()
        self._validate_algorithms()

    def _validate_algorithms(self) -> None:
        """Validate that required algorithms are available."""
        enabled_sigs = self._oqs.get_enabled_sig_mechanisms()
        for algo in SignatureAlgorithm:
            if algo.oqs_name not in enabled_sigs:
                logger.warning(f"Signature algorithm {algo.oqs_name} not available in liboqs")

    def generate_keypair(self, algorithm: SignatureAlgorithm) -> "SignatureKeyPair":
        """Generate a new signature key pair."""
        from qsop.crypto.pqc import SignatureKeyPair

        params = get_signature_parameters(algorithm)

        try:
            sig = self._oqs.Signature(algorithm.oqs_name)
            public_key = sig.generate_keypair()
            secret_key = sig.export_secret_key()

            if len(public_key) != params.public_key_size:
                raise ValueError(
                    f"Public key size mismatch: expected {params.public_key_size}, "
                    f"got {len(public_key)}"
                )
            if len(secret_key) != params.secret_key_size:
                raise ValueError(
                    f"Secret key size mismatch: expected {params.secret_key_size}, "
                    f"got {len(secret_key)}"
                )

            return SignatureKeyPair(
                public_key=bytes(public_key),
                secret_key=bytes(secret_key),
                algorithm=algorithm,
            )
        except Exception as e:
            if "not enabled" in str(e).lower() or "not supported" in str(e).lower():
                raise RuntimeError(
                    f"Signature algorithm {algorithm.oqs_name} is not enabled in liboqs. "
                    "Rebuild liboqs with this algorithm enabled."
                ) from e
            raise

    def sign(self, secret_key: bytes, message: bytes, algorithm: SignatureAlgorithm) -> bytes:
        """
        Sign a message.

        Args:
            secret_key: Signer's secret key.
            message: Message to sign.
            algorithm: Signature algorithm to use.

        Returns:
            The signature.
        """
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

        try:
            sig = self._oqs.Signature(algorithm.oqs_name, secret_key)
            signature = sig.sign(message)

            # SPHINCS+ has variable signature sizes, others are fixed
            max_sig_size = params.signature_size
            if len(signature) > max_sig_size:
                raise ValueError(
                    f"Signature too large: expected <= {max_sig_size}, got {len(signature)}"
                )

            return bytes(signature)
        except Exception as e:
            if "sign" in str(e).lower() and "fail" in str(e).lower():
                raise ValueError("Signing failed - invalid secret key") from e
            raise

    def verify(
        self,
        public_key: bytes,
        message: bytes,
        signature: bytes,
        algorithm: SignatureAlgorithm,
    ) -> bool:
        """
        Verify a signature.

        Args:
            public_key: Signer's public key.
            message: Original message.
            signature: Signature to verify.
            algorithm: Signature algorithm used.

        Returns:
            True if the signature is valid, False otherwise.
        """
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

        try:
            sig = self._oqs.Signature(algorithm.oqs_name)
            return sig.verify(message, signature, public_key)
        except Exception:
            # Verification failures return False, not exceptions
            return False

    @property
    def is_production_ready(self) -> bool:
        """This provider is production-ready."""
        return True


__all__ = [
    "is_oqs_available",
    "OQSKEMProvider",
    "OQSSignatureProvider",
]

"""
Post-Quantum Cryptography providers.

Supports KEM (Key Encapsulation Mechanism) and digital signatures
using liboqs when available, with fail-closed fallback.
"""

from qsop.crypto.pqc.algorithms import (
    KEMAlgorithm,
    SignatureAlgorithm,
    KEM_PARAMETERS,
    SIGNATURE_PARAMETERS,
    get_kem_parameters,
    get_signature_parameters,
)
from qsop.crypto.pqc.oqs_provider import (
    OQSKEMProvider,
    OQSSignatureProvider,
    is_oqs_available,
)
from qsop.crypto.pqc.fallback_provider import (
    FallbackKEMProvider,
    FallbackSignatureProvider,
)

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple, Optional


@dataclass(frozen=True)
class KEMKeyPair:
    """KEM key pair."""
    public_key: bytes
    secret_key: bytes
    algorithm: KEMAlgorithm


@dataclass(frozen=True)
class SignatureKeyPair:
    """Signature key pair."""
    public_key: bytes
    secret_key: bytes
    algorithm: SignatureAlgorithm


class KEMProvider(ABC):
    """Abstract KEM provider interface."""
    
    @abstractmethod
    def generate_keypair(self, algorithm: KEMAlgorithm) -> KEMKeyPair:
        """Generate a new KEM key pair."""
        pass
    
    @abstractmethod
    def encapsulate(self, public_key: bytes, algorithm: KEMAlgorithm) -> Tuple[bytes, bytes]:
        """Encapsulate a shared secret. Returns (ciphertext, shared_secret)."""
        pass
    
    @abstractmethod
    def decapsulate(self, secret_key: bytes, ciphertext: bytes, algorithm: KEMAlgorithm) -> bytes:
        """Decapsulate to recover the shared secret."""
        pass
    
    @property
    @abstractmethod
    def is_production_ready(self) -> bool:
        """Whether this provider is safe for production use."""
        pass


class SignatureProvider(ABC):
    """Abstract signature provider interface."""
    
    @abstractmethod
    def generate_keypair(self, algorithm: SignatureAlgorithm) -> SignatureKeyPair:
        """Generate a new signature key pair."""
        pass
    
    @abstractmethod
    def sign(self, secret_key: bytes, message: bytes, algorithm: SignatureAlgorithm) -> bytes:
        """Sign a message."""
        pass
    
    @abstractmethod
    def verify(self, public_key: bytes, message: bytes, signature: bytes, algorithm: SignatureAlgorithm) -> bool:
        """Verify a signature. Returns True if valid."""
        pass
    
    @property
    @abstractmethod
    def is_production_ready(self) -> bool:
        """Whether this provider is safe for production use."""
        pass


_kem_provider: Optional[KEMProvider] = None
_signature_provider: Optional[SignatureProvider] = None


def get_kem_provider(allow_fallback: bool = False) -> KEMProvider:
    """
    Get the KEM provider.
    
    Args:
        allow_fallback: If True, allow fallback provider for testing.
                       NEVER use in production.
    
    Returns:
        KEMProvider instance.
    
    Raises:
        RuntimeError: If liboqs unavailable and fallback not allowed.
    """
    global _kem_provider
    
    if _kem_provider is not None:
        if not allow_fallback and not _kem_provider.is_production_ready:
            raise RuntimeError(
                "Cached provider is not production-ready. "
                "Install liboqs or explicitly allow fallback for testing."
            )
        return _kem_provider
    
    if is_oqs_available():
        _kem_provider = OQSKEMProvider()
    elif allow_fallback:
        _kem_provider = FallbackKEMProvider()
    else:
        raise RuntimeError(
            "liboqs is not available. Install liboqs-python for production use. "
            "Set allow_fallback=True only for testing."
        )
    
    return _kem_provider


def get_signature_provider(allow_fallback: bool = False) -> SignatureProvider:
    """
    Get the signature provider.
    
    Args:
        allow_fallback: If True, allow fallback provider for testing.
                       NEVER use in production.
    
    Returns:
        SignatureProvider instance.
    
    Raises:
        RuntimeError: If liboqs unavailable and fallback not allowed.
    """
    global _signature_provider
    
    if _signature_provider is not None:
        if not allow_fallback and not _signature_provider.is_production_ready:
            raise RuntimeError(
                "Cached provider is not production-ready. "
                "Install liboqs or explicitly allow fallback for testing."
            )
        return _signature_provider
    
    if is_oqs_available():
        _signature_provider = OQSSignatureProvider()
    elif allow_fallback:
        _signature_provider = FallbackSignatureProvider()
    else:
        raise RuntimeError(
            "liboqs is not available. Install liboqs-python for production use. "
            "Set allow_fallback=True only for testing."
        )
    
    return _signature_provider


def reset_providers() -> None:
    """Reset cached providers. For testing only."""
    global _kem_provider, _signature_provider
    _kem_provider = None
    _signature_provider = None


class KEMInstance:
    """KEM instance bound to a specific algorithm."""
    
    def __init__(self, algorithm: KEMAlgorithm):
        self.algorithm = algorithm
        self._provider = get_kem_provider(allow_fallback=True)
    
    def keygen(self) -> Tuple[bytes, bytes]:
        """Generate keypair. Returns (public_key, private_key)."""
        keypair = self._provider.generate_keypair(self.algorithm)
        return keypair.public_key, keypair.secret_key
    
    def encapsulate(self, public_key: bytes) -> Tuple[bytes, bytes]:
        """Encapsulate. Returns (ciphertext, shared_secret)."""
        return self._provider.encapsulate(public_key, self.algorithm)
    
    def decapsulate(self, ciphertext: bytes, secret_key: bytes) -> bytes:
        """Decapsulate to recover shared secret."""
        return self._provider.decapsulate(secret_key, ciphertext, self.algorithm)


class SignatureInstance:
    """Signature scheme instance bound to a specific algorithm."""
    
    def __init__(self, algorithm: SignatureAlgorithm):
        self.algorithm = algorithm
        self._provider = get_signature_provider(allow_fallback=True)
    
    def keygen(self) -> Tuple[bytes, bytes]:
        """Generate keypair. Returns (public_key, private_key)."""
        keypair = self._provider.generate_keypair(self.algorithm)
        return keypair.public_key, keypair.secret_key
    
    def sign(self, message: bytes, secret_key: bytes) -> bytes:
        """Sign a message."""
        return self._provider.sign(secret_key, message, self.algorithm)
    
    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """Verify a signature."""
        return self._provider.verify(public_key, message, signature, self.algorithm)


def get_kem(algorithm: KEMAlgorithm) -> KEMInstance:
    """Get a KEM instance for the given algorithm."""
    return KEMInstance(algorithm)


def get_signature_scheme(algorithm: SignatureAlgorithm) -> SignatureInstance:
    """Get a signature scheme instance for the given algorithm."""
    return SignatureInstance(algorithm)


__all__ = [
    "KEMAlgorithm",
    "SignatureAlgorithm",
    "KEM_PARAMETERS",
    "SIGNATURE_PARAMETERS",
    "get_kem_parameters",
    "get_signature_parameters",
    "KEMKeyPair",
    "SignatureKeyPair",
    "KEMProvider",
    "SignatureProvider",
    "get_kem_provider",
    "get_signature_provider",
    "get_kem",
    "get_signature_scheme",
    "reset_providers",
    "is_oqs_available",
]

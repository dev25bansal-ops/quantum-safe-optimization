"""
Post-quantum cryptography port definitions.

Defines protocols for Key Encapsulation Mechanisms (KEM) and
digital signature schemes.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class KEMKeyPair:
    """
    A KEM key pair.

    Attributes:
        public_key: The public encapsulation key.
        secret_key: The secret decapsulation key.
        algorithm: Name of the KEM algorithm.
    """

    public_key: bytes
    secret_key: bytes
    algorithm: str


@dataclass(frozen=True)
class KEMEncapsulation:
    """
    Result of KEM encapsulation.

    Attributes:
        ciphertext: The encapsulated key ciphertext.
        shared_secret: The shared secret (symmetric key material).
    """

    ciphertext: bytes
    shared_secret: bytes


@dataclass(frozen=True)
class SignatureKeyPair:
    """
    A signature key pair.

    Attributes:
        public_key: The public verification key.
        secret_key: The secret signing key.
        algorithm: Name of the signature algorithm.
    """

    public_key: bytes
    secret_key: bytes
    algorithm: str


@runtime_checkable
class KEMScheme(Protocol):
    """
    Protocol for Key Encapsulation Mechanisms.

    KEMs provide a way to establish shared secrets using public key cryptography.
    Post-quantum KEMs like ML-KEM (Kyber) are resistant to quantum attacks.
    """

    @property
    def name(self) -> str:
        """Return the algorithm name (e.g., 'ML-KEM-768')."""
        ...

    @property
    def public_key_size(self) -> int:
        """Return the public key size in bytes."""
        ...

    @property
    def secret_key_size(self) -> int:
        """Return the secret key size in bytes."""
        ...

    @property
    def ciphertext_size(self) -> int:
        """Return the ciphertext size in bytes."""
        ...

    @property
    def shared_secret_size(self) -> int:
        """Return the shared secret size in bytes."""
        ...

    @property
    def security_level(self) -> int:
        """Return the NIST security level (1, 2, 3, or 5)."""
        ...

    def generate_keypair(self) -> KEMKeyPair:
        """
        Generate a new KEM key pair.

        Returns:
            A new key pair for encapsulation/decapsulation.

        Raises:
            CryptoError: If key generation fails.
        """
        ...

    def encapsulate(self, public_key: bytes) -> KEMEncapsulation:
        """
        Encapsulate a shared secret using a public key.

        Args:
            public_key: The recipient's public key.

        Returns:
            The encapsulation containing ciphertext and shared secret.

        Raises:
            CryptoError: If encapsulation fails.
        """
        ...

    def decapsulate(self, ciphertext: bytes, secret_key: bytes) -> bytes:
        """
        Decapsulate to recover the shared secret.

        Args:
            ciphertext: The encapsulated ciphertext.
            secret_key: The recipient's secret key.

        Returns:
            The recovered shared secret.

        Raises:
            CryptoError: If decapsulation fails.
        """
        ...


@runtime_checkable
class SignatureScheme(Protocol):
    """
    Protocol for digital signature schemes.

    Post-quantum signatures like ML-DSA (Dilithium) provide
    quantum-resistant authentication.
    """

    @property
    def name(self) -> str:
        """Return the algorithm name (e.g., 'ML-DSA-65')."""
        ...

    @property
    def public_key_size(self) -> int:
        """Return the public key size in bytes."""
        ...

    @property
    def secret_key_size(self) -> int:
        """Return the secret key size in bytes."""
        ...

    @property
    def signature_size(self) -> int:
        """Return the signature size in bytes."""
        ...

    @property
    def security_level(self) -> int:
        """Return the NIST security level (1, 2, 3, or 5)."""
        ...

    def generate_keypair(self) -> SignatureKeyPair:
        """
        Generate a new signature key pair.

        Returns:
            A new key pair for signing/verification.

        Raises:
            CryptoError: If key generation fails.
        """
        ...

    def sign(self, message: bytes, secret_key: bytes) -> bytes:
        """
        Sign a message.

        Args:
            message: The message to sign.
            secret_key: The signer's secret key.

        Returns:
            The signature bytes.

        Raises:
            CryptoError: If signing fails.
        """
        ...

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """
        Verify a signature.

        Args:
            message: The original message.
            signature: The signature to verify.
            public_key: The signer's public key.

        Returns:
            True if the signature is valid.

        Raises:
            CryptoError: If verification fails (distinct from invalid signature).
        """
        ...

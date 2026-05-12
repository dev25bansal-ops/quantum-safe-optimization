"""
AEAD (Authenticated Encryption with Associated Data) implementations.

Supports AES-256-GCM and ChaCha20-Poly1305.
"""

import os
from dataclasses import dataclass
from enum import Enum

from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305


class AEADAlgorithm(Enum):
    """Supported AEAD algorithms."""

    AES_256_GCM = "AES-256-GCM"
    CHACHA20_POLY1305 = "ChaCha20-Poly1305"

    @property
    def key_size(self) -> int:
        """Key size in bytes."""
        if self == AEADAlgorithm.AES_256_GCM:
            return 32
        elif self == AEADAlgorithm.CHACHA20_POLY1305:
            return 32
        raise ValueError(f"Unknown algorithm: {self}")

    @property
    def nonce_size(self) -> int:
        """Nonce size in bytes."""
        if self == AEADAlgorithm.AES_256_GCM:
            return 12  # 96 bits
        elif self == AEADAlgorithm.CHACHA20_POLY1305:
            return 12  # 96 bits
        raise ValueError(f"Unknown algorithm: {self}")

    @property
    def tag_size(self) -> int:
        """Authentication tag size in bytes."""
        return 16  # Both use 128-bit tags


@dataclass(frozen=True)
class EncryptedData:
    """Container for encrypted data."""

    ciphertext: bytes
    nonce: bytes
    tag: bytes
    algorithm: AEADAlgorithm

    def to_bytes(self) -> bytes:
        """Serialize to bytes (nonce || ciphertext || tag)."""
        # Note: For GCM, tag is appended to ciphertext by cryptography library
        return self.nonce + self.ciphertext

    @classmethod
    def from_bytes(cls, data: bytes, algorithm: AEADAlgorithm) -> "EncryptedData":
        """Deserialize from bytes."""
        nonce_size = algorithm.nonce_size
        tag_size = algorithm.tag_size

        if len(data) < nonce_size + tag_size:
            raise ValueError("Data too short to contain nonce and tag")

        nonce = data[:nonce_size]
        ciphertext_with_tag = data[nonce_size:]

        # Tag is appended to ciphertext by cryptography library
        ciphertext_with_tag[:-tag_size]
        tag = ciphertext_with_tag[-tag_size:]

        return cls(
            ciphertext=ciphertext_with_tag,  # Keep together for decryption
            nonce=nonce,
            tag=tag,
            algorithm=algorithm,
        )


class AEADCipher:
    """Convenience AES-GCM cipher with a cryptography-compatible surface."""

    def __init__(
        self,
        key: bytes | None = None,
        algorithm: AEADAlgorithm = AEADAlgorithm.AES_256_GCM,
    ):
        self._algorithm = algorithm
        self._key = key or self.generate_key()
        if len(self._key) != algorithm.key_size:
            raise ValueError(f"Key must be {algorithm.key_size} bytes, got {len(self._key)}")
        self._cipher = (
            AESGCM(self._key)
            if algorithm == AEADAlgorithm.AES_256_GCM
            else ChaCha20Poly1305(self._key)
        )

    @property
    def algorithm(self) -> AEADAlgorithm:
        """The algorithm used by this cipher."""
        return self._algorithm

    @staticmethod
    def generate_key() -> bytes:
        """Generate a 256-bit AEAD key."""
        return os.urandom(32)

    def encrypt(self, nonce: bytes, plaintext: bytes, aad: bytes | None = None) -> bytes:
        """Encrypt using the same argument order as cryptography's AEAD classes."""
        if len(nonce) != self.algorithm.nonce_size:
            raise ValueError(f"Nonce must be {self.algorithm.nonce_size} bytes")
        return self._cipher.encrypt(nonce, plaintext, aad)

    def decrypt(self, nonce: bytes, ciphertext: bytes, aad: bytes | None = None) -> bytes:
        """Decrypt using the same argument order as cryptography's AEAD classes."""
        if len(nonce) != self.algorithm.nonce_size:
            raise ValueError(f"Nonce must be {self.algorithm.nonce_size} bytes")
        return self._cipher.decrypt(nonce, ciphertext, aad)

    def encrypt_bytes(
        self,
        plaintext: bytes,
        aad: bytes | None = None,
        nonce: bytes | None = None,
    ) -> bytes:
        """Encrypt and return as serialized bytes."""
        if type(self) is AEADCipher:
            nonce = nonce or os.urandom(self.algorithm.nonce_size)
            return nonce + self.encrypt(nonce, plaintext, aad)

        encrypted = self.encrypt(plaintext, aad, nonce)
        return encrypted.to_bytes()

    def decrypt_bytes(
        self,
        data: bytes,
        aad: bytes | None = None,
    ) -> bytes:
        """Decrypt from serialized bytes."""
        if type(self) is AEADCipher:
            nonce = data[: self.algorithm.nonce_size]
            ciphertext = data[self.algorithm.nonce_size :]
            return self.decrypt(nonce, ciphertext, aad)

        encrypted = EncryptedData.from_bytes(data, self.algorithm)
        return self.decrypt(encrypted, aad)


class AES256GCMCipher(AEADCipher):
    """AES-256-GCM cipher implementation."""

    def __init__(self, key: bytes):
        """
        Initialize with encryption key.

        Args:
            key: 32-byte (256-bit) key.
        """
        if not isinstance(key, bytes):
            raise TypeError("Key must be bytes")
        if len(key) != 32:
            raise ValueError(f"Key must be 32 bytes, got {len(key)}")

        self._key = key
        self._cipher = AESGCM(key)

    @property
    def algorithm(self) -> AEADAlgorithm:
        return AEADAlgorithm.AES_256_GCM

    def encrypt(
        self,
        plaintext: bytes,
        aad: bytes | None = None,
        nonce: bytes | None = None,
    ) -> EncryptedData:
        if not isinstance(plaintext, bytes):
            raise TypeError("Plaintext must be bytes")
        if aad is not None and not isinstance(aad, bytes):
            raise TypeError("AAD must be bytes")

        # Generate random nonce if not provided
        if nonce is None:
            nonce = os.urandom(12)
        elif len(nonce) != 12:
            raise ValueError(f"Nonce must be 12 bytes, got {len(nonce)}")

        # Encrypt (returns ciphertext || tag)
        ciphertext_with_tag = self._cipher.encrypt(nonce, plaintext, aad)

        # Extract tag (last 16 bytes)
        tag = ciphertext_with_tag[-16:]

        return EncryptedData(
            ciphertext=ciphertext_with_tag,
            nonce=nonce,
            tag=tag,
            algorithm=self.algorithm,
        )

    def decrypt(
        self,
        encrypted: EncryptedData,
        aad: bytes | None = None,
    ) -> bytes:
        if encrypted.algorithm != self.algorithm:
            raise ValueError(
                f"Algorithm mismatch: expected {self.algorithm}, got {encrypted.algorithm}"
            )
        if aad is not None and not isinstance(aad, bytes):
            raise TypeError("AAD must be bytes")

        try:
            return self._cipher.decrypt(encrypted.nonce, encrypted.ciphertext, aad)
        except Exception as e:
            raise ValueError("Decryption failed: authentication error") from e


class ChaCha20Poly1305Cipher(AEADCipher):
    """ChaCha20-Poly1305 cipher implementation."""

    def __init__(self, key: bytes):
        """
        Initialize with encryption key.

        Args:
            key: 32-byte (256-bit) key.
        """
        if not isinstance(key, bytes):
            raise TypeError("Key must be bytes")
        if len(key) != 32:
            raise ValueError(f"Key must be 32 bytes, got {len(key)}")

        self._key = key
        self._cipher = ChaCha20Poly1305(key)

    @property
    def algorithm(self) -> AEADAlgorithm:
        return AEADAlgorithm.CHACHA20_POLY1305

    def encrypt(
        self,
        plaintext: bytes,
        aad: bytes | None = None,
        nonce: bytes | None = None,
    ) -> EncryptedData:
        if not isinstance(plaintext, bytes):
            raise TypeError("Plaintext must be bytes")
        if aad is not None and not isinstance(aad, bytes):
            raise TypeError("AAD must be bytes")

        # Generate random nonce if not provided
        if nonce is None:
            nonce = os.urandom(12)
        elif len(nonce) != 12:
            raise ValueError(f"Nonce must be 12 bytes, got {len(nonce)}")

        # Encrypt (returns ciphertext || tag)
        ciphertext_with_tag = self._cipher.encrypt(nonce, plaintext, aad)

        # Extract tag (last 16 bytes)
        tag = ciphertext_with_tag[-16:]

        return EncryptedData(
            ciphertext=ciphertext_with_tag,
            nonce=nonce,
            tag=tag,
            algorithm=self.algorithm,
        )

    def decrypt(
        self,
        encrypted: EncryptedData,
        aad: bytes | None = None,
    ) -> bytes:
        if encrypted.algorithm != self.algorithm:
            raise ValueError(
                f"Algorithm mismatch: expected {self.algorithm}, got {encrypted.algorithm}"
            )
        if aad is not None and not isinstance(aad, bytes):
            raise TypeError("AAD must be bytes")

        try:
            return self._cipher.decrypt(encrypted.nonce, encrypted.ciphertext, aad)
        except Exception as e:
            raise ValueError("Decryption failed: authentication error") from e


def get_aead_cipher(algorithm: AEADAlgorithm, key: bytes) -> AEADCipher:
    """
    Get an AEAD cipher for the specified algorithm.

    Args:
        algorithm: AEAD algorithm to use.
        key: Encryption key (32 bytes).

    Returns:
        AEADCipher instance.
    """
    if algorithm == AEADAlgorithm.AES_256_GCM:
        return AES256GCMCipher(key)
    elif algorithm == AEADAlgorithm.CHACHA20_POLY1305:
        return ChaCha20Poly1305Cipher(key)
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")


__all__ = [
    "AEADAlgorithm",
    "AEADCipher",
    "AES256GCMCipher",
    "ChaCha20Poly1305Cipher",
    "EncryptedData",
    "get_aead_cipher",
]

"""
HKDF (HMAC-based Key Derivation Function) utilities.

Provides key derivation and expansion using HKDF-SHA256.
"""

from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF, HKDFExpand


@dataclass(frozen=True)
class HKDFConfig:
    """Configuration for HKDF operations."""

    hash_algorithm: str = "SHA256"

    @property
    def hash_length(self) -> int:
        """Output length of the hash algorithm."""
        if self.hash_algorithm == "SHA256":
            return 32
        elif self.hash_algorithm == "SHA384":
            return 48
        elif self.hash_algorithm == "SHA512":
            return 64
        raise ValueError(f"Unsupported hash algorithm: {self.hash_algorithm}")

    def get_hash(self) -> hashes.HashAlgorithm:
        """Get the cryptography hash algorithm instance."""
        if self.hash_algorithm == "SHA256":
            return hashes.SHA256()
        elif self.hash_algorithm == "SHA384":
            return hashes.SHA384()
        elif self.hash_algorithm == "SHA512":
            return hashes.SHA512()
        raise ValueError(f"Unsupported hash algorithm: {self.hash_algorithm}")


DEFAULT_CONFIG = HKDFConfig()


def derive_key(
    input_key_material: bytes,
    length: int,
    salt: bytes | None = None,
    info: bytes | None = None,
    config: HKDFConfig | None = None,
) -> bytes:
    """
    Derive a cryptographic key using HKDF.

    Performs both extract and expand phases of HKDF.

    Args:
        input_key_material: The input keying material (e.g., shared secret).
        length: Desired output key length in bytes.
        salt: Optional salt value. If None, uses zeros.
        info: Optional context/application-specific info.
        config: HKDF configuration. Uses SHA256 by default.

    Returns:
        Derived key of specified length.

    Raises:
        ValueError: If length exceeds maximum allowed.
        TypeError: If inputs are wrong type.
    """
    if config is None:
        config = DEFAULT_CONFIG

    if not isinstance(input_key_material, bytes):
        raise TypeError("input_key_material must be bytes")
    if len(input_key_material) == 0:
        raise ValueError("input_key_material cannot be empty")
    if salt is not None and not isinstance(salt, bytes):
        raise TypeError("salt must be bytes")
    if info is not None and not isinstance(info, bytes):
        raise TypeError("info must be bytes")

    # Maximum output length for HKDF is 255 * hash_length
    max_length = 255 * config.hash_length
    if length <= 0:
        raise ValueError("length must be positive")
    if length > max_length:
        raise ValueError(
            f"Requested length {length} exceeds maximum {max_length} for {config.hash_algorithm}"
        )

    hkdf = HKDF(
        algorithm=config.get_hash(),
        length=length,
        salt=salt,
        info=info or b"",
    )

    return hkdf.derive(input_key_material)


def expand_key(
    prk: bytes,
    length: int,
    info: bytes | None = None,
    config: HKDFConfig | None = None,
) -> bytes:
    """
    Expand a pseudorandom key using HKDF-Expand.

    Use this when you already have a uniformly random key (PRK)
    and need to derive additional keys from it.

    Args:
        prk: Pseudorandom key (output of extract or derive).
        length: Desired output key length in bytes.
        info: Optional context/application-specific info.
        config: HKDF configuration. Uses SHA256 by default.

    Returns:
        Expanded key of specified length.

    Raises:
        ValueError: If length exceeds maximum allowed.
        TypeError: If inputs are wrong type.
    """
    if config is None:
        config = DEFAULT_CONFIG

    if not isinstance(prk, bytes):
        raise TypeError("prk must be bytes")
    if len(prk) < config.hash_length:
        raise ValueError(
            f"PRK must be at least {config.hash_length} bytes for {config.hash_algorithm}, "
            f"got {len(prk)}"
        )
    if info is not None and not isinstance(info, bytes):
        raise TypeError("info must be bytes")

    # Maximum output length for HKDF is 255 * hash_length
    max_length = 255 * config.hash_length
    if length <= 0:
        raise ValueError("length must be positive")
    if length > max_length:
        raise ValueError(
            f"Requested length {length} exceeds maximum {max_length} for {config.hash_algorithm}"
        )

    hkdf_expand = HKDFExpand(
        algorithm=config.get_hash(),
        length=length,
        info=info or b"",
    )

    return hkdf_expand.derive(prk)


def derive_multiple_keys(
    input_key_material: bytes,
    key_specs: list,
    salt: bytes | None = None,
    config: HKDFConfig | None = None,
) -> list:
    """
    Derive multiple keys with different contexts from the same IKM.

    Args:
        input_key_material: The input keying material.
        key_specs: List of (info, length) tuples for each key.
        salt: Optional salt value.
        config: HKDF configuration.

    Returns:
        List of derived keys in the same order as key_specs.

    Example:
        keys = derive_multiple_keys(
            shared_secret,
            [
                (b"encryption_key", 32),
                (b"mac_key", 32),
                (b"iv", 12),
            ]
        )
    """
    if config is None:
        config = DEFAULT_CONFIG

    if not isinstance(input_key_material, bytes):
        raise TypeError("input_key_material must be bytes")
    if len(input_key_material) == 0:
        raise ValueError("input_key_material cannot be empty")

    # First, extract to get PRK
    prk = derive_key(input_key_material, config.hash_length, salt=salt, config=config)

    # Then expand for each key
    keys = []
    for info, length in key_specs:
        if not isinstance(info, bytes):
            raise TypeError("info must be bytes")
        if not isinstance(length, int) or length <= 0:
            raise ValueError("length must be a positive integer")

        key = expand_key(prk, length, info=info, config=config)
        keys.append(key)

    return keys


__all__ = [
    "HKDFConfig",
    "derive_key",
    "expand_key",
    "derive_multiple_keys",
]

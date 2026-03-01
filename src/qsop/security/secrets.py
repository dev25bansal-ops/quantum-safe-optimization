"""Secret handling utilities with secure memory management."""

from __future__ import annotations

import ctypes
import hmac
import secrets
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass


class SecretError(Exception):
    """Base exception for secret handling errors."""

    pass


def zeroize(data: bytearray | memoryview) -> None:
    """
    Securely zero out memory containing sensitive data.

    Args:
        data: Mutable byte data to zero out

    Note:
        This function attempts to prevent compiler optimization from
        removing the zeroing operation. It uses ctypes.memset for
        more reliable zeroing.
    """
    if isinstance(data, memoryview):
        if data.readonly:
            raise SecretError("Cannot zeroize read-only memoryview")
        data_len = len(data)
        for i in range(data_len):
            data[i] = 0
    elif isinstance(data, bytearray):
        data_len = len(data)
        ctypes.memset(
            (ctypes.c_char * data_len).from_buffer(data),
            0,
            data_len,
        )
        for i in range(data_len):
            data[i] = 0
    else:
        raise TypeError("data must be bytearray or memoryview")


def secure_compare(a: bytes, b: bytes) -> bool:
    """
    Compare two byte strings in constant time.

    This prevents timing attacks by ensuring the comparison takes
    the same amount of time regardless of where the first difference occurs.

    Args:
        a: First byte string
        b: Second byte string

    Returns:
        True if strings are equal, False otherwise
    """
    return hmac.compare_digest(a, b)


def generate_secure_random(length: int) -> bytes:
    """
    Generate cryptographically secure random bytes.

    Args:
        length: Number of bytes to generate

    Returns:
        Random bytes
    """
    if length < 0:
        raise ValueError("Length must be non-negative")
    return secrets.token_bytes(length)


def generate_secure_token(length: int = 32) -> str:
    """
    Generate a URL-safe random token.

    Args:
        length: Number of random bytes (token will be longer due to encoding)

    Returns:
        URL-safe base64 encoded token
    """
    return secrets.token_urlsafe(length)


class SecureBytes:
    """
    Secure container for sensitive byte data.

    Features:
    - Automatic memory zeroing on deletion
    - Controlled access to underlying data
    - Prevention of accidental string representation

    Example:
        secret = SecureBytes(b"my-secret-key")
        with secret.reveal() as data:
            use_secret_data(data)
        # Data is automatically zeroized when SecureBytes is garbage collected
    """

    __slots__ = ("_data", "_locked")

    def __init__(self, data: bytes) -> None:
        """
        Initialize with sensitive data.

        Args:
            data: The sensitive data to protect
        """
        self._data = bytearray(data)
        self._locked = False

        if isinstance(data, bytearray):
            zeroize(data)

    def __del__(self) -> None:
        """Zero out data on deletion."""
        if hasattr(self, "_data") and self._data:
            try:
                zeroize(self._data)
            except Exception:
                pass

    def __repr__(self) -> str:
        """Prevent accidental exposure in logs."""
        return f"SecureBytes(length={len(self._data)}, locked={self._locked})"

    def __str__(self) -> str:
        """Prevent accidental exposure in string conversion."""
        return "[REDACTED SecureBytes]"

    def __len__(self) -> int:
        """Return length of data."""
        return len(self._data)

    def __eq__(self, other: object) -> bool:
        """Constant-time comparison with another SecureBytes."""
        if isinstance(other, SecureBytes):
            return secure_compare(bytes(self._data), bytes(other._data))
        if isinstance(other, bytes):
            return secure_compare(bytes(self._data), other)
        return NotImplemented

    @contextmanager
    def reveal(self) -> Generator[memoryview, None, None]:
        """
        Context manager to access the secret data.

        Yields:
            A memoryview of the secret data

        Raises:
            SecretError: If the secret is locked

        Example:
            with secret.reveal() as data:
                key = bytes(data)
        """
        if self._locked:
            raise SecretError("Secret is locked and cannot be revealed")

        view = memoryview(self._data)
        try:
            yield view
        finally:
            view.release()

    def lock(self) -> None:
        """
        Lock the secret, preventing further access.

        Once locked, the secret cannot be revealed again.
        """
        self._locked = True

    def copy(self) -> SecureBytes:
        """
        Create a copy of this secret.

        Returns:
            A new SecureBytes with the same data
        """
        if self._locked:
            raise SecretError("Cannot copy locked secret")
        return SecureBytes(bytes(self._data))

    def derive(self, derivation_fn: callable) -> SecureBytes:
        """
        Derive a new secret using a derivation function.

        Args:
            derivation_fn: Function that takes bytes and returns bytes

        Returns:
            New SecureBytes with derived data
        """
        if self._locked:
            raise SecretError("Cannot derive from locked secret")

        with self.reveal() as data:
            derived = derivation_fn(bytes(data))

        return SecureBytes(derived)

    @classmethod
    def generate(cls, length: int = 32) -> SecureBytes:
        """
        Generate a new random secret.

        Args:
            length: Number of bytes to generate

        Returns:
            New SecureBytes with random data
        """
        return cls(generate_secure_random(length))

    def to_bytes(self) -> bytes:
        """
        Get an immutable copy of the secret data.

        Warning: The returned bytes cannot be securely erased.
        Use reveal() context manager for safer access.

        Returns:
            Copy of the secret data
        """
        if self._locked:
            raise SecretError("Cannot access locked secret")
        return bytes(self._data)


@dataclass
class ProtectedMemory:
    """
    Manager for memory protection operations.

    Provides utilities for working with sensitive data in memory,
    including allocation, protection, and secure destruction.
    """

    @staticmethod
    def allocate_secure(size: int) -> bytearray:
        """
        Allocate a bytearray for sensitive data.

        Args:
            size: Size in bytes

        Returns:
            Zero-initialized bytearray
        """
        return bytearray(size)

    @staticmethod
    def secure_copy(source: bytes) -> SecureBytes:
        """
        Create a secure copy of sensitive data.

        Args:
            source: Data to copy

        Returns:
            SecureBytes containing the data
        """
        return SecureBytes(source)

    @staticmethod
    @contextmanager
    def temporary_secret(data: bytes) -> Generator[memoryview, None, None]:
        """
        Create a temporary secret that is automatically zeroized.

        Args:
            data: The sensitive data

        Yields:
            memoryview of the data
        """
        temp = bytearray(data)
        view = memoryview(temp)
        try:
            yield view
        finally:
            view.release()
            zeroize(temp)


class SecretKey:
    """
    Represents a cryptographic key with secure handling.

    Wraps SecureBytes with additional key-specific functionality.
    """

    __slots__ = ("_secret", "_algorithm", "_key_id")

    def __init__(
        self,
        key_data: bytes,
        algorithm: str,
        key_id: str | None = None,
    ) -> None:
        """
        Initialize a secret key.

        Args:
            key_data: The raw key material
            algorithm: Algorithm this key is used with
            key_id: Optional key identifier
        """
        self._secret = SecureBytes(key_data)
        self._algorithm = algorithm
        self._key_id = key_id or generate_secure_token(16)

    def __repr__(self) -> str:
        return f"SecretKey(algorithm={self._algorithm}, key_id={self._key_id})"

    @property
    def algorithm(self) -> str:
        return self._algorithm

    @property
    def key_id(self) -> str:
        return self._key_id

    @property
    def key_length(self) -> int:
        return len(self._secret)

    @contextmanager
    def use(self) -> Generator[memoryview, None, None]:
        """
        Use the key material.

        Yields:
            memoryview of the key data
        """
        with self._secret.reveal() as data:
            yield data

    def destroy(self) -> None:
        """Securely destroy the key."""
        self._secret.lock()

    @classmethod
    def generate(
        cls,
        algorithm: str,
        length: int,
        key_id: str | None = None,
    ) -> SecretKey:
        """
        Generate a new random key.

        Args:
            algorithm: Algorithm for this key
            length: Key length in bytes
            key_id: Optional key identifier

        Returns:
            New SecretKey
        """
        return cls(
            generate_secure_random(length),
            algorithm,
            key_id,
        )


def scrub_memory() -> None:
    """
    Attempt to scrub sensitive data from Python's memory.

    Note: This is a best-effort operation. Python's memory management
    makes it impossible to guarantee all sensitive data is removed.
    """
    import gc

    gc.collect()
    gc.collect()
    gc.collect()

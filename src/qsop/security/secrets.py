"""Secret handling helpers.

These utilities keep common secret operations in one place so callers do not
fall back to plain equality checks or ad hoc random generation.
"""

from __future__ import annotations

import hmac
import secrets
from collections.abc import ByteString


class SecureBytes:
    """Mutable byte container that can be explicitly zeroized."""

    def __init__(self, value: bytes | bytearray | memoryview | str):
        if isinstance(value, str):
            value = value.encode("utf-8")
        self._buffer = bytearray(value)

    @classmethod
    def random(cls, length: int = 32) -> "SecureBytes":
        """Create a secure random byte container."""
        return cls(generate_secure_random(length))

    def as_bytes(self) -> bytes:
        """Return a copy of the contained bytes."""
        return bytes(self._buffer)

    def zeroize(self) -> None:
        """Overwrite the contained bytes in-place."""
        zeroize(self._buffer)

    def __bytes__(self) -> bytes:
        return self.as_bytes()

    def __len__(self) -> int:
        return len(self._buffer)

    def __repr__(self) -> str:
        return f"SecureBytes(length={len(self)})"


def generate_secure_random(length: int = 32) -> bytes:
    """Generate cryptographically secure random bytes."""
    if length <= 0:
        raise ValueError("length must be positive")
    return secrets.token_bytes(length)


def secure_compare(left: bytes | str | ByteString, right: bytes | str | ByteString) -> bool:
    """Compare secret values in constant time."""
    if isinstance(left, str):
        left = left.encode("utf-8")
    if isinstance(right, str):
        right = right.encode("utf-8")
    return hmac.compare_digest(bytes(left), bytes(right))


def zeroize(value: bytearray | memoryview | SecureBytes) -> None:
    """Best-effort in-place overwrite for mutable secret buffers."""
    if isinstance(value, SecureBytes):
        value.zeroize()
        return

    if isinstance(value, memoryview):
        if value.readonly:
            raise ValueError("cannot zeroize a readonly memoryview")
        value[:] = b"\x00" * len(value)
        return

    if isinstance(value, bytearray):
        value[:] = b"\x00" * len(value)
        return

    raise TypeError("zeroize requires a mutable byte buffer")

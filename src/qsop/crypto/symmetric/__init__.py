"""
Symmetric cryptography utilities.

Provides AEAD encryption and key derivation.
"""

from qsop.crypto.symmetric.aead import (
    AEADAlgorithm,
    AEADCipher,
    AES256GCMCipher,
    ChaCha20Poly1305Cipher,
    get_aead_cipher,
)
from qsop.crypto.symmetric.hkdf import (
    HKDFConfig,
    derive_key,
    expand_key,
)

__all__ = [
    "AEADAlgorithm",
    "AEADCipher",
    "AES256GCMCipher",
    "ChaCha20Poly1305Cipher",
    "get_aead_cipher",
    "derive_key",
    "expand_key",
    "HKDFConfig",
]

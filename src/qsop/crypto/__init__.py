"""
QSOP Post-Quantum Cryptography Layer.

Provides post-quantum secure encryption, key encapsulation, and digital signatures.
"""

from qsop.crypto.envelopes import (
    EncryptedEnvelope,
    EnvelopeDecryptor,
    EnvelopeEncryptor,
    EnvelopeMetadata,
    RecipientInfo,
)
from qsop.crypto.pqc import (
    KEMAlgorithm,
    KEMProvider,
    SignatureAlgorithm,
    SignatureProvider,
    get_kem_provider,
    get_signature_provider,
)
from qsop.crypto.signing import (
    SignatureBundle,
    Signer,
    Verifier,
    canonicalize,
)
from qsop.crypto.symmetric import (
    AEADAlgorithm,
    AEADCipher,
    derive_key,
    expand_key,
    get_aead_cipher,
)

__all__ = [
    # PQC
    "KEMAlgorithm",
    "SignatureAlgorithm",
    "get_kem_provider",
    "get_signature_provider",
    "KEMProvider",
    "SignatureProvider",
    # Symmetric
    "AEADAlgorithm",
    "AEADCipher",
    "get_aead_cipher",
    "derive_key",
    "expand_key",
    # Envelopes
    "EnvelopeEncryptor",
    "EnvelopeDecryptor",
    "EncryptedEnvelope",
    "RecipientInfo",
    "EnvelopeMetadata",
    # Signing
    "Signer",
    "Verifier",
    "SignatureBundle",
    "canonicalize",
]

"""
QSOP Post-Quantum Cryptography Layer.

Provides post-quantum secure encryption, key encapsulation, and digital signatures.
"""

from qsop.crypto.pqc import (
    KEMAlgorithm,
    SignatureAlgorithm,
    get_kem_provider,
    get_signature_provider,
    KEMProvider,
    SignatureProvider,
)
from qsop.crypto.symmetric import (
    AEADAlgorithm,
    AEADCipher,
    get_aead_cipher,
    derive_key,
    expand_key,
)
from qsop.crypto.envelopes import (
    EnvelopeEncryptor,
    EnvelopeDecryptor,
    EncryptedEnvelope,
    RecipientInfo,
    EnvelopeMetadata,
)
from qsop.crypto.signing import (
    Signer,
    Verifier,
    SignatureBundle,
    canonicalize,
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

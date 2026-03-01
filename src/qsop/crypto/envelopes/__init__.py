"""
Envelope encryption for hybrid PQC encryption.

Provides KEM-DEM (Key Encapsulation Mechanism - Data Encapsulation Mechanism)
envelope encryption with multi-recipient support.
"""

from qsop.crypto.envelopes.envelope import (
    EncryptedEnvelope,
    EnvelopeDecryptor,
    EnvelopeEncryptor,
    RecipientInfo,
)
from qsop.crypto.envelopes.metadata import (
    EnvelopeMetadata,
    EnvelopeVersion,
    build_aad,
)

__all__ = [
    "EnvelopeEncryptor",
    "EnvelopeDecryptor",
    "EncryptedEnvelope",
    "RecipientInfo",
    "EnvelopeMetadata",
    "build_aad",
    "EnvelopeVersion",
]

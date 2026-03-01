"""
Envelope encryption implementation.

Provides KEM-DEM envelope encryption with multi-recipient support.
"""

import json
import os
from dataclasses import dataclass
from typing import Any

from qsop.crypto.envelopes.metadata import EnvelopeMetadata, build_aad
from qsop.crypto.pqc import KEMAlgorithm, KEMProvider, get_kem_provider
from qsop.crypto.symmetric import AEADAlgorithm, derive_key, get_aead_cipher


@dataclass
class RecipientInfo:
    """Information for a single envelope recipient."""

    public_key: bytes
    key_id: str | None = None
    kem_ciphertext: bytes | None = None
    wrapped_dek: bytes | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {}
        if self.public_key:
            result["public_key"] = self.public_key.hex()
        if self.key_id:
            result["key_id"] = self.key_id
        if self.kem_ciphertext:
            result["kem_ciphertext"] = self.kem_ciphertext.hex()
        if self.wrapped_dek:
            result["wrapped_dek"] = self.wrapped_dek.hex()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any], public_key: bytes = b"") -> "RecipientInfo":
        """Create from dictionary."""
        return cls(
            public_key=bytes.fromhex(data["public_key"]) if data.get("public_key") else public_key,
            key_id=data.get("key_id"),
            kem_ciphertext=bytes.fromhex(data["kem_ciphertext"])
            if data.get("kem_ciphertext")
            else None,
            wrapped_dek=bytes.fromhex(data["wrapped_dek"]) if data.get("wrapped_dek") else None,
        )


@dataclass
class EncryptedEnvelope:
    """Complete encrypted envelope with all recipient information."""

    metadata: EnvelopeMetadata
    recipients: list[RecipientInfo]
    ciphertext: bytes
    nonce: bytes

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "metadata": self.metadata.to_dict(),
            "recipients": [r.to_dict() for r in self.recipients],
            "ciphertext": self.ciphertext.hex(),
            "nonce": self.nonce.hex(),
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    def to_bytes(self) -> bytes:
        """Convert to compact bytes format."""
        return json.dumps(self.to_dict(), separators=(",", ":")).encode("utf-8")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EncryptedEnvelope":
        """Create from dictionary."""
        return cls(
            metadata=EnvelopeMetadata.from_dict(data["metadata"]),
            recipients=[RecipientInfo.from_dict(r) for r in data["recipients"]],
            ciphertext=bytes.fromhex(data["ciphertext"]),
            nonce=bytes.fromhex(data["nonce"]),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "EncryptedEnvelope":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_bytes(cls, data: bytes) -> "EncryptedEnvelope":
        """Create from bytes."""
        return cls.from_json(data.decode("utf-8"))


class EnvelopeEncryptor:
    """
    Envelope encryption using KEM-DEM pattern.

    Process:
    1. Generate random DEK (Data Encryption Key)
    2. For each recipient:
       - Use KEM to encapsulate shared secret
       - Derive KEK from shared secret
       - Wrap DEK with KEK
    3. Encrypt plaintext with DEK using AEAD
    """

    def __init__(
        self,
        kem_algorithm: KEMAlgorithm = KEMAlgorithm.KYBER768,
        aead_algorithm: AEADAlgorithm = AEADAlgorithm.AES_256_GCM,
        kem_provider: KEMProvider | None = None,
    ):
        """
        Initialize encryptor.

        Args:
            kem_algorithm: KEM algorithm for key encapsulation.
            aead_algorithm: AEAD algorithm for content encryption.
            kem_provider: Optional KEM provider (uses default if None).
        """
        self.kem_algorithm = kem_algorithm
        self.aead_algorithm = aead_algorithm
        self._kem_provider = kem_provider

    @property
    def kem_provider(self) -> KEMProvider:
        """Get KEM provider, initializing if needed."""
        if self._kem_provider is None:
            self._kem_provider = get_kem_provider(allow_fallback=True)
        return self._kem_provider

    def encrypt(
        self,
        plaintext: bytes,
        recipients: list[RecipientInfo],
        metadata: EnvelopeMetadata | None = None,
        additional_context: bytes | None = None,
    ) -> EncryptedEnvelope:
        """
        Encrypt plaintext for multiple recipients.

        Args:
            plaintext: Data to encrypt.
            recipients: List of recipients with public keys.
            metadata: Optional envelope metadata.
            additional_context: Optional additional AAD context.

        Returns:
            EncryptedEnvelope containing all encryption artifacts.
        """
        if not isinstance(plaintext, bytes):
            raise TypeError("plaintext must be bytes")
        if not recipients:
            raise ValueError("At least one recipient is required")

        for r in recipients:
            if not isinstance(r.public_key, bytes) or len(r.public_key) == 0:
                raise ValueError("Each recipient must have a valid public key")

        # Build metadata
        if metadata is None:
            metadata = EnvelopeMetadata()

        metadata.kem_algorithm = self.kem_algorithm.value
        metadata.aead_algorithm = self.aead_algorithm.value
        metadata.recipient_count = len(recipients)

        # Generate random DEK
        dek = os.urandom(self.aead_algorithm.key_size)

        # Process each recipient
        processed_recipients = []
        recipient_public_keys = [r.public_key for r in recipients]

        for recipient in recipients:
            # KEM encapsulation
            kem_ct, shared_secret = self.kem_provider.encapsulate(
                recipient.public_key,
                self.kem_algorithm,
            )

            # Derive KEK from shared secret
            kek = derive_key(
                shared_secret,
                32,
                salt=None,
                info=b"QSOP-envelope-kek-v1",
            )

            # Wrap DEK with KEK using AEAD
            kek_cipher = get_aead_cipher(self.aead_algorithm, kek)
            wrapped_dek_data = kek_cipher.encrypt_bytes(
                dek,
                aad=b"dek-wrap",
            )

            processed_recipients.append(
                RecipientInfo(
                    public_key=recipient.public_key,
                    key_id=recipient.key_id,
                    kem_ciphertext=kem_ct,
                    wrapped_dek=wrapped_dek_data,
                )
            )

        # Build AAD
        aad = build_aad(
            metadata,
            recipient_public_keys=recipient_public_keys,
            additional_context=additional_context,
        )

        # Encrypt plaintext with DEK
        dek_cipher = get_aead_cipher(self.aead_algorithm, dek)
        encrypted = dek_cipher.encrypt(plaintext, aad=aad)

        return EncryptedEnvelope(
            metadata=metadata,
            recipients=processed_recipients,
            ciphertext=encrypted.ciphertext,
            nonce=encrypted.nonce,
        )

    def encrypt_for_single_recipient(
        self,
        plaintext: bytes,
        public_key: bytes,
        key_id: str | None = None,
        metadata: EnvelopeMetadata | None = None,
    ) -> EncryptedEnvelope:
        """
        Convenience method for single-recipient encryption.

        Args:
            plaintext: Data to encrypt.
            public_key: Recipient's public key.
            key_id: Optional key identifier.
            metadata: Optional envelope metadata.

        Returns:
            EncryptedEnvelope.
        """
        recipient = RecipientInfo(public_key=public_key, key_id=key_id)
        return self.encrypt(plaintext, [recipient], metadata)


class EnvelopeDecryptor:
    """
    Envelope decryption.

    Process:
    1. Find matching recipient entry
    2. Use KEM to decapsulate shared secret
    3. Derive KEK from shared secret
    4. Unwrap DEK with KEK
    5. Decrypt ciphertext with DEK
    """

    def __init__(
        self,
        kem_provider: KEMProvider | None = None,
    ):
        """
        Initialize decryptor.

        Args:
            kem_provider: Optional KEM provider (uses default if None).
        """
        self._kem_provider = kem_provider

    @property
    def kem_provider(self) -> KEMProvider:
        """Get KEM provider, initializing if needed."""
        if self._kem_provider is None:
            self._kem_provider = get_kem_provider(allow_fallback=True)
        return self._kem_provider

    def decrypt(
        self,
        envelope: EncryptedEnvelope,
        secret_key: bytes,
        public_key: bytes | None = None,
        key_id: str | None = None,
        additional_context: bytes | None = None,
    ) -> bytes:
        """
        Decrypt an envelope.

        Must provide either public_key or key_id to identify the recipient entry.

        Args:
            envelope: Encrypted envelope.
            secret_key: Recipient's secret key.
            public_key: Recipient's public key (for matching).
            key_id: Key ID (for matching).
            additional_context: Additional AAD context (must match encryption).

        Returns:
            Decrypted plaintext.
        """
        if not isinstance(secret_key, bytes):
            raise TypeError("secret_key must be bytes")

        # Find matching recipient
        recipient = self._find_recipient(envelope, public_key, key_id)
        if recipient is None:
            raise ValueError("No matching recipient found in envelope")

        if recipient.kem_ciphertext is None or recipient.wrapped_dek is None:
            raise ValueError("Recipient entry is incomplete")

        # Parse algorithms from metadata
        kem_algorithm = KEMAlgorithm(envelope.metadata.kem_algorithm)
        aead_algorithm = AEADAlgorithm(envelope.metadata.aead_algorithm)

        # KEM decapsulation
        shared_secret = self.kem_provider.decapsulate(
            secret_key,
            recipient.kem_ciphertext,
            kem_algorithm,
        )

        # Derive KEK from shared secret
        kek = derive_key(
            shared_secret,
            32,
            salt=None,
            info=b"QSOP-envelope-kek-v1",
        )

        # Unwrap DEK
        kek_cipher = get_aead_cipher(aead_algorithm, kek)
        dek = kek_cipher.decrypt_bytes(recipient.wrapped_dek, aad=b"dek-wrap")

        # Build AAD - need to reconstruct recipient public keys to match encryption
        # During encryption, all recipient public keys were included in AAD
        # During decryption, we need to use the same set of public keys
        recipient_public_keys = []
        if public_key:
            # Use provided public_key if available
            recipient_public_keys = [public_key]
        else:
            # Otherwise, extract all public keys from the envelope to match encryption
            recipient_public_keys = [r.public_key for r in envelope.recipients]

        aad = build_aad(
            envelope.metadata,
            recipient_public_keys=recipient_public_keys,
            additional_context=additional_context,
        )

        # Decrypt ciphertext
        dek_cipher = get_aead_cipher(aead_algorithm, dek)
        from qsop.crypto.symmetric.aead import EncryptedData

        # The envelope.ciphertext contains ciphertext + tag in standard AEAD format
        encrypted = EncryptedData(
            ciphertext=envelope.ciphertext,
            nonce=envelope.nonce,
            tag=envelope.ciphertext[-16:],  # Extract tag from end of ciphertext
            algorithm=aead_algorithm,
        )

        return dek_cipher.decrypt(encrypted, aad=aad)

    def _find_recipient(
        self,
        envelope: EncryptedEnvelope,
        public_key: bytes | None,
        key_id: str | None,
    ) -> RecipientInfo | None:
        """Find matching recipient in envelope."""
        if public_key is None and key_id is None:
            # Return first recipient if only one
            if len(envelope.recipients) == 1:
                return envelope.recipients[0]
            raise ValueError("Must provide public_key or key_id for multi-recipient envelopes")

        for recipient in envelope.recipients:
            if key_id and recipient.key_id == key_id:
                return recipient
            if public_key and recipient.public_key == public_key:
                return recipient

        return None


__all__ = [
    "RecipientInfo",
    "EncryptedEnvelope",
    "EnvelopeEncryptor",
    "EnvelopeDecryptor",
]

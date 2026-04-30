"""
ML-KEM Encryption Service for Job Results.

Provides secure encryption of sensitive data using ML-KEM-768 (NIST FIPS 203)
for post-quantum secure key exchange combined with AES-256-GCM for symmetric encryption.

Features:
- Encrypt job results with user's registered public key
- Support for all ML-KEM security levels (512, 768, 1024)
- Automatic key management and caching
- JSON-serializable encrypted envelopes
"""

import base64
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

# Import PQC crypto module
import quantum_safe_crypto as pqc

logger = logging.getLogger(__name__)


@dataclass
class EncryptedResult:
    """Container for an encrypted job result."""

    kem_ciphertext: str  # Base64-encoded ML-KEM ciphertext
    nonce: str  # Base64-encoded AES-GCM nonce
    ciphertext: str  # Base64-encoded encrypted data
    algorithm: str  # e.g., "ML-KEM-768+AES-256-GCM"
    encrypted_at: str  # ISO timestamp
    key_id: str | None = None  # Reference to the key used


class MLKEMEncryptionService:
    """
    Service for encrypting sensitive data using ML-KEM + AES-256-GCM.

    ML-KEM (CRYSTALS-Kyber) is a post-quantum key encapsulation mechanism
    standardized by NIST in FIPS 203. This service uses ML-KEM to establish
    a shared secret, then derives an AES-256 key for symmetric encryption.
    """

    def __init__(self, default_security_level: int = 3):
        """
        Initialize the encryption service.

        Args:
            default_security_level: Default ML-KEM security level (1, 3, or 5)
                - Level 1: ML-KEM-512 (~AES-128 equivalent)
                - Level 3: ML-KEM-768 (~AES-192 equivalent, recommended)
                - Level 5: ML-KEM-1024 (~AES-256 equivalent)
        """
        self.default_security_level = default_security_level
        self._key_cache: dict[str, tuple[str, datetime]] = {}  # user_id -> (public_key, cached_at)

        logger.info("ml_kem_service_initialized", extra={"default_level": default_security_level})

    def generate_keypair(self, security_level: int | None = None) -> dict[str, str]:
        """
        Generate a new ML-KEM key pair.

        Args:
            security_level: Security level (1, 3, or 5). Defaults to service default.

        Returns:
            Dictionary with 'public_key', 'secret_key', 'algorithm', and 'security_level'
        """
        level = security_level or self.default_security_level
        keypair = pqc.KemKeyPair(security_level=level)

        return {
            "public_key": keypair.public_key,
            "secret_key": keypair.secret_key,
            "algorithm": keypair.algorithm,
            "security_level": level,
        }

    def encrypt_data(
        self, plaintext: bytes, recipient_public_key: str, key_id: str | None = None
    ) -> EncryptedResult:
        """
        Encrypt data using recipient's ML-KEM public key.

        The encryption process:
        1. Generate ephemeral ML-KEM ciphertext and shared secret
        2. Derive AES-256 key from shared secret using HKDF
        3. Encrypt plaintext with AES-256-GCM

        Args:
            plaintext: Data to encrypt
            recipient_public_key: Base64-encoded ML-KEM public key
            key_id: Optional reference to the key used

        Returns:
            EncryptedResult containing all components needed for decryption
        """
        # Use the high-level encrypt function from quantum_safe_crypto
        envelope = pqc.py_encrypt(plaintext, recipient_public_key)
        envelope_json = envelope.to_json()
        envelope_data = json.loads(base64.b64decode(envelope_json))

        return EncryptedResult(
            kem_ciphertext=base64.b64encode(bytes(envelope_data["kem_ciphertext"])).decode(),
            nonce=base64.b64encode(bytes(envelope_data["nonce"])).decode(),
            ciphertext=base64.b64encode(bytes(envelope_data["ciphertext"])).decode(),
            algorithm=envelope_data.get("algorithm", "ML-KEM-768+AES-256-GCM"),
            encrypted_at=datetime.now(UTC).isoformat(),
            key_id=key_id,
        )

    def encrypt_json(
        self, data: Any, recipient_public_key: str, key_id: str | None = None
    ) -> EncryptedResult:
        """
        Encrypt JSON-serializable data.

        Args:
            data: Any JSON-serializable object
            recipient_public_key: Base64-encoded ML-KEM public key
            key_id: Optional reference to the key used

        Returns:
            EncryptedResult containing encrypted JSON
        """
        json_bytes = json.dumps(data, default=str).encode("utf-8")
        return self.encrypt_data(json_bytes, recipient_public_key, key_id)

    def decrypt_data(self, encrypted_result: EncryptedResult, recipient_secret_key: str) -> bytes:
        """
        Decrypt data using recipient's ML-KEM secret key.

        Args:
            encrypted_result: EncryptedResult from encrypt_data()
            recipient_secret_key: Base64-encoded ML-KEM secret key

        Returns:
            Decrypted plaintext bytes
        """
        # Reconstruct envelope for decryption
        envelope_data = {
            "kem_ciphertext": list(base64.b64decode(encrypted_result.kem_ciphertext)),
            "nonce": list(base64.b64decode(encrypted_result.nonce)),
            "ciphertext": list(base64.b64decode(encrypted_result.ciphertext)),
            "algorithm": encrypted_result.algorithm,
        }
        envelope_json = base64.b64encode(json.dumps(envelope_data).encode()).decode()
        envelope = pqc.EncryptedEnvelope.from_json(envelope_json)

        return bytes(pqc.py_decrypt(envelope, recipient_secret_key))

    def decrypt_json(self, encrypted_result: EncryptedResult, recipient_secret_key: str) -> Any:
        """
        Decrypt to JSON object.

        Args:
            encrypted_result: EncryptedResult from encrypt_json()
            recipient_secret_key: Base64-encoded ML-KEM secret key

        Returns:
            Decrypted JSON object
        """
        plaintext = self.decrypt_data(encrypted_result, recipient_secret_key)
        return json.loads(plaintext.decode("utf-8"))

    def encapsulate(
        self, recipient_public_key: str, security_level: int | None = None
    ) -> tuple[str, str]:
        """
        Perform ML-KEM key encapsulation.

        This is useful when you need to establish a shared secret
        for custom key derivation (e.g., for session keys).

        Args:
            recipient_public_key: Base64-encoded ML-KEM public key
            security_level: Optional security level override

        Returns:
            Tuple of (ciphertext_base64, shared_secret_base64)
        """
        level = security_level or self.default_security_level
        if level == self.default_security_level:
            return pqc.py_kem_encapsulate(recipient_public_key)
        else:
            return pqc.py_kem_encapsulate_with_level(recipient_public_key, level)

    def decapsulate(
        self, ciphertext: str, recipient_secret_key: str, security_level: int | None = None
    ) -> str:
        """
        Perform ML-KEM key decapsulation.

        Args:
            ciphertext: Base64-encoded ML-KEM ciphertext
            recipient_secret_key: Base64-encoded ML-KEM secret key
            security_level: Optional security level override

        Returns:
            Base64-encoded shared secret
        """
        level = security_level or self.default_security_level
        if level == self.default_security_level:
            return pqc.py_kem_decapsulate(ciphertext, recipient_secret_key)
        else:
            return pqc.py_kem_decapsulate_with_level(ciphertext, recipient_secret_key, level)

    def to_dict(self, encrypted_result: EncryptedResult) -> dict[str, Any]:
        """Convert EncryptedResult to dictionary for JSON serialization."""
        return {
            "kem_ciphertext": encrypted_result.kem_ciphertext,
            "nonce": encrypted_result.nonce,
            "ciphertext": encrypted_result.ciphertext,
            "algorithm": encrypted_result.algorithm,
            "encrypted_at": encrypted_result.encrypted_at,
            "key_id": encrypted_result.key_id,
        }

    def from_dict(self, data: dict[str, Any]) -> EncryptedResult:
        """Create EncryptedResult from dictionary."""
        return EncryptedResult(
            kem_ciphertext=data["kem_ciphertext"],
            nonce=data["nonce"],
            ciphertext=data["ciphertext"],
            algorithm=data.get("algorithm", "ML-KEM-768+AES-256-GCM"),
            encrypted_at=data.get("encrypted_at", datetime.now(UTC).isoformat()),
            key_id=data.get("key_id"),
        )


# Global service instance
encryption_service = MLKEMEncryptionService(default_security_level=3)


def encrypt_job_result(
    result: dict[str, Any], user_public_key: str, key_id: str | None = None
) -> dict[str, Any]:
    """
    Encrypt a job result using the user's ML-KEM public key.

    Args:
        result: Job result dictionary to encrypt
        user_public_key: User's registered ML-KEM public key (base64)
        key_id: Optional key identifier

    Returns:
        Dictionary with 'encrypted' flag and encrypted envelope
    """
    try:
        encrypted = encryption_service.encrypt_json(result, user_public_key, key_id)
        return {
            "encrypted": True,
            "algorithm": encrypted.algorithm,
            "envelope": encryption_service.to_dict(encrypted),
        }
    except Exception as e:
        logger.error("job_result_encryption_failed", extra={"error": str(e)})
        # Return unencrypted if encryption fails (with warning)
        return {
            "encrypted": False,
            "encryption_error": str(e),
            "result": result,
        }


def decrypt_job_result(encrypted_envelope: dict[str, Any], user_secret_key: str) -> dict[str, Any]:
    """
    Decrypt a job result using the user's ML-KEM secret key.

    Args:
        encrypted_envelope: Envelope from encrypt_job_result()
        user_secret_key: User's ML-KEM secret key (base64)

    Returns:
        Decrypted job result dictionary
    """
    envelope = encryption_service.from_dict(encrypted_envelope["envelope"])
    return encryption_service.decrypt_json(envelope, user_secret_key)


def get_supported_algorithms() -> dict[str, Any]:
    """Get information about supported encryption algorithms."""
    levels = pqc.py_get_supported_levels()
    return {
        "kem_algorithms": [{"level": level, "name": kem, "dsa": dsa} for level, kem, dsa in levels],
        "symmetric_algorithm": "AES-256-GCM",
        "key_derivation": "HKDF-SHA256",
        "default_level": 3,
        "recommended": "ML-KEM-768+AES-256-GCM",
    }

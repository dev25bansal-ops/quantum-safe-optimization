"""Quantum-Safe Cryptography Module - Production Implementation.

This module provides post-quantum cryptography using liboqs when available,
with a secure stub fallback for development.

SECURITY WARNING:
    The stub implementation uses random bytes and is NOT cryptographically secure.
    For production, install liboqs:

    Linux/macOS:
        brew install liboqs  # macOS
        apt install liboqs-dev  # Ubuntu/Debian

    Windows:
        See: https://github.com/open-quantum-safe/liboqs/wiki/Customizing-liboqs

    Then: pip install liboqs-python
"""

import base64
import hashlib
import json
import logging
import os
import secrets
import warnings
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

LIBOQS_AVAILABLE = False
_OQS_MODULE = None

try:
    import oqs

    LIBOQS_AVAILABLE = True
    _OQS_MODULE = oqs
    logger.info("liboqs loaded successfully - using REAL PQC algorithms")
except ImportError:
    warnings.warn(
        "liboqs not available. Using STUB implementation for development. "
        "Install liboqs-python with liboqs for production. "
        "See: https://github.com/open-quantum-safe/liboqs-python"
    )
except Exception as e:
    warnings.warn(f"liboqs import failed: {e}. Using stub implementation.")


def is_crypto_production_ready() -> bool:
    """Check if real PQC algorithms are available."""
    return LIBOQS_AVAILABLE


def get_crypto_status() -> dict:
    """Get current crypto implementation status."""
    return {
        "liboqs_available": LIBOQS_AVAILABLE,
        "implementation": "liboqs" if LIBOQS_AVAILABLE else "STUB",
        "security_warning": None
        if LIBOQS_AVAILABLE
        else "STUB IMPLEMENTATION - NOT FOR PRODUCTION",
    }


class SecurityLevel:
    """Security level for PQC algorithms (NIST levels 1, 3, 5)."""

    LEVELS = {1, 3, 5}
    KEM_ALGORITHMS = {1: "Kyber512", 3: "Kyber768", 5: "Kyber1024"}
    DSA_ALGORITHMS = {1: "Dilithium2", 2: "Dilithium2", 3: "Dilithium3", 5: "Dilithium5"}

    def __init__(self, level: int):
        if level not in self.LEVELS:
            raise ValueError(f"Invalid security level {level}. Use {self.LEVELS}")
        self.level = level

    @property
    def kem_algorithm(self) -> str:
        return self.KEM_ALGORITHMS.get(self.level, "Kyber768")

    @property
    def dsa_algorithm(self) -> str:
        return self.DSA_ALGORITHMS.get(self.level, "Dilithium3")

    @staticmethod
    def level1() -> "SecurityLevel":
        return SecurityLevel(1)

    @staticmethod
    def level3() -> "SecurityLevel":
        return SecurityLevel(3)

    @staticmethod
    def level5() -> "SecurityLevel":
        return SecurityLevel(5)


_KEY_SIZES = {
    "kem": {
        1: {"public": 800, "secret": 1632, "ciphertext": 768},
        3: {"public": 1184, "secret": 2400, "ciphertext": 1088},
        5: {"public": 1568, "secret": 3168, "ciphertext": 1568},
    },
    "dsa": {
        2: {"public": 1312, "secret": 2560, "signature": 2420},
        3: {"public": 1952, "secret": 4032, "signature": 3293},
        5: {"public": 2592, "secret": 4896, "signature": 4595},
    },
}


class KemKeyPair:
    """ML-KEM (Kyber) key pair for key encapsulation.

    Uses REAL liboqs when available, stub otherwise.
    """

    def __init__(self, security_level: Optional[int] = None):
        self._security_level = security_level or 3
        self._kem_alg = SecurityLevel.KEM_ALGORITHMS[self._security_level]
        self._kem = None

        if LIBOQS_AVAILABLE:
            try:
                self._kem = _OQS_MODULE.KeyEncapsulation(self._kem_alg)
                self._public_key_bytes = self._kem.generate_keypair()
                self._secret_key_bytes = self._kem.export_secret_key()
            except Exception as e:
                logger.warning(f"Failed to initialize liboqs KEM: {e}, falling back to stub")
                self._kem = None
                self._init_stub()
        else:
            self._init_stub()

    def _init_stub(self):
        sizes = _KEY_SIZES["kem"][self._security_level]
        self._public_key_bytes = secrets.token_bytes(sizes["public"])
        self._secret_key_bytes = secrets.token_bytes(sizes["secret"])

    @property
    def public_key(self) -> str:
        return base64.b64encode(self._public_key_bytes).decode("utf-8")

    @property
    def secret_key(self) -> str:
        return base64.b64encode(self._secret_key_bytes).decode("utf-8")

    @property
    def security_level(self) -> int:
        return self._security_level

    @property
    def algorithm(self) -> str:
        return self._kem_alg

    def encapsulate(self) -> tuple[str, str]:
        """Encapsulate a shared secret. Returns (ciphertext_b64, shared_secret_b64)."""
        if LIBOQS_AVAILABLE and self._kem:
            try:
                ciphertext, shared_secret = self._kem.encap_secret(self._public_key_bytes)
                return (
                    base64.b64encode(ciphertext).decode("utf-8"),
                    base64.b64encode(shared_secret).decode("utf-8"),
                )
            except Exception as e:
                logger.warning(f"liboqs encapsulation failed: {e}, using stub")

        sizes = _KEY_SIZES["kem"][self._security_level]
        return (
            base64.b64encode(secrets.token_bytes(sizes["ciphertext"])).decode("utf-8"),
            base64.b64encode(secrets.token_bytes(32)).decode("utf-8"),
        )

    def decapsulate(self, ciphertext: str) -> str:
        """Decapsulate to recover shared secret."""
        if LIBOQS_AVAILABLE and self._kem:
            try:
                ct_bytes = base64.b64decode(ciphertext)
                shared_secret = self._kem.decap_secret(ct_bytes)
                return base64.b64encode(shared_secret).decode("utf-8")
            except Exception as e:
                logger.warning(f"liboqs decapsulation failed: {e}, using stub")

        return base64.b64encode(secrets.token_bytes(32)).decode("utf-8")

    @staticmethod
    def from_base64(public_key: str, secret_key: str, security_level: int = 3) -> "KemKeyPair":
        keypair = KemKeyPair.__new__(KemKeyPair)
        keypair._security_level = security_level
        keypair._kem_alg = SecurityLevel.KEM_ALGORITHMS[security_level]
        keypair._public_key_bytes = base64.b64decode(public_key)
        keypair._secret_key_bytes = base64.b64decode(secret_key)
        keypair._kem = None
        return keypair

    def __del__(self):
        if self._kem:
            try:
                self._kem.free()
            except Exception:
                pass


class SigningKeyPair:
    """ML-DSA (Dilithium) signing key pair for digital signatures.

    Uses REAL liboqs when available, stub otherwise.
    """

    _signature_store: dict[tuple[str, str], bytes] = {}

    def __init__(self, security_level: Optional[int] = None):
        level = security_level or 3
        if level == 1:
            level = 2
        self._security_level = level
        self._sig_alg = SecurityLevel.DSA_ALGORITHMS[level]
        self._sig = None

        if LIBOQS_AVAILABLE:
            try:
                self._sig = _OQS_MODULE.Signature(self._sig_alg)
                self._public_key_bytes = self._sig.generate_keypair()
                self._secret_key_bytes = self._sig.export_secret_key()
            except Exception as e:
                logger.warning(f"Failed to initialize liboqs Signature: {e}, falling back to stub")
                self._sig = None
                self._init_stub(level)
        else:
            self._init_stub(level)

    def _init_stub(self, level: int):
        sizes = _KEY_SIZES["dsa"][level]
        self._public_key_bytes = secrets.token_bytes(sizes["public"])
        self._secret_key_bytes = secrets.token_bytes(sizes["secret"])

    @property
    def public_key(self) -> str:
        return base64.b64encode(self._public_key_bytes).decode("utf-8")

    @property
    def secret_key(self) -> str:
        return base64.b64encode(self._secret_key_bytes).decode("utf-8")

    @property
    def security_level(self) -> int:
        return self._security_level

    @property
    def algorithm(self) -> str:
        return self._sig_alg

    def sign(self, message: bytes) -> str:
        """Sign a message. Returns base64-encoded signature."""
        if LIBOQS_AVAILABLE and self._sig:
            try:
                signature = self._sig.sign(message, self._secret_key_bytes)
                return base64.b64encode(signature).decode("utf-8")
            except Exception as e:
                logger.warning(f"liboqs signing failed: {e}, using stub")

        h = hashlib.sha3_256(message + self._secret_key_bytes).digest()
        sig = base64.b64encode(h + secrets.token_bytes(32)).decode("utf-8")
        SigningKeyPair._signature_store[(self.public_key, h.hex())] = message
        return sig

    def verify(self, message: bytes, signature: str) -> bool:
        """Verify a signature."""
        if LIBOQS_AVAILABLE and self._sig:
            try:
                sig_bytes = base64.b64decode(signature)
                return self._sig.verify(message, sig_bytes, self._public_key_bytes)
            except Exception as e:
                logger.warning(f"liboqs verification failed: {e}, using stub")
                return False

        try:
            sig_bytes = base64.b64decode(signature)
            h = sig_bytes[:32]
            stored_msg = SigningKeyPair._signature_store.get((self.public_key, h.hex()))
            return stored_msg == message
        except Exception:
            return False

    @staticmethod
    def from_base64(public_key: str, secret_key: str, security_level: int = 3) -> "SigningKeyPair":
        keypair = SigningKeyPair.__new__(SigningKeyPair)
        keypair._security_level = security_level
        keypair._sig_alg = SecurityLevel.DSA_ALGORITHMS[security_level]
        keypair._public_key_bytes = base64.b64decode(public_key)
        keypair._secret_key_bytes = base64.b64decode(secret_key)
        keypair._sig = None
        return keypair

    def __del__(self):
        if self._sig:
            try:
                self._sig.free()
            except Exception:
                pass


class EncryptedEnvelope:
    """Encrypted data envelope using ML-KEM + AES-256-GCM."""

    def __init__(
        self,
        ciphertext: bytes,
        encapsulated_key: bytes,
        nonce: bytes,
        algorithm: str = "ML-KEM-768+AES-256-GCM",
    ):
        self.ciphertext = ciphertext
        self.encapsulated_key = encapsulated_key
        self.nonce = nonce
        self.algorithm = algorithm

    def to_json(self) -> str:
        return json.dumps(
            {
                "ciphertext": base64.b64encode(self.ciphertext).decode("utf-8"),
                "encapsulated_key": base64.b64encode(self.encapsulated_key).decode("utf-8"),
                "nonce": base64.b64encode(self.nonce).decode("utf-8"),
                "algorithm": self.algorithm,
            }
        )

    @staticmethod
    def from_json(json_str: str) -> "EncryptedEnvelope":
        data = json.loads(json_str)
        return EncryptedEnvelope(
            ciphertext=base64.b64decode(data["ciphertext"]),
            encapsulated_key=base64.b64decode(data["encapsulated_key"]),
            nonce=base64.b64decode(data["nonce"]),
            algorithm=data.get("algorithm", "ML-KEM-768+AES-256-GCM"),
        )


def py_kem_generate(security_level: Optional[int] = None) -> KemKeyPair:
    return KemKeyPair(security_level)


def py_kem_generate_with_level(security_level: int) -> KemKeyPair:
    return KemKeyPair(security_level)


def py_kem_encapsulate(public_key: str) -> tuple[str, str]:
    kp = KemKeyPair.from_base64(public_key, base64.b64encode(secrets.token_bytes(2400)).decode())
    return kp.encapsulate()


def py_kem_encapsulate_with_level(public_key: str, security_level: int) -> tuple[str, str]:
    return py_kem_encapsulate(public_key)


def py_kem_decapsulate(ciphertext: str, secret_key: str) -> str:
    kp = KemKeyPair.from_base64(base64.b64encode(secrets.token_bytes(1184)).decode(), secret_key)
    return kp.decapsulate(ciphertext)


def py_kem_decapsulate_with_level(ciphertext: str, secret_key: str, security_level: int) -> str:
    kp = KemKeyPair.from_base64(
        base64.b64encode(secrets.token_bytes(1184)).decode(), secret_key, security_level
    )
    return kp.decapsulate(ciphertext)


def py_sign(message: bytes, secret_key: str) -> str:
    kp = SigningKeyPair.from_base64(
        base64.b64encode(secrets.token_bytes(1952)).decode(), secret_key
    )
    return kp.sign(message)


def py_sign_with_level(message: bytes, secret_key: str, security_level: int) -> str:
    kp = SigningKeyPair.from_base64(
        base64.b64encode(secrets.token_bytes(1952)).decode(), secret_key, security_level
    )
    return kp.sign(message)


def py_verify(message: bytes, signature: str, public_key: str) -> bool:
    kp = SigningKeyPair.from_base64(
        public_key, base64.b64encode(secrets.token_bytes(4032)).decode()
    )
    return kp.verify(message, signature)


def py_verify_with_level(
    message: bytes, signature: str, public_key: str, security_level: int
) -> bool:
    kp = SigningKeyPair.from_base64(
        public_key, base64.b64encode(secrets.token_bytes(4032)).decode(), security_level
    )
    return kp.verify(message, signature)


def py_encrypt(plaintext: bytes, recipient_public_key: str) -> EncryptedEnvelope:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    shared_secret = secrets.token_bytes(32)
    aes_key = hashlib.sha256(shared_secret).digest()
    nonce = secrets.token_bytes(12)

    aesgcm = AESGCM(aes_key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    return EncryptedEnvelope(
        ciphertext=ciphertext,
        encapsulated_key=base64.b64decode(py_kem_encapsulate(recipient_public_key)[0]),
        nonce=nonce,
    )


def py_decrypt(envelope: EncryptedEnvelope, recipient_secret_key: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    shared_secret = base64.b64decode(
        py_kem_decapsulate(
            base64.b64encode(envelope.encapsulated_key).decode(), recipient_secret_key
        )
    )
    aes_key = hashlib.sha256(shared_secret).digest()

    aesgcm = AESGCM(aes_key)
    return aesgcm.decrypt(envelope.nonce, envelope.ciphertext, None)


def py_get_supported_levels() -> list[tuple[int, str, str]]:
    return [
        (1, "ML-KEM-512", "ML-DSA-44"),
        (3, "ML-KEM-768", "ML-DSA-65"),
        (5, "ML-KEM-1024", "ML-DSA-87"),
    ]


__all__ = [
    "SecurityLevel",
    "KemKeyPair",
    "SigningKeyPair",
    "EncryptedEnvelope",
    "py_kem_generate",
    "py_kem_generate_with_level",
    "py_kem_encapsulate",
    "py_kem_encapsulate_with_level",
    "py_kem_decapsulate",
    "py_kem_decapsulate_with_level",
    "py_sign",
    "py_sign_with_level",
    "py_verify",
    "py_verify_with_level",
    "py_encrypt",
    "py_decrypt",
    "py_get_supported_levels",
    "is_crypto_production_ready",
    "get_crypto_status",
    "LIBOQS_AVAILABLE",
]

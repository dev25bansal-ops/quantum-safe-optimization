"""Quantum-Safe Cryptography Module - Stub/Development Implementation.

This module provides a Python-only fallback when the Rust-based
quantum_safe_crypto module is not available. It simulates the API
for development and testing purposes.

For production, use the Rust module built from crypto/ directory.
"""

import base64
import hashlib
import secrets
from typing import Optional


class SecurityLevel:
    def __init__(self, level: int):
        if level not in (1, 2, 3, 5):
            raise ValueError("Invalid security level. Use 1, 2, 3, or 5")
        self.level = level

    @property
    def kem_algorithm(self) -> str:
        return {1: "ML-KEM-512", 3: "ML-KEM-768", 5: "ML-KEM-1024"}.get(self.level, "ML-KEM-768")

    @property
    def dsa_algorithm(self) -> str:
        return {1: "ML-DSA-44", 2: "ML-DSA-44", 3: "ML-DSA-65", 5: "ML-DSA-87"}.get(
            self.level, "ML-DSA-65"
        )

    @staticmethod
    def level1():
        return SecurityLevel(1)

    @staticmethod
    def level3():
        return SecurityLevel(3)

    @staticmethod
    def level5():
        return SecurityLevel(5)


class KemKeyPair:
    """ML-KEM key pair for key encapsulation."""

    _signatures: dict = {}

    def __init__(self, security_level: Optional[int] = None):
        self._security_level = security_level or 3
        self._public_key = base64.b64encode(secrets.token_bytes(1184)).decode("utf-8")
        self._secret_key = base64.b64encode(secrets.token_bytes(2400)).decode("utf-8")

    @property
    def public_key(self) -> str:
        return self._public_key

    @property
    def secret_key(self) -> str:
        return self._secret_key

    @property
    def security_level(self) -> int:
        return self._security_level

    @property
    def algorithm(self) -> str:
        return {1: "ML-KEM-512", 3: "ML-KEM-768", 5: "ML-KEM-1024"}.get(
            self._security_level, "ML-KEM-768"
        )

    @staticmethod
    def from_base64(public_key: str, secret_key: str) -> "KemKeyPair":
        keypair = KemKeyPair.__new__(KemKeyPair)
        keypair._public_key = public_key
        keypair._secret_key = secret_key
        keypair._security_level = 3
        return keypair


class SigningKeyPair:
    """ML-DSA signing key pair for digital signatures."""

    _signatures: dict = {}

    def __init__(self, security_level: Optional[int] = None):
        level = security_level or 3
        if level == 1:
            level = 2
        self._security_level = level
        key_size = {2: 1952, 3: 2496, 5: 4032}.get(level, 2496)
        self._public_key = base64.b64encode(secrets.token_bytes(key_size // 8)).decode("utf-8")
        self._secret_key = base64.b64encode(secrets.token_bytes(key_size)).decode("utf-8")

    @property
    def public_key(self) -> str:
        return self._public_key

    @property
    def secret_key(self) -> str:
        return self._secret_key

    @property
    def security_level(self) -> int:
        return self._security_level

    @property
    def algorithm(self) -> str:
        return {2: "ML-DSA-44", 3: "ML-DSA-65", 5: "ML-DSA-87"}.get(
            self._security_level, "ML-DSA-65"
        )

    def sign(self, message: bytes) -> str:
        h = hashlib.sha3_256(message + base64.b64decode(self._secret_key)).digest()
        sig = base64.b64encode(h + secrets.token_bytes(32)).decode("utf-8")
        SigningKeyPair._signatures[(self._public_key, h.hex())] = message
        return sig

    def verify(self, message: bytes, signature: str) -> bool:
        try:
            sig_bytes = base64.b64decode(signature)
            h = sig_bytes[:32]
            stored_msg = SigningKeyPair._signatures.get((self._public_key, h.hex()))
            return stored_msg == message
        except Exception:
            return False

    @staticmethod
    def from_base64(public_key: str, secret_key: str) -> "SigningKeyPair":
        keypair = SigningKeyPair.__new__(SigningKeyPair)
        keypair._public_key = public_key
        keypair._secret_key = secret_key
        keypair._security_level = 3
        return keypair


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
        import json

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
        import json

        data = json.loads(json_str)
        return EncryptedEnvelope(
            ciphertext=base64.b64decode(data["ciphertext"]),
            encapsulated_key=base64.b64decode(data["encapsulated_key"]),
            nonce=base64.b64decode(data["nonce"]),
        )


def py_kem_generate(security_level: Optional[int] = None) -> KemKeyPair:
    return KemKeyPair(security_level)


def py_kem_generate_with_level(security_level: int) -> KemKeyPair:
    return KemKeyPair(security_level)


def py_kem_encapsulate(public_key: str) -> tuple[str, str]:
    ciphertext = base64.b64encode(secrets.token_bytes(1152)).decode("utf-8")
    shared_secret = base64.b64encode(secrets.token_bytes(32)).decode("utf-8")
    return (ciphertext, shared_secret)


def py_kem_encapsulate_with_level(public_key: str, security_level: int) -> tuple[str, str]:
    return py_kem_encapsulate(public_key)


def py_kem_decapsulate(ciphertext: str, secret_key: str) -> str:
    return base64.b64encode(secrets.token_bytes(32)).decode("utf-8")


def py_kem_decapsulate_with_level(ciphertext: str, secret_key: str, security_level: int) -> str:
    return py_kem_decapsulate(ciphertext, secret_key)


def py_sign(message: bytes, secret_key: str) -> str:
    return base64.b64encode(hashlib.sha3_256(message).digest() + secrets.token_bytes(32)).decode(
        "utf-8"
    )


def py_sign_with_level(message: bytes, secret_key: str, security_level: int) -> str:
    return py_sign(message, secret_key)


def py_verify(message: bytes, signature: str, public_key: str) -> bool:
    try:
        sig_bytes = base64.b64decode(signature)
        h = sig_bytes[:32]
        stored_msg = SigningKeyPair._signatures.get((public_key, h.hex()))
        return stored_msg == message
    except Exception:
        return False


def py_verify_with_level(
    message: bytes, signature: str, public_key: str, security_level: int
) -> bool:
    return py_verify(message, signature, public_key)


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
    return envelope.ciphertext


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
]

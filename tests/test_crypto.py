"""
Tests for Quantum-Safe Cryptography Module.

Tests the PQC (Post-Quantum Cryptography) integration from Python:
- ML-KEM-768 (Key Encapsulation)
- ML-DSA-65 (Digital Signatures)
"""

import pytest

# Import the qsop PQC module
from qsop.crypto.pqc import (
    KEMAlgorithm,
    KEMKeyPair,
    SignatureAlgorithm,
    SignatureKeyPair,
    get_kem,
    get_signature_scheme,
    reset_providers,
)


class TestMLKEM768:
    """Test ML-KEM-768 (CRYSTALS-Kyber) key encapsulation."""

    def setup_method(self):
        """Reset providers before each test."""
        reset_providers()

    def test_kem_keypair_generation(self):
        """Test KEM keypair generation."""
        kem = get_kem(KEMAlgorithm.KYBER768)
        public_key, secret_key = kem.keygen()

        # Verify keys exist
        assert public_key is not None
        assert secret_key is not None

        # ML-KEM-768 public key is 1184 bytes
        assert len(public_key) > 1000
        assert len(secret_key) > 2000

    def test_kem_keypair_uniqueness(self):
        """Test that each keypair is unique."""
        kem = get_kem(KEMAlgorithm.KYBER768)
        public_key1, secret_key1 = kem.keygen()
        public_key2, secret_key2 = kem.keygen()

        assert public_key1 != public_key2
        assert secret_key1 != secret_key2

    def test_kem_encapsulation(self):
        """Test key encapsulation produces ciphertext and shared secret."""
        kem = get_kem(KEMAlgorithm.KYBER768)
        public_key, _ = kem.keygen()

        ciphertext, shared_secret = kem.encapsulate(public_key)

        # Verify outputs exist and have reasonable sizes
        assert ciphertext is not None
        assert shared_secret is not None
        assert len(ciphertext) > 1000  # ~1088 bytes for ML-KEM-768
        assert len(shared_secret) > 30  # 32 bytes

    def test_kem_decapsulation(self):
        """Test that decapsulation recovers the same shared secret."""
        kem = get_kem(KEMAlgorithm.KYBER768)
        public_key, secret_key = kem.keygen()

        # Encapsulate
        ciphertext, shared_secret_enc = kem.encapsulate(public_key)

        # Decapsulate
        shared_secret_dec = kem.decapsulate(ciphertext, secret_key)

        # Verify shared secrets match
        assert shared_secret_enc == shared_secret_dec


class TestMLDSA65:
    """Test ML-DSA-65 (CRYSTALS-Dilithium) digital signatures."""

    def setup_method(self):
        """Reset providers before each test."""
        reset_providers()

    def test_signing_keypair_generation(self):
        """Test signing keypair generation."""
        sig = get_signature_scheme(SignatureAlgorithm.DILITHIUM3)
        public_key, secret_key = sig.keygen()

        assert public_key is not None
        assert secret_key is not None

        # ML-DSA-65 public key is 1312 bytes, secret key is 2528 bytes
        assert len(public_key) > 1000
        assert len(secret_key) > 2000

    def test_signing_keypair_uniqueness(self):
        """Test that each signing keypair is unique."""
        sig = get_signature_scheme(SignatureAlgorithm.DILITHIUM3)
        public_key1, secret_key1 = sig.keygen()
        public_key2, secret_key2 = sig.keygen()

        assert public_key1 != public_key2
        assert secret_key1 != secret_key2

    def test_message_signing(self):
        """Test message signing produces signature."""
        sig = get_signature_scheme(SignatureAlgorithm.DILITHIUM3)
        _, secret_key = sig.keygen()

        message = b"Test message for signing"
        signature = sig.sign(message, secret_key)

        assert signature is not None
        # ML-DSA-65 signature is always 2420 bytes
        assert len(signature) > 2000

    def test_signature_verification(self):
        """Test that verification succeeds with correct signature."""
        sig = get_signature_scheme(SignatureAlgorithm.DILITHIUM3)
        public_key, secret_key = sig.keygen()

        message = b"Test message for signing"
        signature = sig.sign(message, secret_key)

        # Verify should succeed
        is_valid = sig.verify(message, signature, public_key)
        assert is_valid is True

    def test_signature_verification_wrong_message_fails(self):
        """Test that verification fails with wrong message."""
        sig = get_signature_scheme(SignatureAlgorithm.DILITHIUM3)
        public_key, secret_key = sig.keygen()

        message = b"Test message for signing"
        signature = sig.sign(message, secret_key)

        # Verify with wrong message should fail
        is_valid = sig.verify(b"Wrong message", signature, public_key)
        assert is_valid is False

    def test_signature_verification_wrong_key_fails(self):
        """Test that verification fails with wrong public key."""
        sig = get_signature_scheme(SignatureAlgorithm.DILITHIUM3)
        public_key1, secret_key1 = sig.keygen()
        public_key2, _ = sig.keygen()

        message = b"Test message for signing"
        signature = sig.sign(message, secret_key1)

        # Verify with wrong public key should fail
        is_valid = sig.verify(message, signature, public_key2)
        assert is_valid is False


class TestKEMKeyPair:
    """Test KEMKeyPair dataclass."""

    def test_keypair_equals_self(self):
        """Test that keypair equals itself."""
        kem = get_kem(KEMAlgorithm.KYBER768)
        public_key, secret_key = kem.keygen()

        keypair = KEMKeyPair(
            public_key=public_key,
            secret_key=secret_key,
            algorithm=KEMAlgorithm.KYBER768,
        )

        assert keypair == keypair

    def test_keypair_not_equals_different(self):
        """Test that different keypairs are not equal."""
        kem = get_kem(KEMAlgorithm.KYBER768)
        keypair1 = KEMKeyPair(
            public_key=b"pk1",
            secret_key=b"sk1",
            algorithm=KEMAlgorithm.KYBER768,
        )
        keypair2 = KEMKeyPair(
            public_key=b"pk2",
            secret_key=b"sk2",
            algorithm=KEMAlgorithm.KYBER768,
        )

        assert keypair1 != keypair2

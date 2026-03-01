"""Tests for envelope encryption."""

import pytest

from qsop.crypto.envelopes.envelope import (
    EncryptedEnvelope,
    EnvelopeDecryptor,
    EnvelopeEncryptor,
    RecipientInfo,
)
from qsop.crypto.pqc import KEMAlgorithm, get_kem


class TestEnvelopeEncryption:
    """Test envelope encryption and decryption."""

    @pytest.fixture
    def keypair(self):
        """Generate a test keypair."""
        kem = get_kem(KEMAlgorithm.KYBER768)
        return kem.keygen()  # Returns (public_key, secret_key)

    def test_encrypt_decrypt_roundtrip(self, keypair):
        """Test basic encrypt/decrypt cycle."""
        public_key, private_key = keypair
        plaintext = b"Hello, quantum-safe world!"

        # Encrypt
        encryptor = EnvelopeEncryptor(kem_algorithm=KEMAlgorithm.KYBER768)
        recipient = RecipientInfo(public_key=public_key, key_id="test-key")
        envelope = encryptor.encrypt(plaintext, recipients=[recipient])

        assert envelope is not None
        assert envelope.ciphertext != plaintext
        assert len(envelope.recipients) == 1

        # Decrypt
        decryptor = EnvelopeDecryptor()
        decrypted = decryptor.decrypt(envelope, secret_key=private_key, key_id="test-key")

        assert decrypted == plaintext

    def test_encrypt_with_aad(self, keypair):
        """Test encryption with additional authenticated data."""
        public_key, private_key = keypair
        plaintext = b"Sensitive optimization data"

        encryptor = EnvelopeEncryptor(kem_algorithm=KEMAlgorithm.KYBER768)
        recipient = RecipientInfo(public_key=public_key, key_id="test-key")
        envelope = encryptor.encrypt(plaintext, recipients=[recipient])

        decryptor = EnvelopeDecryptor()
        decrypted = decryptor.decrypt(envelope, secret_key=private_key, key_id="test-key")

        assert decrypted == plaintext

    def test_envelope_serialization(self, keypair):
        """Test envelope can be serialized and deserialized."""
        public_key, private_key = keypair
        plaintext = b"Test data"

        encryptor = EnvelopeEncryptor(kem_algorithm=KEMAlgorithm.KYBER768)
        recipient = RecipientInfo(public_key=public_key, key_id="test-key")
        envelope = encryptor.encrypt(plaintext, recipients=[recipient])

        # Serialize
        envelope_dict = envelope.to_dict()
        assert isinstance(envelope_dict, dict)
        assert "ciphertext" in envelope_dict

        # Deserialize
        restored = EncryptedEnvelope.from_dict(envelope_dict)

        # Decrypt restored envelope
        decryptor = EnvelopeDecryptor()
        decrypted = decryptor.decrypt(restored, secret_key=private_key, key_id="test-key")

        assert decrypted == plaintext

    def test_tampered_ciphertext_fails(self, keypair):
        """Test that tampered ciphertext is detected."""
        public_key, private_key = keypair
        plaintext = b"Original data"

        encryptor = EnvelopeEncryptor(kem_algorithm=KEMAlgorithm.KYBER768)
        recipient = RecipientInfo(public_key=public_key, key_id="test-key")
        envelope = encryptor.encrypt(plaintext, recipients=[recipient])

        # Tamper with ciphertext
        tampered_ct = bytearray(envelope.ciphertext)
        tampered_ct[0] ^= 0xFF

        # Create tampered envelope
        tampered_envelope = EncryptedEnvelope(
            metadata=envelope.metadata,
            recipients=envelope.recipients,
            ciphertext=bytes(tampered_ct),
            nonce=envelope.nonce,
        )

        decryptor = EnvelopeDecryptor()

        with pytest.raises(Exception):  # Decryption should fail
            decryptor.decrypt(tampered_envelope, secret_key=private_key, key_id="test-key")

    def test_different_algorithms(self):
        """Test encryption with different KEM algorithms."""
        algorithms = [
            KEMAlgorithm.KYBER512,
            KEMAlgorithm.KYBER768,
            KEMAlgorithm.KYBER1024,
        ]

        plaintext = b"Test data for different algorithms"

        for alg in algorithms:
            kem = get_kem(alg)
            public_key, private_key = kem.keygen()

            encryptor = EnvelopeEncryptor(kem_algorithm=alg)
            recipient = RecipientInfo(public_key=public_key, key_id="test")
            envelope = encryptor.encrypt(plaintext, recipients=[recipient])

            decryptor = EnvelopeDecryptor()
            decrypted = decryptor.decrypt(envelope, secret_key=private_key, key_id="test")

            assert decrypted == plaintext, f"Failed for {alg}"

    def test_large_plaintext(self, keypair):
        """Test encryption of large data."""
        public_key, private_key = keypair

        # 1 MB of data
        plaintext = b"x" * (1024 * 1024)

        encryptor = EnvelopeEncryptor(kem_algorithm=KEMAlgorithm.KYBER768)
        recipient = RecipientInfo(public_key=public_key, key_id="test-key")
        envelope = encryptor.encrypt(plaintext, recipients=[recipient])

        decryptor = EnvelopeDecryptor()
        decrypted = decryptor.decrypt(envelope, secret_key=private_key, key_id="test-key")

        assert decrypted == plaintext
        assert len(decrypted) == 1024 * 1024

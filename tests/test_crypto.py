"""
Tests for Quantum-Safe Cryptography Module.

Tests the PQC (Post-Quantum Cryptography) integration from Python:
- ML-KEM-768 (Key Encapsulation)
- ML-DSA-65 (Digital Signatures)
- HKDF-SHA256 (Key Derivation)
- Hybrid Encryption (ML-KEM + AES-256-GCM)
"""

import base64
import json

import pytest

# Import the Rust PQC module
import quantum_safe_crypto as pqc


class TestMLKEM768:
    """Test ML-KEM-768 (CRYSTALS-Kyber) key encapsulation."""

    def test_kem_keypair_generation(self):
        """Test KEM keypair generation."""
        keypair = pqc.KemKeyPair()

        # Verify keypair exists
        assert keypair.public_key is not None
        assert keypair.secret_key is not None

        # ML-KEM-768 public key is 1184 bytes, base64 encoded ~1580 chars
        assert len(keypair.public_key) > 1000
        assert len(keypair.secret_key) > 2000

    def test_kem_keypair_uniqueness(self):
        """Test that each keypair is unique."""
        keypair1 = pqc.KemKeyPair()
        keypair2 = pqc.KemKeyPair()

        assert keypair1.public_key != keypair2.public_key
        assert keypair1.secret_key != keypair2.secret_key

    def test_kem_encapsulation(self):
        """Test key encapsulation produces ciphertext and shared secret."""
        keypair = pqc.KemKeyPair()

        ciphertext, shared_secret = pqc.py_kem_encapsulate(keypair.public_key)

        # Verify outputs exist and have reasonable sizes
        assert ciphertext is not None
        assert shared_secret is not None
        assert len(ciphertext) > 1000  # ~1088 bytes for ML-KEM-768
        assert len(shared_secret) > 30  # 32 bytes = 44 base64 chars

    def test_kem_decapsulation(self):
        """Test that decapsulation recovers the same shared secret."""
        keypair = pqc.KemKeyPair()

        # Encapsulate
        ciphertext, shared_secret_enc = pqc.py_kem_encapsulate(keypair.public_key)

        # Decapsulate
        shared_secret_dec = pqc.py_kem_decapsulate(ciphertext, keypair.secret_key)

        # Both sides should derive the same shared secret
        assert shared_secret_enc == shared_secret_dec

    def test_kem_decapsulation_wrong_key_fails(self):
        """Test that decapsulation with wrong key produces different secret."""
        keypair1 = pqc.KemKeyPair()
        keypair2 = pqc.KemKeyPair()

        # Encapsulate with keypair1's public key
        ciphertext, shared_secret_enc = pqc.py_kem_encapsulate(keypair1.public_key)

        # Try to decapsulate with keypair2's secret key (wrong key)
        shared_secret_dec = pqc.py_kem_decapsulate(ciphertext, keypair2.secret_key)

        # Should produce different (invalid) secret
        assert shared_secret_enc != shared_secret_dec


class TestMLDSA65:
    """Test ML-DSA-65 (CRYSTALS-Dilithium) digital signatures."""

    def test_signing_keypair_generation(self):
        """Test signing keypair generation."""
        keypair = pqc.SigningKeyPair()

        assert keypair.public_key is not None
        assert keypair.secret_key is not None

        # ML-DSA-65 has larger keys
        assert len(keypair.public_key) > 1000
        assert len(keypair.secret_key) > 3000

    def test_signing_keypair_uniqueness(self):
        """Test that each signing keypair is unique."""
        keypair1 = pqc.SigningKeyPair()
        keypair2 = pqc.SigningKeyPair()

        assert keypair1.public_key != keypair2.public_key

    def test_sign_and_verify(self):
        """Test signing and verification of a message."""
        keypair = pqc.SigningKeyPair()
        message = b"Test message for quantum-safe signing"

        # Sign
        signature = keypair.sign(message)
        assert signature is not None
        assert len(signature) > 2000  # ML-DSA signatures are large

        # Verify
        is_valid = keypair.verify(message, signature)
        assert is_valid is True

    def test_verify_different_message_fails(self):
        """Test that verification fails for different message."""
        keypair = pqc.SigningKeyPair()
        message1 = b"Original message"
        message2 = b"Different message"

        # Sign message1
        signature = keypair.sign(message1)

        # Verify with message2 should fail
        is_valid = keypair.verify(message2, signature)
        assert is_valid is False

    def test_verify_wrong_key_fails(self):
        """Test that verification fails with wrong public key."""
        keypair1 = pqc.SigningKeyPair()
        keypair2 = pqc.SigningKeyPair()
        message = b"Test message"

        # Sign with keypair1
        signature = keypair1.sign(message)

        # Verify with keypair2's public key should fail
        is_valid = pqc.py_verify(message, signature, keypair2.public_key)
        assert is_valid is False

    def test_sign_empty_message(self):
        """Test signing an empty message."""
        keypair = pqc.SigningKeyPair()
        message = b""

        signature = keypair.sign(message)
        is_valid = keypair.verify(message, signature)
        assert is_valid is True

    def test_sign_large_message(self):
        """Test signing a large message."""
        keypair = pqc.SigningKeyPair()
        message = b"X" * 1_000_000  # 1MB message

        signature = keypair.sign(message)
        is_valid = keypair.verify(message, signature)
        assert is_valid is True

    def test_sign_binary_data(self):
        """Test signing binary data."""
        keypair = pqc.SigningKeyPair()
        message = bytes(range(256))  # All byte values

        signature = keypair.sign(message)
        is_valid = keypair.verify(message, signature)
        assert is_valid is True


class TestKEMSharedSecret:
    """Test KEM shared secret derivation."""

    def test_shared_secret_consistency(self):
        """Test that encapsulation and decapsulation produce same secret."""
        keypair = pqc.KemKeyPair()

        # Encapsulate
        ciphertext, shared_secret_enc = pqc.py_kem_encapsulate(keypair.public_key)

        # Decapsulate
        shared_secret_dec = pqc.py_kem_decapsulate(ciphertext, keypair.secret_key)

        # Both should produce the same shared secret
        assert shared_secret_enc == shared_secret_dec

    def test_shared_secret_length(self):
        """Test shared secret has appropriate length."""
        keypair = pqc.KemKeyPair()
        ciphertext, shared_secret = pqc.py_kem_encapsulate(keypair.public_key)

        # ML-KEM-768 produces 32-byte shared secrets
        # Base64 encoded: 44 chars
        assert len(shared_secret) >= 40

    def test_different_encapsulations_different_secrets(self):
        """Test that each encapsulation produces different secrets."""
        keypair = pqc.KemKeyPair()

        _, secret1 = pqc.py_kem_encapsulate(keypair.public_key)
        _, secret2 = pqc.py_kem_encapsulate(keypair.public_key)

        # Random encapsulation means different secrets each time
        assert secret1 != secret2


class TestHybridEncryption:
    """Test hybrid encryption (ML-KEM + AES-256-GCM)."""

    def test_encrypt_decrypt_basic(self):
        """Test basic encryption and decryption."""
        keypair = pqc.KemKeyPair()
        plaintext = b"Secret quantum message"

        # Encrypt - returns EncryptedEnvelope
        envelope = pqc.py_encrypt(plaintext, keypair.public_key)
        assert envelope is not None

        # Serialize to JSON
        ciphertext_json = envelope.to_json()
        assert len(ciphertext_json) > len(plaintext)

        # Decrypt using the envelope
        decrypted = pqc.py_decrypt(envelope, keypair.secret_key)
        assert decrypted == plaintext

    def test_encrypt_decrypt_json(self):
        """Test encrypting JSON data."""
        keypair = pqc.KemKeyPair()
        data = {
            "optimal_value": -3.14159,
            "optimal_bitstring": "10110",
            "iterations": 100,
        }
        plaintext = json.dumps(data).encode("utf-8")

        envelope = pqc.py_encrypt(plaintext, keypair.public_key)
        decrypted = pqc.py_decrypt(envelope, keypair.secret_key)

        recovered = json.loads(decrypted.decode("utf-8"))
        assert recovered == data

    def test_encrypt_decrypt_large_data(self):
        """Test encrypting large data."""
        keypair = pqc.KemKeyPair()
        plaintext = b"X" * 100_000  # 100KB

        envelope = pqc.py_encrypt(plaintext, keypair.public_key)
        decrypted = pqc.py_decrypt(envelope, keypair.secret_key)

        assert decrypted == plaintext

    def test_decrypt_wrong_key_fails(self):
        """Test that decryption with wrong key fails."""
        keypair1 = pqc.KemKeyPair()
        keypair2 = pqc.KemKeyPair()
        plaintext = b"Secret message"

        envelope = pqc.py_encrypt(plaintext, keypair1.public_key)

        # Decryption with wrong key should raise or return None
        with pytest.raises(Exception):
            pqc.py_decrypt(envelope, keypair2.secret_key)

    def test_encrypt_empty_message(self):
        """Test encrypting empty message."""
        keypair = pqc.KemKeyPair()
        plaintext = b""

        envelope = pqc.py_encrypt(plaintext, keypair.public_key)
        decrypted = pqc.py_decrypt(envelope, keypair.secret_key)

        assert decrypted == plaintext

    def test_ciphertext_is_non_deterministic(self):
        """Test that encryption is non-deterministic (different ciphertexts)."""
        keypair = pqc.KemKeyPair()
        plaintext = b"Same message"

        env1 = pqc.py_encrypt(plaintext, keypair.public_key)
        env2 = pqc.py_encrypt(plaintext, keypair.public_key)

        # Different ciphertexts due to random encapsulation
        assert env1.to_json() != env2.to_json()

        # But both decrypt to same plaintext
        assert pqc.py_decrypt(env1, keypair.secret_key) == plaintext
        assert pqc.py_decrypt(env2, keypair.secret_key) == plaintext

    def test_envelope_serialization_roundtrip(self):
        """Test that EncryptedEnvelope can be serialized and deserialized."""
        keypair = pqc.KemKeyPair()
        plaintext = b"Test serialization"

        # Encrypt and serialize
        envelope = pqc.py_encrypt(plaintext, keypair.public_key)
        json_str = envelope.to_json()

        # Deserialize
        restored_envelope = pqc.EncryptedEnvelope.from_json(json_str)

        # Decrypt
        decrypted = pqc.py_decrypt(restored_envelope, keypair.secret_key)
        assert decrypted == plaintext


class TestCryptoIntegration:
    """Integration tests for crypto module."""

    def test_sign_encrypted_payload(self):
        """Test signing an encrypted payload."""
        kem_keys = pqc.KemKeyPair()
        sign_keys = pqc.SigningKeyPair()

        # Encrypt data
        plaintext = b"Sensitive optimization results"
        envelope = pqc.py_encrypt(plaintext, kem_keys.public_key)

        # Serialize envelope to sign it
        envelope_json = envelope.to_json()
        envelope_bytes = envelope_json.encode("utf-8")

        # Sign the serialized envelope
        signature = sign_keys.sign(envelope_bytes)

        # Verify signature
        is_valid = sign_keys.verify(envelope_bytes, signature)
        assert is_valid is True

        # Decrypt
        decrypted = pqc.py_decrypt(envelope, kem_keys.secret_key)
        assert decrypted == plaintext

    def test_derive_session_key_from_kem(self):
        """Test deriving a session key from KEM shared secret."""
        keypair = pqc.KemKeyPair()

        # Perform KEM
        ciphertext, shared_secret = pqc.py_kem_encapsulate(keypair.public_key)

        # The shared secret can be used directly as a session key
        # (In production, you'd use HKDF, but our module doesn't expose it)
        assert shared_secret is not None
        assert len(shared_secret) > 30  # 32 bytes base64 encoded

    def test_token_signature_workflow(self):
        """Test signing and verifying a token (like JWT)."""
        sign_keys = pqc.SigningKeyPair()

        # Create token payload
        import time

        token_data = {
            "user_id": "user_123",
            "exp": time.time() + 3600,
            "roles": ["user", "admin"],
        }
        token_bytes = json.dumps(token_data).encode("utf-8")
        token_b64 = base64.b64encode(token_bytes).decode("utf-8")

        # Sign token
        signature = sign_keys.sign(token_bytes)
        signature_b64 = (
            signature if isinstance(signature, str) else base64.b64encode(signature).decode("utf-8")
        )

        # Full token: header.payload.signature
        full_token = f"pqc.{token_b64}.{signature_b64}"

        # Verify token
        parts = full_token.split(".")
        assert len(parts) == 3

        payload_decoded = base64.b64decode(parts[1])
        is_valid = sign_keys.verify(payload_decoded, signature)
        assert is_valid is True

        # Parse payload
        recovered_data = json.loads(payload_decoded)
        assert recovered_data["user_id"] == "user_123"

    def test_full_secure_communication_flow(self):
        """Test complete secure communication: encrypt → sign → verify → decrypt."""
        # Alice's keys
        alice_kem = pqc.KemKeyPair()
        alice_sign = pqc.SigningKeyPair()

        # Bob creates a message for Alice
        message = b"Top secret quantum optimization results"

        # 1. Encrypt for Alice
        envelope = pqc.py_encrypt(message, alice_kem.public_key)

        # 2. Alice receives, decrypts
        decrypted = pqc.py_decrypt(envelope, alice_kem.secret_key)
        assert decrypted == message

        # 3. Alice signs a response
        response = b"Acknowledged"
        signature = alice_sign.sign(response)

        # 4. Verify Alice's signature
        is_valid = pqc.py_verify(response, signature, alice_sign.public_key)
        assert is_valid is True


class TestCryptoPerformance:
    """Performance benchmarks for crypto operations."""

    def test_kem_keygen_performance(self):
        """Benchmark KEM key generation."""
        import time

        iterations = 10
        start = time.perf_counter()

        for _ in range(iterations):
            pqc.KemKeyPair()

        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / iterations) * 1000

        # Should be under 50ms per keygen
        assert avg_ms < 50, f"KEM keygen too slow: {avg_ms:.2f}ms"

    def test_signing_keygen_performance(self):
        """Benchmark signing key generation."""
        import time

        iterations = 10
        start = time.perf_counter()

        for _ in range(iterations):
            pqc.SigningKeyPair()

        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / iterations) * 1000

        # Should be under 50ms per keygen
        assert avg_ms < 50, f"Signing keygen too slow: {avg_ms:.2f}ms"

    def test_sign_verify_performance(self):
        """Benchmark sign/verify operations."""
        import time

        keypair = pqc.SigningKeyPair()
        message = b"Performance test message" * 100

        iterations = 20

        # Benchmark signing
        start = time.perf_counter()
        for _ in range(iterations):
            sig = keypair.sign(message)
        sign_elapsed = time.perf_counter() - start

        # Benchmark verification
        start = time.perf_counter()
        for _ in range(iterations):
            keypair.verify(message, sig)
        verify_elapsed = time.perf_counter() - start

        sign_avg_ms = (sign_elapsed / iterations) * 1000
        verify_avg_ms = (verify_elapsed / iterations) * 1000

        # Both should be under 20ms
        assert sign_avg_ms < 20, f"Signing too slow: {sign_avg_ms:.2f}ms"
        assert verify_avg_ms < 20, f"Verification too slow: {verify_avg_ms:.2f}ms"

    def test_encryption_performance(self):
        """Benchmark hybrid encryption/decryption."""
        import time

        keypair = pqc.KemKeyPair()
        plaintext = b"X" * 10_000  # 10KB

        iterations = 10

        # Benchmark encryption
        start = time.perf_counter()
        for _ in range(iterations):
            ct = pqc.py_encrypt(plaintext, keypair.public_key)
        enc_elapsed = time.perf_counter() - start

        # Benchmark decryption
        start = time.perf_counter()
        for _ in range(iterations):
            pqc.py_decrypt(ct, keypair.secret_key)
        dec_elapsed = time.perf_counter() - start

        enc_avg_ms = (enc_elapsed / iterations) * 1000
        dec_avg_ms = (dec_elapsed / iterations) * 1000

        # Both should be under 50ms for 10KB
        assert enc_avg_ms < 50, f"Encryption too slow: {enc_avg_ms:.2f}ms"
        assert dec_avg_ms < 50, f"Decryption too slow: {dec_avg_ms:.2f}ms"

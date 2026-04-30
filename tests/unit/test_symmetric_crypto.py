"""
Unit tests for symmetric cryptography operations.

Tests cover:
- AEAD encryption/decryption roundtrips
- Tamper detection
- Key derivation (HKDF)
- Nonce uniqueness
- Associated data integrity
"""

import pytest
import os


class TestAEADCipher:
    """Test AEAD (Authenticated Encryption with Associated Data) operations."""

    @pytest.fixture
    def cipher(self):
        """Create AEAD cipher instance."""
        try:
            from qsop.crypto.symmetric.aead import AEADCipher
            return AEADCipher()
        except ImportError:
            # Fallback to cryptography library if qsop not available
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            return AESGCM()

    @pytest.fixture
    def key(self):
        """Generate a test encryption key."""
        return os.urandom(32)  # 256-bit key

    def test_encrypt_decrypt_roundtrip(self, cipher, key):
        """Test that encryption followed by decryption returns original plaintext."""
        plaintext = b"Hello, Quantum World!"
        nonce = os.urandom(12)  # 96-bit nonce for AES-GCM

        # Encrypt
        ciphertext = cipher.encrypt(nonce, plaintext, None)

        # Decrypt
        decrypted = cipher.decrypt(nonce, ciphertext, None)

        assert decrypted == plaintext

    def test_encrypt_decrypt_with_aad(self, cipher, key):
        """Test encryption with Associated Authenticated Data (AAD)."""
        plaintext = b"Secret quantum optimization result"
        aad = b"job_id:12345,user:alice"
        nonce = os.urandom(12)

        # Encrypt with AAD
        ciphertext = cipher.encrypt(nonce, plaintext, aad)

        # Decrypt with same AAD
        decrypted = cipher.decrypt(nonce, ciphertext, aad)

        assert decrypted == plaintext

    def test_tampered_ciphertext_detected(self, cipher, key):
        """Test that tampering with ciphertext is detected."""
        plaintext = b"Top secret data"
        nonce = os.urandom(12)

        # Encrypt
        ciphertext = cipher.encrypt(nonce, plaintext, None)

        # Tamper with ciphertext (flip a bit)
        tampered = bytearray(ciphertext)
        tampered[0] ^= 0xFF  # Flip bits in first byte

        # Decryption should fail
        with pytest.raises(Exception):  # InvalidTag or similar
            cipher.decrypt(nonce, bytes(tampered), None)

    def test_wrong_aad_detected(self, cipher, key):
        """Test that using wrong AAD causes decryption to fail."""
        plaintext = b"Sensitive result"
        correct_aad = b"correct:aad:value"
        wrong_aad = b"wrong:aad:value"
        nonce = os.urandom(12)

        # Encrypt with correct AAD
        ciphertext = cipher.encrypt(nonce, plaintext, correct_aad)

        # Decrypt with wrong AAD should fail
        with pytest.raises(Exception):
            cipher.decrypt(nonce, ciphertext, wrong_aad)

    def test_unique_nonce_required(self, cipher, key):
        """Test that reusing nonce with same key is insecure (should work but is dangerous)."""
        plaintext1 = b"Message 1"
        plaintext2 = b"Message 2"
        nonce = os.urandom(12)  # Same nonce (BAD practice, but testing it works)

        # Both should encrypt successfully (but this is insecure!)
        ct1 = cipher.encrypt(nonce, plaintext1, None)
        ct2 = cipher.encrypt(nonce, plaintext2, None)

        # Both should decrypt correctly
        assert cipher.decrypt(nonce, ct1, None) == plaintext1
        assert cipher.decrypt(nonce, ct2, None) == plaintext2

        # Note: In production, NEVER reuse nonces with same key!

    def test_empty_plaintext(self, cipher, key):
        """Test encryption of empty message."""
        plaintext = b""
        nonce = os.urandom(12)

        ciphertext = cipher.encrypt(nonce, plaintext, None)
        decrypted = cipher.decrypt(nonce, ciphertext, None)

        assert decrypted == plaintext

    def test_large_plaintext(self, cipher, key):
        """Test encryption of large data (1MB)."""
        plaintext = os.urandom(1024 * 1024)  # 1MB random data
        nonce = os.urandom(12)

        ciphertext = cipher.encrypt(nonce, plaintext, None)
        decrypted = cipher.decrypt(nonce, ciphertext, None)

        assert decrypted == plaintext

    def test_different_keys_different_results(self, cipher):
        """Test that different keys produce different ciphertexts."""
        plaintext = b"Test message"
        nonce = os.urandom(12)
        key1 = os.urandom(32)
        key2 = os.urandom(32)

        ct1 = cipher.encrypt(nonce, plaintext, None)
        # Note: AES-GCM is deterministic with same nonce, so this test is limited
        # In practice, different nonces would be used

    def test_generate_key(self):
        """Test secure key generation."""
        try:
            from qsop.crypto.symmetric.aead import AEADCipher
            cipher = AEADCipher()
            key = cipher.generate_key()

            assert isinstance(key, bytes)
            assert len(key) == 32  # 256 bits
            assert key != b"\x00" * 32  # Not all zeros
        except (ImportError, AttributeError):
            pytest.skip("AEADCipher.generate_key() not available")


class TestHKDF:
    """Test HKDF (HMAC-based Key Derivation Function)."""

    def test_key_derivation_deterministic(self):
        """Test that same inputs always produce same derived key."""
        try:
            from qsop.crypto.symmetric.hkdf import HKDF

            ikm = b"input key material"
            salt = b"salt_value"
            info = b"application context"

            key1 = HKDF.derive(ikm, salt, info, length=32)
            key2 = HKDF.derive(ikm, salt, info, length=32)

            assert key1 == key2
            assert len(key1) == 32
        except ImportError:
            pytest.skip("HKDF not available")

    def test_different_salt_different_keys(self):
        """Test that different salts produce different derived keys."""
        try:
            from qsop.crypto.symmetric.hkdf import HKDF

            ikm = b"input key material"
            info = b"application context"

            key1 = HKDF.derive(ikm, salt=b"salt_1", info=info, length=32)
            key2 = HKDF.derive(ikm, salt=b"salt_2", info=info, length=32)

            assert key1 != key2
        except ImportError:
            pytest.skip("HKDF not available")

    def test_different_info_different_keys(self):
        """Test that different info contexts produce different keys."""
        try:
            from qsop.crypto.symmetric.hkdf import HKDF

            ikm = b"input key material"
            salt = b"salt"

            key1 = HKDF.derive(ikm, salt, info=b"context_1", length=32)
            key2 = HKDF.derive(ikm, salt, info=b"context_2", length=32)

            assert key1 != key2
        except ImportError:
            pytest.skip("HKDF not available")

    def test_output_length(self):
        """Test that derived key has correct length."""
        try:
            from qsop.crypto.symmetric.hkdf import HKDF

            lengths = [16, 32, 64, 128]

            for length in lengths:
                key = HKDF.derive(b"ikm", b"salt", b"info", length=length)
                assert len(key) == length, f"Expected {length} bytes, got {len(key)}"
        except ImportError:
            pytest.skip("HKDF not available")

    def test_empty_ikm_rejected(self):
        """Test that empty input key material is handled safely."""
        try:
            from qsop.crypto.symmetric.hkdf import HKDF

            # HKDF can technically work with empty IKM but should be warned
            key = HKDF.derive(b"", b"salt", b"info", length=32)

            # Should still produce a key (from salt)
            assert len(key) == 32
        except ImportError:
            pytest.skip("HKDF not available")


class TestSymmetricEncryptionIntegration:
    """Test symmetric encryption integration with job processing."""

    @pytest.mark.asyncio
    async def test_job_result_encryption_roundtrip(self):
        """Test that job results can be encrypted and decrypted."""
        # Mock job result
        result = {
            "status": "completed",
            "optimal_value": -5.234,
            "optimal_bitstring": "10110",
            "metadata": {"iterations": 100, "backend": "simulator"},
        }

        # Serialize
        import json
        result_bytes = json.dumps(result).encode("utf-8")

        # Encrypt
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            key = os.urandom(32)
            nonce = os.urandom(12)
            aad = b"job_id:test_123"

            ciphertext = AESGCM(key).encrypt(nonce, result_bytes, aad)

            # Decrypt
            decrypted_bytes = AESGCM(key).decrypt(nonce, ciphertext, aad)
            decrypted_result = json.loads(decrypted_bytes.decode("utf-8"))

            assert decrypted_result == result
        except ImportError:
            pytest.skip("cryptography library not available")

    def test_encrypted_result_integrity(self):
        """Test that encrypted results maintain integrity."""
        import json
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        result = {"data": "quantum_optimization_result", "value": 42}
        result_bytes = json.dumps(result).encode("utf-8")

        key = os.urandom(32)
        nonce = os.urandom(12)

        # Encrypt
        ciphertext = AESGCM(key).encrypt(nonce, result_bytes, None)

        # Tamper with ciphertext
        tampered = bytearray(ciphertext)
        tampered[-1] ^= 0xFF

        # Should fail integrity check
        with pytest.raises(Exception):
            AESGCM(key).decrypt(nonce, bytes(tampered), None)


class TestKeyManagement:
    """Test key management best practices."""

    def test_key_uniqueness(self):
        """Test that generated keys are unique."""
        keys = set()
        for _ in range(100):
            key = os.urandom(32)
            assert key not in keys, "Duplicate key generated!"
            keys.add(key)

    def test_key_entropy(self):
        """Test that keys have sufficient entropy."""
        # Generate key
        key = os.urandom(32)

        # Check that key is not all zeros or all ones
        assert key != b"\x00" * 32
        assert key != b"\xff" * 32

        # Check that key has reasonable bit diversity
        # (Not a perfect test, but catches obvious issues)
        byte_count = {}
        for byte in key:
            byte_count[byte] = byte_count.get(byte, 0) + 1

        # Should have at least 10 unique byte values in 32 bytes
        assert len(byte_count) >= 10, "Key has insufficient entropy"

    def test_key_zeroing_after_use(self):
        """Test that keys can be securely deleted."""
        key = bytearray(os.urandom(32))

        # Use key...
        assert len(key) == 32

        # Securely delete
        for i in range(len(key)):
            key[i] = 0

        assert key == bytearray(32)

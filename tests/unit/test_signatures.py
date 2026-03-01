"""Tests for digital signatures."""

import pytest

from qsop.crypto.pqc import SignatureAlgorithm
from qsop.crypto.signing.signatures import (
    MultiSigner,
    SignatureBundle,
    Signer,
    Verifier,
    canonicalize,
    generate_keypair,
)


class TestSignatures:
    """Test digital signature operations."""

    @pytest.fixture
    def dilithium_keypair(self):
        """Generate Dilithium keypair."""
        return generate_keypair(SignatureAlgorithm.DILITHIUM3)

    def test_sign_verify_bytes(self, dilithium_keypair):
        """Test signing and verifying raw bytes."""
        public_key, private_key = dilithium_keypair
        message = b"Important message to sign"

        signer = Signer(
            algorithm=SignatureAlgorithm.DILITHIUM3,
            private_key=private_key,
            key_id="test-key-1",
        )
        bundle = signer.sign(message)

        assert bundle is not None
        assert bundle.signature is not None
        assert bundle.algorithm == SignatureAlgorithm.DILITHIUM3
        assert bundle.key_id == "test-key-1"

        verifier = Verifier(
            algorithm=SignatureAlgorithm.DILITHIUM3,
            public_key=public_key,
        )
        assert verifier.verify(message, bundle) is True

    def test_sign_verify_dict(self, dilithium_keypair):
        """Test signing and verifying dictionary data."""
        public_key, private_key = dilithium_keypair
        data = {
            "job_id": "job-123",
            "algorithm": "qaoa",
            "parameters": [0.5, 1.2, 0.8],
        }

        signer = Signer(
            algorithm=SignatureAlgorithm.DILITHIUM3,
            private_key=private_key,
            key_id="test-key-2",
        )
        bundle = signer.sign(data)

        verifier = Verifier(
            algorithm=SignatureAlgorithm.DILITHIUM3,
            public_key=public_key,
        )
        assert verifier.verify(data, bundle) is True

    def test_signature_detects_tampering(self, dilithium_keypair):
        """Test that modified data fails verification."""
        public_key, private_key = dilithium_keypair
        original_data = {"value": 100}

        signer = Signer(
            algorithm=SignatureAlgorithm.DILITHIUM3,
            private_key=private_key,
            key_id="test-key",
        )
        bundle = signer.sign(original_data)

        # Modify the data
        tampered_data = {"value": 999}

        verifier = Verifier(
            algorithm=SignatureAlgorithm.DILITHIUM3,
            public_key=public_key,
        )
        assert verifier.verify(tampered_data, bundle) is False

    def test_signature_bundle_serialization(self, dilithium_keypair):
        """Test signature bundle serialization."""
        public_key, private_key = dilithium_keypair
        message = b"Test message"

        signer = Signer(
            algorithm=SignatureAlgorithm.DILITHIUM3,
            private_key=private_key,
            key_id="test-key",
        )
        bundle = signer.sign(message)

        # Serialize
        bundle_dict = bundle.to_dict()
        assert isinstance(bundle_dict, dict)
        assert "signature" in bundle_dict
        assert "algorithm" in bundle_dict

        # Deserialize
        restored = SignatureBundle.from_dict(bundle_dict)

        verifier = Verifier(
            algorithm=SignatureAlgorithm.DILITHIUM3,
            public_key=public_key,
        )
        assert verifier.verify(message, restored) is True

    def test_different_algorithms(self):
        """Test signatures with different algorithms."""
        algorithms = [
            SignatureAlgorithm.DILITHIUM2,
            SignatureAlgorithm.DILITHIUM3,
            SignatureAlgorithm.DILITHIUM5,
        ]

        message = b"Test message for different algorithms"

        for alg in algorithms:
            public_key, private_key = generate_keypair(alg)

            signer = Signer(
                algorithm=alg,
                private_key=private_key,
                key_id=f"key-{alg.value}",
            )
            bundle = signer.sign(message)

            verifier = Verifier(algorithm=alg, public_key=public_key)
            assert verifier.verify(message, bundle) is True, f"Failed for {alg}"

    def test_wrong_algorithm_fails(self, dilithium_keypair):
        """Test that wrong algorithm fails verification."""
        public_key, private_key = dilithium_keypair
        message = b"Test"

        signer = Signer(
            algorithm=SignatureAlgorithm.DILITHIUM3,
            private_key=private_key,
            key_id="test-key",
        )
        bundle = signer.sign(message)

        # Try to verify with different algorithm
        other_public, _ = generate_keypair(SignatureAlgorithm.DILITHIUM2)
        verifier = Verifier(
            algorithm=SignatureAlgorithm.DILITHIUM2,
            public_key=other_public,
        )
        assert verifier.verify(message, bundle) is False


class TestCanonicalization:
    """Test data canonicalization."""

    def test_canonicalize_bytes(self):
        """Test bytes pass through unchanged."""
        data = b"raw bytes"
        assert canonicalize(data) == data

    def test_canonicalize_string(self):
        """Test string encoding."""
        data = "hello world"
        assert canonicalize(data) == b"hello world"

    def test_canonicalize_dict_sorted(self):
        """Test dict keys are sorted."""
        data1 = {"b": 1, "a": 2}
        data2 = {"a": 2, "b": 1}

        assert canonicalize(data1) == canonicalize(data2)

    def test_canonicalize_nested(self):
        """Test nested structures."""
        data = {"outer": {"inner": [1, 2, 3]}}
        result = canonicalize(data)
        assert isinstance(result, bytes)


class TestMultiSigner:
    """Test multi-party signing."""

    def test_multiple_signatures(self):
        """Test collecting multiple signatures."""
        message = b"Multi-party message"

        # Generate multiple keypairs
        keypairs = [generate_keypair(SignatureAlgorithm.DILITHIUM3) for _ in range(3)]

        multi = MultiSigner()

        for i, (_pk, sk) in enumerate(keypairs):
            signer = Signer(
                algorithm=SignatureAlgorithm.DILITHIUM3,
                private_key=sk,
                key_id=f"signer-{i}",
            )
            bundle = signer.sign(message)
            multi.add_signature(bundle)

        assert len(multi.get_signatures()) == 3

        # Verify all
        verifiers = {
            f"signer-{i}": Verifier(
                algorithm=SignatureAlgorithm.DILITHIUM3,
                public_key=pk,
            )
            for i, (pk, _) in enumerate(keypairs)
        }

        results = multi.verify_all(message, verifiers)
        assert all(results.values())

    def test_multi_signer_serialization(self):
        """Test serialization of multiple signatures."""
        message = b"Test"
        pk, sk = generate_keypair(SignatureAlgorithm.DILITHIUM3)

        signer = Signer(
            algorithm=SignatureAlgorithm.DILITHIUM3,
            private_key=sk,
            key_id="test",
        )

        multi = MultiSigner()
        multi.add_signature(signer.sign(message))

        # Serialize
        data = multi.to_dict()

        # Deserialize
        restored = MultiSigner.from_dict(data)

        assert len(restored.get_signatures()) == 1

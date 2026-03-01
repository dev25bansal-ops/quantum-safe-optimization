#!/usr/bin/env python3
"""
Demonstration of quantum-safe envelope encryption.

Shows how to use Kyber KEM with AES-GCM for secure data encryption.
"""

import sys

sys.path.insert(0, "src")

from qsop.crypto.pqc import (
    KEMAlgorithm,
    SignatureAlgorithm,
    get_kem,
    get_signature_scheme,
)
from qsop.crypto.signing.signatures import (
    Signer,
    Verifier,
    generate_keypair,
)


def demo_kem_encryption():
    """Demonstrate KEM-based key exchange."""

    # Alice generates a keypair
    kem = get_kem(KEMAlgorithm.KYBER768)
    alice_pk, alice_sk = kem.keygen()

    # Bob encapsulates a shared secret to Alice's public key
    ciphertext, bob_shared_secret = kem.encapsulate(alice_pk)

    # Alice decapsulates to recover the shared secret
    alice_shared_secret = kem.decapsulate(ciphertext, alice_sk)

    # Verify they match
    assert  # noqa: S101 - Valid in demo code alice_shared_secret == bob_shared_secret

    return alice_shared_secret


def demo_digital_signatures():
    """Demonstrate post-quantum digital signatures."""

    # Generate keypair
    public_key, private_key = generate_keypair(SignatureAlgorithm.DILITHIUM3)

    # Create signer
    signer = Signer(
        algorithm=SignatureAlgorithm.DILITHIUM3,
        private_key=private_key,
        key_id="alice-signing-key",
    )

    # Sign a message
    message = {
        "job_id": "job-12345",
        "algorithm": "qaoa",
        "result": {"optimal_value": 42.0},
        "timestamp": "2024-01-15T10:30:00Z",
    }

    bundle = signer.sign(message)

    # Verify signature
    verifier = Verifier(
        algorithm=SignatureAlgorithm.DILITHIUM3,
        public_key=public_key,
    )

    is_valid = verifier.verify(message, bundle)

    # Test tampering detection
    tampered_message = message.copy()
    tampered_message["result"] = {"optimal_value": 999.0}

    is_valid_tampered = verifier.verify(tampered_message, bundle)

    assert  # noqa: S101 - Valid in demo code is_valid and not is_valid_tampered


def demo_signed_encrypted_message():
    """Demonstrate sign-then-encrypt pattern."""

    # Setup: Generate keys for sender and receiver

    # Sender's signing key
    sender_sign_pk, sender_sign_sk = generate_keypair(SignatureAlgorithm.DILITHIUM3)

    # Receiver's encryption key
    kem = get_kem(KEMAlgorithm.KYBER768)
    receiver_enc_pk, receiver_enc_sk = kem.keygen()

    # Create a message
    message = b"This is a secret optimization result: optimal_value=42.0"

    # Step 1: Sign the message
    signer = Signer(
        algorithm=SignatureAlgorithm.DILITHIUM3,
        private_key=sender_sign_sk,
        key_id="sender-key",
    )
    signature_bundle = signer.sign(message)

    # Step 2: Encrypt using KEM
    ciphertext, shared_secret = kem.encapsulate(receiver_enc_pk)

    # In practice, use shared_secret to derive an AES key and encrypt
    # For demo, we just show the key agreement

    # Receiver side: decrypt and verify
    kem.decapsulate(ciphertext, receiver_enc_sk)

    verifier = Verifier(
        algorithm=SignatureAlgorithm.DILITHIUM3,
        public_key=sender_sign_pk,
    )
    verifier.verify(message, signature_bundle)


def compare_algorithm_sizes():
    """Compare key and signature sizes across algorithms."""

    for alg in [KEMAlgorithm.KYBER512, KEMAlgorithm.KYBER768, KEMAlgorithm.KYBER1024]:
        kem = get_kem(alg)
        pk, sk = kem.keygen()
        ct, _ = kem.encapsulate(pk)

    for alg in [
        SignatureAlgorithm.DILITHIUM2,
        SignatureAlgorithm.DILITHIUM3,
        SignatureAlgorithm.DILITHIUM5,
    ]:
        sig = get_signature_scheme(alg)
        pk, sk = sig.keygen()
        sig.sign(b"test message", sk)


def main():
    """Run all encryption demos."""

    demo_kem_encryption()
    demo_digital_signatures()
    demo_signed_encrypted_message()
    compare_algorithm_sizes()


if __name__ == "__main__":
    main()

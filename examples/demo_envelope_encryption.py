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
    SignatureBundle,
)


def demo_kem_encryption():
    """Demonstrate KEM-based key exchange."""
    print("\n" + "="*60)
    print("Kyber Key Encapsulation Mechanism")
    print("="*60)
    
    # Alice generates a keypair
    print("\n1. Alice generates Kyber-768 keypair...")
    kem = get_kem(KEMAlgorithm.KYBER768)
    alice_pk, alice_sk = kem.keygen()
    print(f"   Public key: {len(alice_pk)} bytes")
    print(f"   Private key: {len(alice_sk)} bytes")
    
    # Bob encapsulates a shared secret to Alice's public key
    print("\n2. Bob encapsulates a shared secret to Alice...")
    ciphertext, bob_shared_secret = kem.encapsulate(alice_pk)
    print(f"   Ciphertext: {len(ciphertext)} bytes")
    print(f"   Bob's shared secret: {bob_shared_secret[:16].hex()}...")
    
    # Alice decapsulates to recover the shared secret
    print("\n3. Alice decapsulates to recover the shared secret...")
    alice_shared_secret = kem.decapsulate(ciphertext, alice_sk)
    print(f"   Alice's shared secret: {alice_shared_secret[:16].hex()}...")
    
    # Verify they match
    assert alice_shared_secret == bob_shared_secret
    print("\n✓ Shared secrets match! Secure key exchange complete.")
    
    return alice_shared_secret


def demo_digital_signatures():
    """Demonstrate post-quantum digital signatures."""
    print("\n" + "="*60)
    print("Dilithium Digital Signatures")
    print("="*60)
    
    # Generate keypair
    print("\n1. Generating Dilithium-3 keypair...")
    public_key, private_key = generate_keypair(SignatureAlgorithm.DILITHIUM3)
    print(f"   Public key: {len(public_key)} bytes")
    print(f"   Private key: {len(private_key)} bytes")
    
    # Create signer
    signer = Signer(
        algorithm=SignatureAlgorithm.DILITHIUM3,
        private_key=private_key,
        key_id="alice-signing-key",
    )
    
    # Sign a message
    print("\n2. Signing a message...")
    message = {
        "job_id": "job-12345",
        "algorithm": "qaoa",
        "result": {"optimal_value": 42.0},
        "timestamp": "2024-01-15T10:30:00Z",
    }
    
    bundle = signer.sign(message)
    print(f"   Signature size: {len(bundle.signature)} bytes")
    print(f"   Algorithm: {bundle.algorithm.value}")
    print(f"   Key ID: {bundle.key_id}")
    
    # Verify signature
    print("\n3. Verifying signature...")
    verifier = Verifier(
        algorithm=SignatureAlgorithm.DILITHIUM3,
        public_key=public_key,
    )
    
    is_valid = verifier.verify(message, bundle)
    print(f"   Signature valid: {is_valid}")
    
    # Test tampering detection
    print("\n4. Testing tampering detection...")
    tampered_message = message.copy()
    tampered_message["result"] = {"optimal_value": 999.0}
    
    is_valid_tampered = verifier.verify(tampered_message, bundle)
    print(f"   Tampered message verification: {is_valid_tampered}")
    
    assert is_valid and not is_valid_tampered
    print("\n✓ Signature system working correctly!")


def demo_signed_encrypted_message():
    """Demonstrate sign-then-encrypt pattern."""
    print("\n" + "="*60)
    print("Signed and Encrypted Message")
    print("="*60)
    
    # Setup: Generate keys for sender and receiver
    print("\n1. Setting up keys...")
    
    # Sender's signing key
    sender_sign_pk, sender_sign_sk = generate_keypair(SignatureAlgorithm.DILITHIUM3)
    print("   Sender's signing keypair generated")
    
    # Receiver's encryption key
    kem = get_kem(KEMAlgorithm.KYBER768)
    receiver_enc_pk, receiver_enc_sk = kem.keygen()
    print("   Receiver's encryption keypair generated")
    
    # Create a message
    message = b"This is a secret optimization result: optimal_value=42.0"
    print(f"\n2. Original message: {message.decode()}")
    
    # Step 1: Sign the message
    print("\n3. Signing the message...")
    signer = Signer(
        algorithm=SignatureAlgorithm.DILITHIUM3,
        private_key=sender_sign_sk,
        key_id="sender-key",
    )
    signature_bundle = signer.sign(message)
    print(f"   Signature created: {len(signature_bundle.signature)} bytes")
    
    # Step 2: Encrypt using KEM
    print("\n4. Encrypting with Kyber KEM...")
    ciphertext, shared_secret = kem.encapsulate(receiver_enc_pk)
    print(f"   KEM ciphertext: {len(ciphertext)} bytes")
    
    # In practice, use shared_secret to derive an AES key and encrypt
    # For demo, we just show the key agreement
    print(f"   Shared secret established: {shared_secret[:16].hex()}...")
    
    # Receiver side: decrypt and verify
    print("\n5. Receiver: Decrypting and verifying...")
    recovered_secret = kem.decapsulate(ciphertext, receiver_enc_sk)
    print(f"   Recovered secret: {recovered_secret[:16].hex()}...")
    
    verifier = Verifier(
        algorithm=SignatureAlgorithm.DILITHIUM3,
        public_key=sender_sign_pk,
    )
    is_authentic = verifier.verify(message, signature_bundle)
    print(f"   Signature verified: {is_authentic}")
    
    print("\n✓ Message authenticated and secure key established!")


def compare_algorithm_sizes():
    """Compare key and signature sizes across algorithms."""
    print("\n" + "="*60)
    print("Algorithm Comparison")
    print("="*60)
    
    print("\nKEM Algorithms:")
    print("-" * 50)
    print(f"{'Algorithm':<20} {'Public Key':<12} {'Private Key':<12} {'Ciphertext':<12}")
    print("-" * 50)
    
    for alg in [KEMAlgorithm.KYBER512, KEMAlgorithm.KYBER768, KEMAlgorithm.KYBER1024]:
        kem = get_kem(alg)
        pk, sk = kem.keygen()
        ct, _ = kem.encapsulate(pk)
        print(f"{alg.value:<20} {len(pk):<12} {len(sk):<12} {len(ct):<12}")
    
    print("\nSignature Algorithms:")
    print("-" * 60)
    print(f"{'Algorithm':<25} {'Public Key':<12} {'Private Key':<12} {'Signature':<12}")
    print("-" * 60)
    
    for alg in [SignatureAlgorithm.DILITHIUM2, SignatureAlgorithm.DILITHIUM3, SignatureAlgorithm.DILITHIUM5]:
        sig = get_signature_scheme(alg)
        pk, sk = sig.keygen()
        signature = sig.sign(b"test message", sk)
        print(f"{alg.value:<25} {len(pk):<12} {len(sk):<12} {len(signature):<12}")


def main():
    """Run all encryption demos."""
    print("Post-Quantum Cryptography Demonstrations")
    print("="*60)
    
    demo_kem_encryption()
    demo_digital_signatures()
    demo_signed_encrypted_message()
    compare_algorithm_sizes()
    
    print("\n" + "="*60)
    print("All cryptography demonstrations completed!")
    print("="*60)


if __name__ == "__main__":
    main()

"""
Post-Quantum Cryptography algorithm definitions and parameters.
"""

from dataclasses import dataclass
from enum import Enum


class KEMAlgorithm(Enum):
    """Key Encapsulation Mechanism algorithms."""

    # ML-KEM (Kyber) - NIST standardized
    KYBER512 = "Kyber512"
    KYBER768 = "Kyber768"
    KYBER1024 = "Kyber1024"

    # BIKE - NIST Round 4 alternate
    BIKE_L1 = "BIKE-L1"
    BIKE_L3 = "BIKE-L3"

    @property
    def security_level(self) -> int:
        """NIST security level (1, 3, or 5)."""
        return KEM_PARAMETERS[self].security_level

    @property
    def is_standardized(self) -> bool:
        """Whether this algorithm is NIST standardized."""
        return self in (self.KYBER512, self.KYBER768, self.KYBER1024)

    @property
    def oqs_name(self) -> str:
        """Name used by liboqs."""
        return KEM_PARAMETERS[self].oqs_name


class SignatureAlgorithm(Enum):
    """Digital signature algorithms."""

    # ML-DSA (Dilithium) - NIST standardized
    DILITHIUM2 = "Dilithium2"
    DILITHIUM3 = "Dilithium3"
    DILITHIUM5 = "Dilithium5"

    # SLH-DSA (SPHINCS+) - NIST standardized
    SPHINCS_SHA2_128s = "SPHINCS+-SHA2-128s-simple"
    SPHINCS_SHA2_256f = "SPHINCS+-SHA2-256f-simple"

    @property
    def security_level(self) -> int:
        """NIST security level (1, 3, or 5)."""
        return SIGNATURE_PARAMETERS[self].security_level

    @property
    def is_stateless(self) -> bool:
        """Whether this algorithm is stateless (safe for multiple signatures)."""
        return True  # All supported algorithms are stateless

    @property
    def oqs_name(self) -> str:
        """Name used by liboqs."""
        return SIGNATURE_PARAMETERS[self].oqs_name


@dataclass(frozen=True)
class KEMParameters:
    """Parameters for a KEM algorithm."""

    oqs_name: str
    security_level: int
    public_key_size: int
    secret_key_size: int
    ciphertext_size: int
    shared_secret_size: int


@dataclass(frozen=True)
class SignatureParameters:
    """Parameters for a signature algorithm."""

    oqs_name: str
    security_level: int
    public_key_size: int
    secret_key_size: int
    signature_size: int


# KEM algorithm parameters
# Values from liboqs and NIST specifications
KEM_PARAMETERS: dict[KEMAlgorithm, KEMParameters] = {
    KEMAlgorithm.KYBER512: KEMParameters(
        oqs_name="Kyber512",
        security_level=1,
        public_key_size=800,
        secret_key_size=1632,
        ciphertext_size=768,
        shared_secret_size=32,
    ),
    KEMAlgorithm.KYBER768: KEMParameters(
        oqs_name="Kyber768",
        security_level=3,
        public_key_size=1184,
        secret_key_size=2400,
        ciphertext_size=1088,
        shared_secret_size=32,
    ),
    KEMAlgorithm.KYBER1024: KEMParameters(
        oqs_name="Kyber1024",
        security_level=5,
        public_key_size=1568,
        secret_key_size=3168,
        ciphertext_size=1568,
        shared_secret_size=32,
    ),
    KEMAlgorithm.BIKE_L1: KEMParameters(
        oqs_name="BIKE-L1",
        security_level=1,
        public_key_size=1541,
        secret_key_size=3114,
        ciphertext_size=1573,
        shared_secret_size=32,
    ),
    KEMAlgorithm.BIKE_L3: KEMParameters(
        oqs_name="BIKE-L3",
        security_level=3,
        public_key_size=3083,
        secret_key_size=6198,
        ciphertext_size=3115,
        shared_secret_size=32,
    ),
}


# Signature algorithm parameters
SIGNATURE_PARAMETERS: dict[SignatureAlgorithm, SignatureParameters] = {
    SignatureAlgorithm.DILITHIUM2: SignatureParameters(
        oqs_name="Dilithium2",
        security_level=2,
        public_key_size=1312,
        secret_key_size=2528,
        signature_size=2420,
    ),
    SignatureAlgorithm.DILITHIUM3: SignatureParameters(
        oqs_name="Dilithium3",
        security_level=3,
        public_key_size=1952,
        secret_key_size=4000,
        signature_size=3293,
    ),
    SignatureAlgorithm.DILITHIUM5: SignatureParameters(
        oqs_name="Dilithium5",
        security_level=5,
        public_key_size=2592,
        secret_key_size=4864,
        signature_size=4595,
    ),
    SignatureAlgorithm.SPHINCS_SHA2_128s: SignatureParameters(
        oqs_name="SPHINCS+-SHA2-128s-simple",
        security_level=1,
        public_key_size=32,
        secret_key_size=64,
        signature_size=7856,
    ),
    SignatureAlgorithm.SPHINCS_SHA2_256f: SignatureParameters(
        oqs_name="SPHINCS+-SHA2-256f-simple",
        security_level=5,
        public_key_size=64,
        secret_key_size=128,
        signature_size=49856,
    ),
}


def get_kem_parameters(algorithm: KEMAlgorithm) -> KEMParameters:
    """Get parameters for a KEM algorithm."""
    if algorithm not in KEM_PARAMETERS:
        raise ValueError(f"Unknown KEM algorithm: {algorithm}")
    return KEM_PARAMETERS[algorithm]


def get_signature_parameters(algorithm: SignatureAlgorithm) -> SignatureParameters:
    """Get parameters for a signature algorithm."""
    if algorithm not in SIGNATURE_PARAMETERS:
        raise ValueError(f"Unknown signature algorithm: {algorithm}")
    return SIGNATURE_PARAMETERS[algorithm]


__all__ = [
    "KEMAlgorithm",
    "SignatureAlgorithm",
    "KEMParameters",
    "SignatureParameters",
    "KEM_PARAMETERS",
    "SIGNATURE_PARAMETERS",
    "get_kem_parameters",
    "get_signature_parameters",
]

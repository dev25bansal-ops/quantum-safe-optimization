"""
Compliance and policy enforcement.

Ensures cryptographic operations meet regulatory requirements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..crypto.pqc import KEMAlgorithm, SignatureAlgorithm


class ComplianceLevel(str, Enum):
    """Compliance levels for cryptographic operations."""

    STANDARD = "standard"
    NIST_L1 = "nist_l1"  # NIST Security Level 1
    NIST_L3 = "nist_l3"  # NIST Security Level 3
    NIST_L5 = "nist_l5"  # NIST Security Level 5


# Algorithm mappings to NIST security levels
KEM_SECURITY_LEVELS: dict[KEMAlgorithm, int] = {
    KEMAlgorithm.KYBER512: 1,
    KEMAlgorithm.KYBER768: 3,
    KEMAlgorithm.KYBER1024: 5,
    KEMAlgorithm.BIKE_L1: 1,
    KEMAlgorithm.BIKE_L3: 3,
}

SIGNATURE_SECURITY_LEVELS: dict[SignatureAlgorithm, int] = {
    SignatureAlgorithm.DILITHIUM2: 2,
    SignatureAlgorithm.DILITHIUM3: 3,
    SignatureAlgorithm.DILITHIUM5: 5,
    SignatureAlgorithm.SPHINCS_SHA2_128s: 1,
    SignatureAlgorithm.SPHINCS_SHA2_256f: 5,
}


@dataclass
class CompliancePolicy:
    """Policy for cryptographic compliance."""

    name: str
    minimum_security_level: int = 3
    allowed_kem_algorithms: list[KEMAlgorithm] = field(default_factory=list)
    allowed_signature_algorithms: list[SignatureAlgorithm] = field(default_factory=list)
    require_pqc: bool = True
    require_signing: bool = True
    require_encryption: bool = True
    max_key_age_days: int = 365
    require_key_rotation: bool = True

    @classmethod
    def nist_l3(cls) -> CompliancePolicy:
        """NIST Security Level 3 policy."""
        return cls(
            name="NIST-L3",
            minimum_security_level=3,
            allowed_kem_algorithms=[KEMAlgorithm.KYBER768, KEMAlgorithm.KYBER1024],
            allowed_signature_algorithms=[
                SignatureAlgorithm.DILITHIUM3,
                SignatureAlgorithm.DILITHIUM5,
            ],
        )

    @classmethod
    def nist_l5(cls) -> CompliancePolicy:
        """NIST Security Level 5 policy."""
        return cls(
            name="NIST-L5",
            minimum_security_level=5,
            allowed_kem_algorithms=[KEMAlgorithm.KYBER1024],
            allowed_signature_algorithms=[
                SignatureAlgorithm.DILITHIUM5,
                SignatureAlgorithm.SPHINCS_SHA2_256s,
            ],
        )


class ComplianceChecker:
    """
    Validates cryptographic operations against compliance policies.
    """

    def __init__(self, policy: CompliancePolicy):
        self.policy = policy

    def check_kem_algorithm(self, algorithm: KEMAlgorithm) -> ComplianceResult:
        """Check if a KEM algorithm is compliant."""
        issues = []

        if self.policy.allowed_kem_algorithms:
            if algorithm not in self.policy.allowed_kem_algorithms:
                issues.append(f"KEM algorithm {algorithm.value} not in allowed list")

        security_level = KEM_SECURITY_LEVELS.get(algorithm, 0)
        if security_level < self.policy.minimum_security_level:
            issues.append(
                f"KEM algorithm {algorithm.value} has security level {security_level}, "
                f"minimum required is {self.policy.minimum_security_level}"
            )

        return ComplianceResult(
            compliant=len(issues) == 0,
            issues=issues,
            policy_name=self.policy.name,
        )

    def check_signature_algorithm(
        self,
        algorithm: SignatureAlgorithm,
    ) -> ComplianceResult:
        """Check if a signature algorithm is compliant."""
        issues = []

        if self.policy.allowed_signature_algorithms:
            if algorithm not in self.policy.allowed_signature_algorithms:
                issues.append(f"Signature algorithm {algorithm.value} not in allowed list")

        security_level = SIGNATURE_SECURITY_LEVELS.get(algorithm, 0)
        if security_level < self.policy.minimum_security_level:
            issues.append(
                f"Signature algorithm {algorithm.value} has security level {security_level}, "
                f"minimum required is {self.policy.minimum_security_level}"
            )

        return ComplianceResult(
            compliant=len(issues) == 0,
            issues=issues,
            policy_name=self.policy.name,
        )

    def check_operation(
        self,
        operation: str,
        kem_algorithm: KEMAlgorithm | None = None,
        signature_algorithm: SignatureAlgorithm | None = None,
    ) -> ComplianceResult:
        """Check if an operation is compliant."""
        issues = []

        if self.policy.require_encryption and kem_algorithm is None:
            issues.append("Encryption required but no KEM algorithm specified")

        if self.policy.require_signing and signature_algorithm is None:
            issues.append("Signing required but no signature algorithm specified")

        if kem_algorithm:
            kem_result = self.check_kem_algorithm(kem_algorithm)
            issues.extend(kem_result.issues)

        if signature_algorithm:
            sig_result = self.check_signature_algorithm(signature_algorithm)
            issues.extend(sig_result.issues)

        return ComplianceResult(
            compliant=len(issues) == 0,
            issues=issues,
            policy_name=self.policy.name,
        )


@dataclass
class ComplianceResult:
    """Result of a compliance check."""

    compliant: bool
    issues: list[str]
    policy_name: str

    def raise_if_non_compliant(self) -> None:
        """Raise an exception if not compliant."""
        if not self.compliant:
            raise ComplianceError(f"Policy {self.policy_name} violation: {'; '.join(self.issues)}")


class ComplianceError(Exception):
    """Raised when an operation violates compliance policy."""

    pass


def get_recommended_algorithms(
    security_level: int = 3,
) -> tuple[KEMAlgorithm, SignatureAlgorithm]:
    """
    Get recommended algorithms for a security level.

    Returns:
        Tuple of (recommended KEM, recommended signature algorithm)
    """
    if security_level >= 5:
        return KEMAlgorithm.KYBER1024, SignatureAlgorithm.DILITHIUM5
    elif security_level >= 3:
        return KEMAlgorithm.KYBER768, SignatureAlgorithm.DILITHIUM3
    else:
        return KEMAlgorithm.KYBER512, SignatureAlgorithm.DILITHIUM2

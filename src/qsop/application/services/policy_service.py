"""
Policy service for algorithm and resource management.

Enforces tenant-specific restrictions and resource quotas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import logging

from ...crypto.pqc import KEMAlgorithm, SignatureAlgorithm
from ...security.compliance import CompliancePolicy, ComplianceChecker

logger = logging.getLogger(__name__)


class ResourceType(str, Enum):
    """Types of resources that can be limited."""
    JOBS = "jobs"
    SHOTS = "shots"
    QUBITS = "qubits"
    STORAGE_BYTES = "storage_bytes"
    API_CALLS = "api_calls"


@dataclass
class ResourceQuota:
    """Resource quota for a tenant."""
    resource_type: ResourceType
    limit: int
    period_seconds: int | None = None  # None = lifetime
    current_usage: int = 0
    last_reset: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def is_exceeded(self) -> bool:
        """Check if quota is exceeded."""
        return self.current_usage >= self.limit
    
    def remaining(self) -> int:
        """Get remaining quota."""
        return max(0, self.limit - self.current_usage)
    
    def should_reset(self) -> bool:
        """Check if quota period has elapsed and should reset."""
        if self.period_seconds is None:
            return False
        elapsed = (datetime.now(timezone.utc) - self.last_reset).total_seconds()
        return elapsed >= self.period_seconds


@dataclass
class TenantPolicy:
    """Policy configuration for a tenant."""
    tenant_id: str
    name: str
    
    # Algorithm restrictions
    allowed_algorithms: list[str] = field(default_factory=list)
    allowed_backends: list[str] = field(default_factory=list)
    
    # Crypto policy
    crypto_policy: CompliancePolicy | None = None
    
    # Resource quotas
    quotas: dict[ResourceType, ResourceQuota] = field(default_factory=dict)
    
    # Feature flags
    hybrid_optimization_enabled: bool = True
    real_hardware_enabled: bool = False
    multi_recipient_encryption_enabled: bool = True
    
    # Limits
    max_qubits: int = 20
    max_shots_per_job: int = 100000
    max_iterations: int = 1000
    max_concurrent_jobs: int = 5


class PolicyService:
    """
    Service for managing and enforcing policies.
    
    Handles algorithm allowlists, resource quotas, and feature flags.
    """
    
    def __init__(self) -> None:
        self._policies: dict[str, TenantPolicy] = {}
        self._default_policy = self._create_default_policy()
    
    def _create_default_policy(self) -> TenantPolicy:
        """Create default policy for new tenants."""
        return TenantPolicy(
            tenant_id="default",
            name="Default Policy",
            allowed_algorithms=[
                "gradient_descent",
                "genetic_algorithm",
                "differential_evolution",
                "particle_swarm",
                "simulated_annealing",
                "qaoa",
                "vqe",
            ],
            allowed_backends=[
                "statevector",
                "qiskit_aer",
            ],
            crypto_policy=CompliancePolicy.nist_l3(),
            quotas={
                ResourceType.JOBS: ResourceQuota(
                    resource_type=ResourceType.JOBS,
                    limit=100,
                    period_seconds=86400,  # per day
                ),
                ResourceType.SHOTS: ResourceQuota(
                    resource_type=ResourceType.SHOTS,
                    limit=1_000_000,
                    period_seconds=86400,
                ),
            },
        )
    
    def get_policy(self, tenant_id: str) -> TenantPolicy:
        """Get policy for a tenant."""
        return self._policies.get(tenant_id, self._default_policy)
    
    def set_policy(self, policy: TenantPolicy) -> None:
        """Set policy for a tenant."""
        self._policies[policy.tenant_id] = policy
        logger.info(f"Policy updated for tenant {policy.tenant_id}")
    
    def check_algorithm_allowed(
        self,
        tenant_id: str,
        algorithm: str,
    ) -> tuple[bool, str]:
        """
        Check if an algorithm is allowed for a tenant.
        
        Returns:
            Tuple of (allowed, reason)
        """
        policy = self.get_policy(tenant_id)
        
        if not policy.allowed_algorithms:
            return True, "All algorithms allowed"
        
        if algorithm.lower() in [a.lower() for a in policy.allowed_algorithms]:
            return True, "Algorithm allowed"
        
        return False, f"Algorithm '{algorithm}' not in allowed list"
    
    def check_backend_allowed(
        self,
        tenant_id: str,
        backend: str,
    ) -> tuple[bool, str]:
        """Check if a backend is allowed for a tenant."""
        policy = self.get_policy(tenant_id)
        
        if not policy.allowed_backends:
            return True, "All backends allowed"
        
        if backend.lower() in [b.lower() for b in policy.allowed_backends]:
            return True, "Backend allowed"
        
        return False, f"Backend '{backend}' not in allowed list"
    
    def check_quota(
        self,
        tenant_id: str,
        resource: ResourceType,
        requested: int = 1,
    ) -> tuple[bool, str]:
        """
        Check if a resource quota would be exceeded.
        
        Returns:
            Tuple of (allowed, reason)
        """
        policy = self.get_policy(tenant_id)
        quota = policy.quotas.get(resource)
        
        if quota is None:
            return True, "No quota set"
        
        # Check for period reset
        if quota.should_reset():
            quota.current_usage = 0
            quota.last_reset = datetime.now(timezone.utc)
        
        if quota.current_usage + requested > quota.limit:
            return False, f"Quota exceeded: {quota.current_usage}/{quota.limit}"
        
        return True, f"Within quota: {quota.current_usage + requested}/{quota.limit}"
    
    def consume_quota(
        self,
        tenant_id: str,
        resource: ResourceType,
        amount: int = 1,
    ) -> bool:
        """
        Consume quota for a resource.
        
        Returns:
            True if quota was consumed, False if would exceed limit.
        """
        allowed, _ = self.check_quota(tenant_id, resource, amount)
        
        if not allowed:
            return False
        
        policy = self.get_policy(tenant_id)
        quota = policy.quotas.get(resource)
        
        if quota:
            quota.current_usage += amount
        
        return True
    
    def check_job_parameters(
        self,
        tenant_id: str,
        qubits: int,
        shots: int,
        iterations: int,
    ) -> tuple[bool, list[str]]:
        """
        Check if job parameters are within limits.
        
        Returns:
            Tuple of (allowed, list of violations)
        """
        policy = self.get_policy(tenant_id)
        violations = []
        
        if qubits > policy.max_qubits:
            violations.append(f"Qubits ({qubits}) exceeds max ({policy.max_qubits})")
        
        if shots > policy.max_shots_per_job:
            violations.append(f"Shots ({shots}) exceeds max ({policy.max_shots_per_job})")
        
        if iterations > policy.max_iterations:
            violations.append(f"Iterations ({iterations}) exceeds max ({policy.max_iterations})")
        
        return len(violations) == 0, violations
    
    def get_crypto_checker(self, tenant_id: str) -> ComplianceChecker | None:
        """Get compliance checker for tenant's crypto policy."""
        policy = self.get_policy(tenant_id)
        
        if policy.crypto_policy:
            return ComplianceChecker(policy.crypto_policy)
        
        return None
    
    def get_usage_summary(self, tenant_id: str) -> dict[str, Any]:
        """Get resource usage summary for a tenant."""
        policy = self.get_policy(tenant_id)
        
        summary = {
            "tenant_id": tenant_id,
            "policy_name": policy.name,
            "quotas": {},
        }
        
        for resource_type, quota in policy.quotas.items():
            summary["quotas"][resource_type.value] = {
                "limit": quota.limit,
                "used": quota.current_usage,
                "remaining": quota.remaining(),
                "period_seconds": quota.period_seconds,
            }
        
        return summary

"""
Budget management service.

Handles cost tracking, budget allocation, and limit enforcement
for quantum optimization jobs across tenants and backends.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID


@dataclass
class Budget:
    """Budget allocation for a tenant."""

    tenant_id: str
    limit: Decimal
    used: Decimal = Decimal("0.00")
    currency: str = "USD"
    period_start: datetime.datetime = field(default_factory=datetime.datetime.utcnow)
    period_end: datetime.datetime | None = None

    def remaining(self) -> Decimal:
        """Get remaining budget."""
        return self.limit - self.used

    def check_available(self, amount: Decimal) -> bool:
        """Check if amount is available within budget."""
        return self.remaining() >= amount

    def add_cost(self, amount: Decimal) -> None:
        """Add a cost to used budget."""
        self.used += amount


@dataclass
class CostBreakdown:
    """Cost breakdown for a job or operation."""

    quantum_backend: Decimal
    storage: Decimal
    compute: Decimal
    overhead: Decimal
    total: Decimal = Decimal("0.00")
    currency: str = "USD"

    def __post_init__(self) -> None:
        self.total = self.quantum_backend + self.storage + self.compute + self.overhead


@dataclass
class BackendPricing:
    """Pricing information for quantum backends."""

    backend_id: str
    provider: str
    cost_per_qubit_hour: Decimal
    cost_per_shot: Decimal | None = None
    cost_per_circuit: Decimal | None = None
    currency: str = "USD"

    def estimate_job_cost(
        self,
        num_qubits: int,
        shots: int = 1024,
        runtime_seconds: float = 1.0,
        circuit_depth: int = 10,
    ) -> CostBreakdown:
        """Estimate cost for a quantum job."""
        backend_cost = Decimal("0.0")

        if self.cost_per_qubit_hour:
            hours = Decimal(str(runtime_seconds / 3600.0))
            backend_cost += self.cost_per_qubit_hour * Decimal(str(num_qubits)) * hours

        if self.cost_per_shot:
            backend_cost += self.cost_per_shot * Decimal(str(shots))

        if self.cost_per_circuit:
            backend_cost += self.cost_per_circuit * Decimal(str(circuit_depth))

        # Storage and compute costs (simplified)
        storage = Decimal(str(shots * num_qubits * 0.00001))
        compute = Decimal(str(runtime_seconds * 0.0001))
        overhead = backend_cost * Decimal("0.1")

        return CostBreakdown(
            quantum_backend=backend_cost,
            storage=storage,
            compute=compute,
            overhead=overhead,
            currency=self.currency,
        )


class BudgetService:
    """
    Manages budgets and cost tracking.

    Features:
    - Per-tenant budget tracking
    - Backend pricing models
    - Cost estimation
    - Budget limit enforcement
    - Usage history
    """

    def __init__(self):
        self._budgets: dict[str, Budget] = {}
        self._pricing: dict[str, BackendPricing] = {}
        self._default_pricing = self._init_default_pricing()

    def _init_default_pricing(self) -> dict[str, BackendPricing]:
        """Initialize default backend pricing."""
        return {
            "ibm_quantum": BackendPricing(
                backend_id="ibm_quantum",
                provider="IBM",
                cost_per_qubit_hour=Decimal("1.6"),
                cost_per_shot=Decimal("0.000016"),
                currency="USD",
            ),
            "aws_braket": BackendPricing(
                backend_id="aws_braket",
                provider="AWS",
                cost_per_qubit_hour=Decimal("6.2"),
                cost_per_shot=Decimal("0.00032"),
                currency="USD",
            ),
            "azure_quantum": BackendPricing(
                backend_id="azure_quantum",
                provider="Azure",
                cost_per_qubit_hour=Decimal("5.0"),
                cost_per_shot=Decimal("0.00025"),
                currency="USD",
            ),
            "ionq": BackendPricing(
                backend_id="ionq",
                provider="IonQ",
                cost_per_qubit_hour=Decimal("3.0"),
                cost_per_shot=Decimal("0.0002"),
                currency="USD",
            ),
            "statevector_simulator": BackendPricing(
                backend_id="statevector_simulator",
                provider="QSOP",
                cost_per_qubit_hour=Decimal("0.0"),
                cost_per_shot=Decimal("0.0"),
                currency="USD",
            ),
            "qiskit_aer": BackendPricing(
                backend_id="qiskit_aer",
                provider="QSOP",
                cost_per_qubit_hour=Decimal("0.0"),
                cost_per_shot=Decimal("0.0"),
                currency="USD",
            ),
            " gpu_simulator": BackendPricing(
                backend_id="gpu_simulator",
                provider="QSOP",
                cost_per_qubit_hour=Decimal("0.1"),
                cost_per_shot=Decimal("0.00001"),
                currency="USD",
            ),
        }

    def register_backend_pricing(self, pricing: BackendPricing) -> None:
        """Register or update backend pricing."""
        self._pricing[pricing.backend_id] = pricing

    def get_backend_pricing(self, backend_id: str) -> BackendPricing:
        """Get pricing for a backend."""
        if backend_id in self._pricing:
            return self._pricing[backend_id]
        if backend_id in self._default_pricing:
            return self._default_pricing[backend_id]
        raise ValueError(f"No pricing available for backend: {backend_id}")

    def create_budget(
        self,
        tenant_id: str,
        limit: float,
        currency: str = "USD",
    ) -> Budget:
        """Create a new budget for a tenant."""
        budget = Budget(
            tenant_id=tenant_id,
            limit=Decimal(str(limit)),
            currency=currency,
        )
        self._budgets[tenant_id] = budget
        return budget

    def get_budget(self, tenant_id: str) -> Budget | None:
        """Get budget for a tenant."""
        return self._budgets.get(tenant_id)

    def check_availability(
        self,
        tenant_id: str,
        estimated_cost: float,
    ) -> tuple[bool, Decimal]:
        """
        Check if job fits within budget.

        Args:
            tenant_id: Tenant ID
            estimated_cost: Estimated cost
            Returns:
                Tuple of (within_budget, remaining_budget)
        """
        budget = self.get_budget(tenant_id)
        if budget is None:
            return True, Decimal("999999")  # Unlimited if no budget

        cost_decimal = Decimal(str(estimated_cost))
        return budget.check_available(cost_decimal), budget.remaining()

    def estimate_job_cost(
        self,
        backend_id: str,
        num_qubits: int,
        shots: int = 1024,
        runtime_seconds: float = 1.0,
        circuit_depth: int = 10,
    ) -> CostBreakdown:
        """Estimate cost for a job."""
        pricing = self.get_backend_pricing(backend_id)
        return pricing.estimate_job_cost(
            num_qubits=num_qubits,
            shots=shots,
            runtime_seconds=runtime_seconds,
            circuit_depth=circuit_depth,
        )

    def track_job_cost(
        self,
        job_id: UUID,
        tenant_id: str,
        actual_cost: CostBreakdown,
    ) -> None:
        """Track actual cost of a completed job."""
        budget = self.get_budget(tenant_id)
        if budget is not None:
            budget.add_cost(actual_cost.total)

    def get_usage_history(
        self,
        tenant_id: str,
        days: int = 30,
    ) -> list[dict[str, any]]:
        """
        Get cost usage history.

        Args:
            tenant_id: Tenant ID
            days: Number of days of history

        Returns:
            List of daily cost breakdowns
        """
        budget = self.get_budget(tenant_id)
        if budget is None:
            return []

        start_date = datetime.datetime.utcnow() - datetime.timedelta(days=days)
        daily_costs = []

        for i in range(days):
            date = start_date + datetime.timedelta(days=i)
            daily_costs.append(
                {
                    "date": date.isoformat(),
                    "cost": float(budget.used) / days,  # Simplified
                    "currency": budget.currency,
                }
            )

        return daily_costs


_global_budget_service: BudgetService | None = None


def get_budget_service() -> BudgetService:
    """Get global budget service singleton."""
    global _global_budget_service
    if _global_budget_service is None:
        _global_budget_service = BudgetService()
    return _global_budget_service


__all__ = [
    "Budget",
    "CostBreakdown",
    "BackendPricing",
    "BudgetService",
    "get_budget_service",
]

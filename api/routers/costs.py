"""
Cost estimation router - Estimate costs for quantum backend jobs.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from enum import Enum

router = APIRouter(prefix="/costs", tags=["Cost Estimation"])


class JobTypeEnum(str, Enum):
    """Supported job types."""
    QAOA = "qaoa"
    VQE = "vqe"
    ANNEALING = "annealing"


class QuantumBackendEnum(str, Enum):
    """Supported quantum backends."""
    SIMULATOR = "simulator"
    IBM_QUANTUM = "ibm_quantum"
    IBM_BRISBANE = "ibm_brisbane"
    IBM_OSAKA = "ibm_osaka"
    AWS_BRAKET = "aws_braket"
    AWS_SV1 = "aws_sv1"
    AWS_DM1 = "aws_dm1"
    AWS_TN1 = "aws_tn1"
    AZURE_QUANTUM = "azure_quantum"
    AZURE_IONQ = "azure_ionq"
    AZURE_QUANTINUUM = "azure_quantinuum"
    DWAVE = "dwave"
    DWAVE_ADVANTAGE = "dwave_advantage"
    DWAVE_2000Q = "dwave_2000q"


class CostEstimateRequest(BaseModel):
    """Request model for cost estimation."""
    job_type: JobTypeEnum = Field(..., description="Type of quantum job")
    backend: str = Field(..., description="Target quantum backend")
    shots: int = Field(default=1000, ge=1, le=100000, description="Number of shots/reads")
    circuit_depth: Optional[int] = Field(default=None, ge=1, description="Estimated circuit depth")
    num_qubits: Optional[int] = Field(default=None, ge=1, le=5000, description="Number of qubits")
    problem_size: Optional[int] = Field(default=None, ge=1, description="Size of optimization problem")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_type": "qaoa",
                "backend": "ibm_quantum",
                "shots": 10000,
                "circuit_depth": 50,
                "num_qubits": 20
            }
        }


class CostBreakdown(BaseModel):
    """Detailed cost breakdown."""
    compute_cost: float = Field(..., description="Core compute cost")
    queue_cost: float = Field(default=0.0, description="Queue/priority cost")
    data_transfer_cost: float = Field(default=0.0, description="Data transfer cost")
    storage_cost: float = Field(default=0.0, description="Result storage cost")


class CostEstimateResponse(BaseModel):
    """Response model for cost estimation."""
    backend: str
    job_type: str
    estimated_cost_usd: float = Field(..., description="Total estimated cost in USD")
    estimated_time_seconds: float = Field(..., description="Estimated execution time")
    shots: int
    currency: str = "USD"
    breakdown: CostBreakdown
    notes: Optional[str] = None
    pricing_tier: str = Field(default="standard", description="Pricing tier applied")
    
    class Config:
        json_schema_extra = {
            "example": {
                "backend": "ibm_quantum",
                "job_type": "qaoa",
                "estimated_cost_usd": 2.50,
                "estimated_time_seconds": 120.0,
                "shots": 10000,
                "currency": "USD",
                "breakdown": {
                    "compute_cost": 2.00,
                    "queue_cost": 0.25,
                    "data_transfer_cost": 0.15,
                    "storage_cost": 0.10
                },
                "notes": "Prices are estimates and may vary based on queue length and availability.",
                "pricing_tier": "standard"
            }
        }


# Pricing models for different backends (USD per unit)
BACKEND_PRICING = {
    # Simulators - Free or low cost
    "simulator": {
        "base_rate": 0.0,
        "per_shot": 0.0,
        "per_qubit": 0.0,
        "per_second": 0.001,
        "queue_multiplier": 1.0,
        "notes": "Local simulator - compute costs only"
    },
    
    # IBM Quantum
    "ibm_quantum": {
        "base_rate": 1.60,
        "per_shot": 0.00008,
        "per_qubit": 0.01,
        "per_second": 0.02,
        "queue_multiplier": 1.2,
        "notes": "IBM Quantum Network pricing. Actual costs depend on your plan."
    },
    "ibm_brisbane": {
        "base_rate": 1.60,
        "per_shot": 0.00008,
        "per_qubit": 0.01,
        "per_second": 0.02,
        "queue_multiplier": 1.5,
        "notes": "IBM Brisbane (127 qubits). Premium pricing due to high demand."
    },
    "ibm_osaka": {
        "base_rate": 1.60,
        "per_shot": 0.00008,
        "per_qubit": 0.01,
        "per_second": 0.02,
        "queue_multiplier": 1.3,
        "notes": "IBM Osaka (127 qubits)."
    },
    
    # AWS Braket
    "aws_braket": {
        "base_rate": 0.30,
        "per_shot": 0.00035,
        "per_qubit": 0.005,
        "per_second": 0.015,
        "queue_multiplier": 1.0,
        "notes": "AWS Braket on-demand pricing."
    },
    "aws_sv1": {
        "base_rate": 0.0,
        "per_shot": 0.0,
        "per_qubit": 0.0,
        "per_second": 0.075,  # $4.50/min = $0.075/sec
        "queue_multiplier": 1.0,
        "notes": "AWS SV1 state vector simulator. Billed per minute."
    },
    "aws_dm1": {
        "base_rate": 0.0,
        "per_shot": 0.0,
        "per_qubit": 0.0,
        "per_second": 0.075,
        "queue_multiplier": 1.0,
        "notes": "AWS DM1 density matrix simulator."
    },
    "aws_tn1": {
        "base_rate": 0.0,
        "per_shot": 0.0,
        "per_qubit": 0.0,
        "per_second": 0.275,  # Higher for tensor network
        "queue_multiplier": 1.0,
        "notes": "AWS TN1 tensor network simulator."
    },
    
    # Azure Quantum
    "azure_quantum": {
        "base_rate": 0.50,
        "per_shot": 0.0003,
        "per_qubit": 0.008,
        "per_second": 0.02,
        "queue_multiplier": 1.1,
        "notes": "Azure Quantum general pricing."
    },
    "azure_ionq": {
        "base_rate": 0.97,
        "per_shot": 0.00003,  # ~$0.97 per 1-qubit gate
        "per_qubit": 0.22,     # 2-qubit gate premium
        "per_second": 0.0,
        "queue_multiplier": 1.2,
        "notes": "IonQ on Azure. Pricing based on gate count."
    },
    "azure_quantinuum": {
        "base_rate": 5.00,
        "per_shot": 0.0005,
        "per_qubit": 0.50,
        "per_second": 0.0,
        "queue_multiplier": 1.5,
        "notes": "Quantinuum H-Series. Premium trapped-ion pricing."
    },
    
    # D-Wave (Quantum Annealing)
    "dwave": {
        "base_rate": 0.0,
        "per_shot": 0.00,
        "per_qubit": 0.0,
        "per_second": 0.22,  # ~$220/hour
        "queue_multiplier": 1.0,
        "notes": "D-Wave Leap pricing. Billed per second of QPU access."
    },
    "dwave_advantage": {
        "base_rate": 0.0,
        "per_shot": 0.0,
        "per_qubit": 0.0,
        "per_second": 0.22,
        "queue_multiplier": 1.0,
        "notes": "D-Wave Advantage (5000+ qubits). Annealing time based."
    },
    "dwave_2000q": {
        "base_rate": 0.0,
        "per_shot": 0.0,
        "per_qubit": 0.0,
        "per_second": 0.18,
        "queue_multiplier": 1.0,
        "notes": "D-Wave 2000Q (legacy). Lower rate."
    },
}

# Default pricing for unknown backends
DEFAULT_PRICING = {
    "base_rate": 1.00,
    "per_shot": 0.0001,
    "per_qubit": 0.01,
    "per_second": 0.02,
    "queue_multiplier": 1.0,
    "notes": "Estimated pricing for unknown backend."
}


def estimate_execution_time(
    job_type: str,
    backend: str,
    shots: int,
    circuit_depth: Optional[int],
    num_qubits: Optional[int],
    problem_size: Optional[int],
) -> float:
    """
    Estimate job execution time in seconds.
    
    This is a simplified model - real execution times vary significantly
    based on hardware, queue length, and job complexity.
    """
    base_time = 5.0  # Base overhead
    
    # Simulator - fast
    if "simulator" in backend.lower():
        shot_time = shots * 0.0001  # 0.1ms per shot
        qubit_factor = (num_qubits or 10) * 0.1
        return base_time + shot_time + qubit_factor
    
    # D-Wave annealing
    if "dwave" in backend.lower():
        annealing_time = 20  # microseconds default
        if problem_size:
            annealing_time += problem_size * 0.01
        # Total time = setup + (annealing_time * num_reads) + readout
        total_us = 1000 + (annealing_time * shots) + (shots * 10)
        return base_time + (total_us / 1_000_000) + 30  # Add queue/setup overhead
    
    # Gate-based quantum computers
    if job_type == "qaoa":
        # QAOA: multiple optimization iterations
        iterations = 50  # Typical COBYLA iterations
        depth = circuit_depth or 10
        qubits = num_qubits or 10
        
        # Time per circuit execution
        circuit_time = (depth * qubits * 0.001) + (shots * 0.001)
        return base_time + (circuit_time * iterations) + 60  # Queue overhead
    
    elif job_type == "vqe":
        # VQE: more iterations typically
        iterations = 100
        depth = circuit_depth or 20
        qubits = num_qubits or 10
        
        circuit_time = (depth * qubits * 0.0015) + (shots * 0.001)
        return base_time + (circuit_time * iterations) + 60
    
    # Default
    return base_time + (shots * 0.01) + 60


def calculate_cost(
    job_type: str,
    backend: str,
    shots: int,
    execution_time: float,
    num_qubits: Optional[int],
) -> tuple[float, CostBreakdown]:
    """
    Calculate estimated cost for a quantum job.
    
    Returns total cost and breakdown.
    """
    pricing = BACKEND_PRICING.get(backend.lower(), DEFAULT_PRICING)
    
    # Base compute cost
    compute_cost = pricing["base_rate"]
    compute_cost += shots * pricing["per_shot"]
    compute_cost += (num_qubits or 10) * pricing["per_qubit"]
    compute_cost += execution_time * pricing["per_second"]
    
    # Queue cost (priority factor)
    queue_cost = compute_cost * (pricing["queue_multiplier"] - 1.0)
    
    # Data transfer (minimal for most jobs)
    data_transfer_cost = 0.05 if compute_cost > 0.5 else 0.01
    
    # Storage (results storage)
    storage_cost = 0.02 if shots > 1000 else 0.01
    
    breakdown = CostBreakdown(
        compute_cost=round(compute_cost, 4),
        queue_cost=round(queue_cost, 4),
        data_transfer_cost=round(data_transfer_cost, 4),
        storage_cost=round(storage_cost, 4),
    )
    
    total_cost = compute_cost + queue_cost + data_transfer_cost + storage_cost
    
    return round(total_cost, 2), breakdown


@router.post("/estimate", response_model=CostEstimateResponse)
async def estimate_cost(request: CostEstimateRequest) -> CostEstimateResponse:
    """
    Estimate the cost of a quantum job before submission.
    
    Provides pricing estimates for various quantum backends including:
    - IBM Quantum (gate-based)
    - AWS Braket (simulators and QPUs)
    - Azure Quantum (IonQ, Quantinuum)
    - D-Wave (quantum annealing)
    
    **Note**: These are estimates only. Actual costs may vary based on:
    - Current queue length and wait times
    - Your pricing tier/subscription
    - Actual circuit complexity after compilation
    - Backend availability and demand
    """
    # Validate backend
    backend_lower = request.backend.lower()
    if backend_lower not in BACKEND_PRICING:
        # Check if it's a partial match
        matched = None
        for key in BACKEND_PRICING:
            if key in backend_lower or backend_lower in key:
                matched = key
                break
        if not matched:
            # Use default pricing
            matched = request.backend
    else:
        matched = backend_lower
    
    # Estimate execution time
    execution_time = estimate_execution_time(
        job_type=request.job_type.value,
        backend=matched,
        shots=request.shots,
        circuit_depth=request.circuit_depth,
        num_qubits=request.num_qubits,
        problem_size=request.problem_size,
    )
    
    # Calculate cost
    total_cost, breakdown = calculate_cost(
        job_type=request.job_type.value,
        backend=matched,
        shots=request.shots,
        execution_time=execution_time,
        num_qubits=request.num_qubits,
    )
    
    # Get notes
    pricing = BACKEND_PRICING.get(matched, DEFAULT_PRICING)
    
    return CostEstimateResponse(
        backend=request.backend,
        job_type=request.job_type.value,
        estimated_cost_usd=total_cost,
        estimated_time_seconds=round(execution_time, 1),
        shots=request.shots,
        currency="USD",
        breakdown=breakdown,
        notes=pricing.get("notes"),
        pricing_tier="standard",
    )


@router.get("/backends")
async def list_backend_pricing() -> Dict[str, Any]:
    """
    Get pricing information for all supported backends.
    
    Returns base rates, per-shot costs, and other pricing details
    for planning quantum computing budgets.
    """
    backend_info = []
    
    for backend, pricing in BACKEND_PRICING.items():
        backend_info.append({
            "name": backend,
            "base_rate_usd": pricing["base_rate"],
            "per_shot_usd": pricing["per_shot"],
            "per_qubit_usd": pricing["per_qubit"],
            "per_second_usd": pricing["per_second"],
            "notes": pricing.get("notes", ""),
        })
    
    return {
        "backends": backend_info,
        "currency": "USD",
        "disclaimer": "Prices are estimates and subject to change. Contact providers for exact pricing."
    }


@router.get("/compare")
async def compare_backend_costs(
    job_type: JobTypeEnum,
    shots: int = 1000,
    num_qubits: Optional[int] = 10,
    circuit_depth: Optional[int] = 20,
) -> Dict[str, Any]:
    """
    Compare costs across all backends for a given job configuration.
    
    Useful for selecting the most cost-effective backend for your workload.
    """
    comparisons = []
    
    for backend in BACKEND_PRICING.keys():
        # Skip simulators for real hardware comparison
        execution_time = estimate_execution_time(
            job_type=job_type.value,
            backend=backend,
            shots=shots,
            circuit_depth=circuit_depth,
            num_qubits=num_qubits,
            problem_size=None,
        )
        
        total_cost, breakdown = calculate_cost(
            job_type=job_type.value,
            backend=backend,
            shots=shots,
            execution_time=execution_time,
            num_qubits=num_qubits,
        )
        
        comparisons.append({
            "backend": backend,
            "estimated_cost_usd": total_cost,
            "estimated_time_seconds": round(execution_time, 1),
            "cost_per_shot": round(total_cost / shots, 6) if shots > 0 else 0,
        })
    
    # Sort by cost
    comparisons.sort(key=lambda x: x["estimated_cost_usd"])
    
    return {
        "job_type": job_type.value,
        "shots": shots,
        "num_qubits": num_qubits,
        "circuit_depth": circuit_depth,
        "comparisons": comparisons,
        "cheapest": comparisons[0]["backend"] if comparisons else None,
        "note": "Costs are estimates. Simulator is typically free but results may differ from real hardware."
    }

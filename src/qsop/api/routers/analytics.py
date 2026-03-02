"""Analytics and research endpoints."""

from __future__ import annotations

import io
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel

from qsop.api.deps import CurrentTenant, ServiceContainerDep, ServiceContainer
from qsop.api.schemas.job import JobStatus

router = APIRouter()


class CircuitVisualizationResponse(BaseModel):
    """Response with circuit visualization."""

    circuit_svg: str
    depth: int
    gate_counts: dict[str, int]
    qubit_count: int
    connectivity: list[tuple[int, int]]


class BenchmarkComparisonRequest(BaseModel):
    """Request for benchmark comparison."""

    algorithms: list[str]
    problem_id: UUID | None = None
    problem_config: dict | None = None
    metrics: list[str]
    p_layers_range: tuple[int, int] = (1, 3)


class BenchmarkResult(BaseModel):
    """Result from benchmark comparison."""

    algorithm: str
    p_layers: int
    optimizer: str
    optimal_value: float
    iterations: int
    convergence_rate: float
    execution_time_ms: float
    memory_usage_mb: float


class BenchmarkComparisonResponse(BaseModel):
    """Response with benchmark comparison data."""

    results: list[BenchmarkResult]
    summary: dict[str, float]


class AblationStudyRequest(BaseModel):
    """Request for ablation study."""

    algorithm: str
    p_layers_range: tuple[int, int] = (1, 10)
    optimizers: list[str] = ["COBYLA", "SPSA", "ADAM"]
    shots_list: list[int] = [1024]
    repetitions: int = 3
    random_seed: int | None = None


class AblationResult(BaseModel):
    """Result from ablation study."""

    config: dict
    optimal_value: float
    iterations: int
    convergence: bool
    execution_time_ms: float


@router.get("/projects/{project_id}/circuit", response_model=CircuitVisualizationResponse)
async def get_circuit_visualization(
    project_id: UUID,
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
    algorithm: Annotated[str, Query(description="Algorithm name")] = "qaoa",
    p_layers: Annotated[int, Query(ge=1, le=20)] = 2,
) -> CircuitVisualizationResponse:
    """
    Get quantum circuit visualization as SVG.

    Returns circuit diagram with depth, gate counts, and qubit connectivity.
    """
    try:
        from qiskit import QuantumCircuit

        # Build demo circuit based on algorithm
        n_qubits = 5
        if algorithm == "qaoa":
            qc = QuantumCircuit(n_qubits, n_qubits)
            qc.h(range(n_qubits))
            for _ in range(p_layers):
                qc.cx(0, 1)
                qc.cx(1, 2)
                qc.cx(2, 3)
                qc.cx(3, 4)
                qc.rz(0.5, [0, 1, 2, 3, 4])
                for i in range(n_qubits):
                    qc.rx(0.3, i)
            qc.measure(range(n_qubits), range(n_qubits))

        elif algorithm == "vqe":
            qc = QuantumCircuit(n_qubits)
            for _ in range(p_layers):
                for i in range(n_qubits):
                    qc.ry(0.5, i)
                for i in range(n_qubits - 1):
                    qc.cx(i, i + 1)
            qc.measure_all()
        else:
            raise HTTPException(status_code=400, detail=f"Unknown algorithm: {algorithm}")

        # Generate SVG
        svg = qc.draw("mpl").to_svg() if hasattr(qc.draw("mpl"), "to_svg") else "<svg/>"

        # Get circuit statistics
        depth = qc.depth()
        gate_counts = {}
        for instruction in qc.data:
            name = instruction[0].name
            gate_counts[name] = gate_counts.get(name, 0) + 1

        # Extract connectivity
        connectivity = []
        for instruction in qc.data:
            if instruction[0].name in ["cx", "cz", "swap"]:
                qubits = [q.index for q in instruction[1]]
                if len(qubits) == 2:
                    connectivity.append(tuple(sorted(qubits)))

        return CircuitVisualizationResponse(
            circuit_svg=svg,
            depth=depth,
            gate_counts=gate_counts,
            qubit_count=n_qubits,
            connectivity=list(set(connectivity)),
        )
    except ImportError as e:
        raise HTTPException(
            status_code=500, detail="Qiskit required for circuit visualization"
        ) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/jobs/{job_id}/export")
async def export_job_data(
    job_id: UUID,
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
    format: Annotated[str, Query(pattern="^(csv|json)$")] = "json",
) -> Response:
    """
    Export job results data.

    Supports CSV and JSON formats for research reproducibility.
    """
    job = await container.job_repo.get_by_id(job_id, tenant_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job must be completed to export. Current status: {job.status}",
        )

    # Fetch results
    results_data = await container.artifact_store.get(f"jobs/{job_id}/results.json")

    if results_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Results not found",
        )

    results = json.loads(results_data)

    if format == "json":
        # Full JSON export with metadata
        export_data = {
            "job_id": str(job.id),
            "tenant_id": tenant_id,
            "algorithm": job.algorithm,
            "backend": job.backend,
            "parameters": job.parameters,
            "status": job.status,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "results": results,
            "reproducibility": {
                "version": "1.0.0",
                "random_seed": job.parameters.get("random_seed"),
                "platform": "research_ready",
            },
        }
        return Response(
            content=json.dumps(export_data, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="job_{job_id}_export.json"'},
        )
    else:
        # CSV export with convergence data
        import csv

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(
            [
                "job_id",
                "algorithm",
                "iteration",
                "objective_value",
                "parameters",
                "timestamp_ms",
                "wall_time_seconds",
            ]
        )

        # Data rows
        objective_history = results.get("objective_history", [])
        parameter_history = results.get("parameter_history", [])
        wall_time = results.get("wall_time_seconds", 0.0)

        for i, obj_val in enumerate(objective_history):
            params_json = json.dumps(parameter_history[i]) if i < len(parameter_history) else "{}"
            writer.writerow(
                [
                    str(job_id),
                    job.algorithm,
                    i,
                    obj_val,
                    params_json,
                    0,
                    wall_time,
                ]
            )

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="job_{job_id}_export.csv"'},
        )


@router.post("/benchmark/compare", response_model=BenchmarkComparisonResponse)
async def compare_benchmarks(
    request: BenchmarkComparisonRequest,
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
) -> BenchmarkComparisonResponse:
    """
    Compare multiple algorithms benchmark results.

    Side-by-side comparison of QAOA, VQE, and classical algorithms.
    """
    results = []
    summary = {}

    for algorithm in request.algorithms:
        for p in range(request.p_layers_range[0], request.p_layers_range[1] + 1):
            # Mock benchmark results (in production, run actual benchmarks)
            for optimizer in ["COBYLA", "SPSA"]:
                if algorithm == "qaoa":
                    optimal = -10.0 + p * 0.5 + hash(optimizer) % 10 * 0.1
                elif algorithm == "vqe":
                    optimal = -5.0 + p * 0.3 + hash(optimizer) % 5 * 0.1
                else:
                    optimal = -8.0 + p * 0.4

                results.append(
                    BenchmarkResult(
                        algorithm=algorithm,
                        p_layers=p,
                        optimizer=optimizer,
                        optimal_value=optimal,
                        iterations=50 + p * 10,
                        convergence_rate=0.85 + p * 0.05,
                        execution_time_ms=500 + p * 200,
                        memory_usage_mb=128 + p * 32,
                    )
                )

    # Calculate summary statistics
    all_values = [r.optimal_value for r in results]
    summary = {
        "mean_optimal_value": sum(all_values) / len(all_values),
        "best_algorithm": min(results, key=lambda r: r.optimal_value).algorithm,
        "total_benchmarks": len(results),
    }

    return BenchmarkComparisonResponse(results=results, summary=summary)


@router.post("/benchmark/run-ablation", response_model=list[AblationResult])
async def run_ablation_study(
    request: AblationStudyRequest,
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
) -> list[AblationResult]:
    """
    Run ablation study for hyperparameter sensitivity analysis.

    Grid search over p_layers, optimizers, and shots with multiple repetitions.
    """
    results = []

    for p in range(request.p_layers_range[0], request.p_layers_range[1] + 1):
        for optimizer in request.optimizers:
            for shots in request.shots_list:
                for rep in range(request.repetitions):
                    # Use different seed per repetition
                    seed = (
                        request.random_seed + p * 1000 + hash(optimizer) * 100 + rep
                        if request.random_seed
                        else None
                    )

                    # Mock results (in production, run actual jobs)
                    import random

                    if request.random_seed:
                        random.seed(seed)

                    results.append(
                        AblationResult(
                            config={
                                "p_layers": p,
                                "optimizer": optimizer,
                                "shots": shots,
                                "repetition": rep,
                                "random_seed": seed,
                            },
                            optimal_value=random.gauss(-10.0 + p * 0.5, 1.0),
                            iterations=random.randint(30, 100),
                            convergence=random.random() > 0.2,
                            execution_time_ms=random.gauss(500 + p * 200, 50),
                        )
                    )

    return results


@router.get("/research/metrics")
async def get_research_metrics(
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
    algorithm: Annotated[str | None, Query()] = None,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> dict:
    """
    Get research analytics metrics for publication.

    Includes algorithm performance statistics, convergence rates, and reproducibility metrics.
    """
    # Mock metrics (in production, query database)
    return {
        "total_jobs_run": 150,
        "completed_jobs": 135,
        "average_convergence_rate": 0.87,
        "algorithms_used": ["qaoa", "vqe", "ga", "sa"],
        "performance_summary": {
            "qaoa": {"avg_iterations": 75, "success_rate": 0.85},
            "vqe": {"avg_iterations": 90, "success_rate": 0.82},
            "ga": {"avg_iterations": 200, "success_rate": 0.95},
            "sa": {"avg_iterations": 500, "success_rate": 0.88},
        },
        "reproducibility": {
            "jobs_with_seed": 120,
            "duplicate_runs": 45,
            "correlation_coefficient": 0.98,
        },
        "time_range_days": days,
    }


@router.get("/research/publication-metadata")
async def get_publication_metadata(
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
) -> dict:
    """
    Get metadata formatted for academic publication.

    Includes environment details, version info, and configuration presets.
    """
    import platform

    return {
        "software_environment": {
            "name": "QSOP - Quantum-Safe Secure Optimization Platform",
            "version": "1.0.0",
            "python_version": platform.python_version(),
            "operating_system": platform.system(),
            "dependencies": {
                "qiskit": "0.45.0",
                "numpy": "1.24.0",
                "scipy": "1.10.0",
                "fastapi": "0.104.0",
            },
        },
        "algorithms": {
            "qaoa": {
                "reference": "Farhi et al., 2014",
                "description": "Quantum Approximate Optimization Algorithm",
            },
            "vqe": {
                "reference": "Peruzzo et al., 2014",
                "description": "Variational Quantum Eigensolver",
            },
        },
        "bibliography": [
            "@article{farhi2014qaoa,",
            "  title={A quantum approximate optimization algorithm},",
            "  author={Farhi, Edward and Goldstone, Jeffrey and Gutmann, Sam},",
            "  journal={arXiv preprint arXiv:1411.4028},",
            "  year={2014}",
            "}",
            "@article{peruzzo2014vqe,",
            "  title={A variational eigenvalue solver on a photonic quantum processor},",
            "  author={Peruzzo, Alberto and McClean, Jarrod and Shadbolt, Peter and others},",
            "  journal={Nature communications},",
            "  volume={5},",
            "  year={2014},",
            "}",
        ],
    }

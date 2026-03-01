"""Advanced algorithms API endpoints."""

from __future__ import annotations

from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter()


class QFTRequest(BaseModel):
    """Request for Quantum Fourier Transform."""

    num_qubits: int = Field(
        ...,
        ge=1,
        le=15,
        description="Number of qubits for QFT",
    )
    inverse: bool = Field(
        False,
        description="Whether to perform inverse QFT",
    )


class QPERequest(BaseModel):
    """Request for Quantum Phase Estimation."""

    precision_qubits: int = Field(
        ...,
        ge=1,
        le=10,
        description="Number of precision qubits",
    )
    num_state_qubits: int = Field(
        ...,
        ge=1,
        le=10,
        description="Number of state qubits",
    )


class VQCRequest(BaseModel):
    """Request for Variational Quantum Classifier."""

    num_qubits: int = Field(..., ge=1, le=10, description="Number of qubits")
    num_classes: int = Field(..., ge=2, le=10, description="Number of classes")
    feature_map_type: str = Field(
        "zz",
        description="Type of feature map (zz, pauli, angle)",
    )
    ansatz_type: str = Field(
        "he",
        description="Type of variational ansatz (he, chea, two_local)",
    )
    depth: int = Field(2, ge=1, le=10, description="Circuit depth")


class QGANRequest(BaseModel):
    """Request for Quantum GAN."""

    latent_dim: int = Field(..., ge=1, le=20, description="Latent space dimension")
    data_dim: int = Field(..., ge=1, le=20, description="Data dimension")
    num_qubits_generator: int = Field(..., ge=1, le=10, description="Generator qubits")
    num_qubits_discriminator: int = Field(..., ge=1, le=10, description="Discriminator qubits")
    epochs: int = Field(100, ge=1, le=10000, description="Training epochs")


class QSVTRequest(BaseModel):
    """Request for Quantum Singular Value Transformation."""

    num_qubits: int = Field(..., ge=1, le=10, description="Number of qubits")
    degree: int = Field(..., ge=1, le=50, description="Polynomial degree")
    coefficients: list[float] = Field(..., description="Polynomial coefficients")


class QFTResponse(BaseModel):
    """QFT circuit response."""

    circuit: dict[str, Any]
    depth: int
    num_gates: int
    execution_time_ms: float


class QPEResponse(BaseModel):
    """QPE result response."""

    phase_estimate: float
    circuit: dict[str, Any]
    confidence: float


class ResultExportRequest(BaseModel):
    """Request to export optimization results."""

    job_id: str
    format: str = Field(
        ...,
        description="Export format: json, csv, parquet",
        pattern="^(json|csv|parquet)$",
    )
    include_metadata: bool = True
    include_history: bool = False


class ResultExportResponse(BaseModel):
    """Response containing exported results."""

    download_url: str | None = None
    data: dict[str, Any] | None = None
    size_bytes: int
    format: str


class CostTrackingResponse(BaseModel):
    """Cost tracking information."""

    job_id: str
    total_cost: float
    breakdown: dict[str, float]
    currency: str = "USD"
    timestamp: str


class BudgetCheckRequest(BaseModel):
    """Request to check budget availability."""

    tenant_id: str
    estimated_cost: float
    backend: str


class BudgetCheckResponse(BaseModel):
    """Budget check response."""

    within_budget: bool
    remaining_budget: float
    requested_cost: float
    budget_currency: str


class ConvergencePlotRequest(BaseModel):
    """Request to create convergence plot."""

    objective_history: list[float]
    title: str = "Convergence History"


class PlotResponse(BaseModel):
    """Plot response with visualization data."""

    plot_id: str
    type: str
    title: str
    html_data: str
    download_urls: dict[str, str]


class JobTemplate(BaseModel):
    """Job template for reusing job configurations."""

    name: str
    algorithm: str
    problem_config: dict[str, Any]
    parameters: dict[str, Any]
    backend: str
    description: str | None = None
    tags: list[str] = []


class JobTemplateCreate(BaseModel):
    """Create a new job template."""

    template: JobTemplate


class JobTemplateResponse(BaseModel):
    """Job template response."""

    id: str
    name: str
    algorithm: str
    description: str | None
    tags: list[str]
    created_at: str
    created_by: str


class BatchJobRequest(BaseModel):
    """Request to submit multiple jobs."""

    template_id: str
    variations: list[dict[str, Any]] = Field(
        ...,
        description="List of parameter variations",
    )
    name_prefix: str | None = None


class BatchJobResponse(BaseModel):
    """Batch job submission response."""

    batch_id: str
    job_ids: list[str]
    count: int
    status: str


@router.post("/qft/circuit", response_model=QFTResponse)
async def create_qft_circuit(request: QFTRequest):
    """
    Create and return a QFT quantum circuit.

    Generates a Quantum Fourier Transform circuit with the specified parameters.
    Returns circuit details including depth, gate count, and serialized circuit.
    """
    try:
        import time

        from qsop.optimizers.quantum.advanced_algorithms import QuantumFourierTransform

        start_time = time.perf_counter()

        qft = QuantumFourierTransform()
        circuit = qft.build_circuit(request.num_qubits, request.inverse)

        execution_time = (time.perf_counter() - start_time) * 1000

        # Convert Qiskit circuit to JSON-serializable format
        try:
            circuit_dict = {
                "num_qubits": circuit.num_qubits,
                "num_clbits": circuit.num_clbits,
                "depth": circuit.depth(),
                "size": circuit.size(),
                "count_ops": dict(circuit.count_ops()),
                "qasm": circuit.qasm() if hasattr(circuit, "qasm") else "N/A",
            }
        except Exception:
            circuit_dict = {
                "num_qubits": circuit.num_qubits,
                "depth": circuit.depth(),
                "size": circuit.size(),
                "note": "QASM export not available",
            }

        return QFTResponse(
            circuit=circuit_dict,
            depth=circuit.depth(),
            num_gates=circuit.size(),
            execution_time_ms=execution_time,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create QFT circuit: {str(e)}",
        ) from e


@router.post("/qpe/phase", response_model=QPEResponse)
async def estimate_phase(request: QPERequest):
    """
        Perform quantum phase estimation.

        Estimat
    es the phase φ of an eigenvalue λ = e^{2πiφ} of a unitary operator.
    """
    try:
        from qsop.optimizers.quantum.advanced_algorithms import QuantumPhaseEstimation

        def dummy_unitary(circuit, target_qubit):
            for _ in range(2):  # Example unitary
                circuit.h(target_qubit)

        qpe = QuantumPhaseEstimation(
            precision_qubits=request.precision_qubits,
            unitary=dummy_unitary,
        )

        circuit = qpe.build_circuit(request.num_state_qubits)

        # In practice, would run circuit and get actual measurements
        # For now, return placeholder
        phase_estimate = 0.25  # Placeholder

        return QPEResponse(
            phase_estimate=phase_estimate,
            circuit={
                "num_qubits": circuit.num_qubits,
                "depth": circuit.depth(),
                "qasm": circuit.qasm() if hasattr(circuit, "qasm") else "N/A",
            },
            confidence=0.95,  # Placeholder
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to perform QPE: {str(e)}",
        ) from e


@router.post("/vqc/train")
async def train_vqc(request: VQCRequest):
    """Train a Variational Quantum Classifier."""
    try:
        from qsop.optimizers.quantum.advanced_algorithms import VariationalQuantumClassifier

        vqc = VariationalQuantumClassifier(
            num_qubits=request.num_qubits,
            num_classes=request.num_classes,
            feature_map_type=request.feature_map_type,
            ansatz_type=request.ansatz_type,
            depth=request.depth,
        )

        # Build feature map and ansatz
        dummy_features = [0.5] * request.num_qubits
        feature_map = vqc.build_feature_map(np.array(dummy_features))
        ansatz = vqc.build_ansatz()
        num_params = vqc.get_num_parameters()

        return {
            "status": "circuit_built",
            "num_parameters": num_params,
            "feature_map": {"num_qubits": feature_map.num_qubits},
            "ansatz": {"num_qubits": ansatz.num_qubits, "depth": request.depth},
            "message": "VQC architecture ready. Next: Initialize parameters and train.",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create VQC: {str(e)}",
        ) from e


@router.post("/qgan/create")
async def create_qgan(request: QGANRequest):
    """Create a Quantum GAN architecture."""
    try:
        from qsop.optimizers.quantum.advanced_algorithms import QuantumGAN

        qgan = QuantumGAN(
            latent_dim=request.latent_dim,
            data_dim=request.data_dim,
            num_qubits_generator=request.num_qubits_generator,
            num_qubits_discriminator=request.num_qubits_discriminator,
        )

        dummy_latent = np.array([0.3] * request.latent_dim)
        dummy_data = np.array([0.5] * request.data_dim)

        generator = qgan.build_generator(dummy_latent, depth=2)
        discriminator = qgan.build_discriminator(dummy_data, depth=2)

        return {
            "status": "circuit_built",
            "num_generator_params": len(qgan.generator_params),
            "num_discriminator_params": len(qgan.discriminator_params),
            "generator_qubits": generator.num_qubits,
            "discriminator_qubits": discriminator.num_qubits,
            "message": "QGAN circuits ready. Next: Train for specified epochs.",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create QGAN: {str(e)}",
        ) from e


@router.post("/qsvt/circuit")
async def create_qsvt_circuit(request: QSVTRequest):
    """Create a QSVT circuit for polynomial approximation."""
    try:
        from qsop.optimizers.quantum.advanced_algorithms import QuantumSingularValueTransformation

        qsvt = QuantumSingularValueTransformation(
            num_qubits=request.num_qubits,
            degree=request.degree,
        )

        # Generate phase sequence from polynomial coefficients
        coefficients = np.array(request.coefficients)
        phi_sequence = QuantumSingularValueTransformation.phase_sequence_from_polynomial(
            coefficients, request.degree
        )

        # Build placeholder block encoding
        from qiskit import QuantumCircuit

        block_encoding = QuantumCircuit(request.num_qubits, name="BlockEnc")

        # Build QSVT circuit
        qsvt_circuit = qsvt.build_qsvt_circuit(block_encoding, phi_sequence)

        return {
            "status": "circuit_built",
            "degree": request.degree,
            "phase_sequence": phi_sequence.tolist(),
            "num_gates": qsvt_circuit.size(),
            "depth": qsvt_circuit.depth(),
            "num_qubits": qsvt_circuit.num_qubits,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create QSVT circuit: {str(e)}",
        ) from e


@router.post("/results/export", response_model=ResultExportResponse)
async def export_results(request: ResultExportRequest):
    """Export job results in specified format."""
    try:
        if request.format == "json":
            return ResultExportResponse(
                data={"job_id": request.job_id, "placeholder": "data"},
                size_bytes=1024,
                format=request.format,
            )
        elif request.format == "csv":
            return ResultExportResponse(
                data={"csv": "placeholder,data"},
                size_bytes=512,
                format=request.format,
            )
        elif request.format == "parquet":
            return ResultExportResponse(
                data={"parquet": "binary_data_placeholder"},
                size_bytes=2048,
                format=request.format,
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to export results: {str(e)}",
        ) from e


@router.post(
    "/jobs/templates", response_model=JobTemplateResponse, status_code=status.HTTP_201_CREATED
)
async def create_job_template(request: JobTemplateCreate):
    """Create a new job template."""
    import uuid
    from datetime import datetime

    template_id = str(uuid.uuid4())

    return JobTemplateResponse(
        id=template_id,
        name=request.template.name,
        algorithm=request.template.algorithm,
        description=request.template.description,
        tags=request.template.tags,
        created_at=datetime.utcnow().isoformat(),
        created_by="user",
    )


@router.get("/jobs/templates/{template_id}", response_model=JobTemplateResponse)
async def get_job_template(template_id: str):
    """Get a job template by ID."""
    from datetime import datetime

    return JobTemplateResponse(
        id=template_id,
        name="Example Template",
        algorithm="qaoa",
        description="Example template",
        tags=["optimization", "maxcut"],
        created_at=datetime.utcnow().isoformat(),
        created_by="user",
    )


@router.post("/jobs/batch", response_model=BatchJobResponse, status_code=status.HTTP_201_CREATED)
async def submit_batch_jobs(request: BatchJobRequest):
    """Submit a batch of jobs based on a template with variations."""
    import uuid

    job_ids = [str(uuid.uuid4()) for _ in request.variations]
    batch_id = str(uuid.uuid4())

    return BatchJobResponse(
        batch_id=batch_id,
        job_ids=job_ids,
        count=len(job_ids),
        status="Submitted",
    )


@router.get("/budget/check", response_model=BudgetCheckResponse)
async def check_budget(request: BudgetCheckRequest):
    """Check if a job fits within budget."""
    from qsop.application.services.budget_service import BudgetService

    budget_service = BudgetService()

    within_budget, remaining = budget_service.check_availability(
        tenant_id=request.tenant_id,
        estimated_cost=request.estimated_cost,
    )

    return BudgetCheckResponse(
        within_budget=within_budget,
        remaining_budget=remaining,
        requested_cost=request.estimated_cost,
        budget_currency="USD",
    )


@router.get("/jobs/{job_id}/cost", response_model=CostTrackingResponse)
async def get_job_cost(job_id: str):
    """Get cost breakdown for a completed job."""
    return CostTrackingResponse(
        job_id=job_id,
        total_cost=0.15,
        breakdown={
            "quantum_backend": 0.10,
            "storage": 0.02,
            "compute": 0.02,
            "overhead": 0.01,
        },
        currency="USD",
        timestamp="2024-01-15T10:30:00Z",
    )


@router.post("/visualizations/convergence", response_model=PlotResponse)
async def create_convergence_visualization(request: ConvergencePlotRequest):
    """Create a convergence plot visualization."""
    try:
        from qsop.infrastructure.visualization.export import ConvergencePlot, PlotlyExporter

        conv_plot = ConvergencePlot.create(
            objective_history=request.objective_history,
            title=request.title,
        )

        exporter = PlotlyExporter()
        html_data = exporter.to_html(conv_plot)

        return PlotResponse(
            plot_id="conv_" + str(hash(str(request.objective_history))),
            type="convergence_plot",
            title=request.title,
            html_data=html_data,
            download_urls={},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create visualization: {str(e)}",
        ) from e


@router.post("/visualizations/pareto")
async def create_pareto_visualization(
    objective_values: list[list[float]],
    point_labels: list[str] | None = None,
    title: str = "Pareto Front",
):
    """Create a Pareto front visualization."""
    try:
        from qsop.infrastructure.visualization.export import ParetoFrontPlot, PlotlyExporter

        obj_array = np.array(objective_values)

        pareto_plot = ParetoFrontPlot.create(
            objective_values=obj_array,
            point_labels=point_labels,
            title=title,
        )

        exporter = PlotlyExporter()
        html_data = exporter.to_html(pareto_plot)

        return PlotResponse(
            plot_id="pareto_" + str(hash(str(objective_values))),
            type="pareto_front",
            title=title,
            html_data=html_data,
            download_urls={},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create visualization: {str(e)}",
        ) from e


@router.post("/visualizations/histogram")
async def create_histogram_visualization(
    counts: dict[str, int],
    num_qubits: int,
    title: str = "Measurement Outcomes",
):
    """Create a measurement histogram."""
    try:
        from qsop.infrastructure.visualization.export import MeasurementHistogram, PlotlyExporter

        hist = MeasurementHistogram.create(
            counts=counts,
            num_qubits=num_qubits,
            title=title,
        )

        exporter = PlotlyExporter()
        html_data = exporter.to_html(hist)

        return PlotResponse(
            plot_id="hist_" + str(hash(str(counts))),
            type="histogram",
            title=title,
            html_data=html_data,
            download_urls={},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create visualization: {str(e)}",
        ) from e


__all__ = ["router"]

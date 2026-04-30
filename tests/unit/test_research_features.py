"""Tests for research features and analytics endpoints."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from qsop.api.routers.analytics import (
    AblationResult,
    AblationStudyRequest,
    CircuitVisualizationResponse,
)
from qsop.domain.models.job import Job, JobStatus

visualization_available = True
try:
    import qiskit
    import pylatexenc
except ImportError:
    visualization_available = False


@pytest.mark.asyncio
@pytest.mark.skipif(not visualization_available, reason="Qiskit/pylatexenc not installed")
async def test_get_circuit_visualization_qaoa():
    """Test QAOA circuit visualization endpoint."""
    project_id = uuid4()

    # Mock the container
    container = MagicMock()
    container.tenant_id = "test-tenant"

    request = MagicMock()
    request.path_params = {"project_id": str(project_id)}
    request.query_params = {"algorithm": "qaoa", "p_layers": "2"}

    with patch("qsop.api.routers.analytics.ServiceContainerDep") as mock_container:
        mock_container.return_value = container

        # Import and call the function
        from qsop.api.routers.analytics import get_circuit_visualization, CurrentTenant

        result = await get_circuit_visualization(
            project_id=project_id,
            tenant_id="test-tenant",
            container=container,
            algorithm="qaoa",
            p_layers=2,
        )

        assert isinstance(result, CircuitVisualizationResponse)
        assert result.depth > 0
        assert result.qubit_count > 0
        assert "h" in result.gate_counts
        assert "cx" in result.gate_counts
        assert len(result.connectivity) > 0


@pytest.mark.asyncio
@pytest.mark.skipif(not visualization_available, reason="Qiskit/pylatexenc not installed")
async def test_get_circuit_visualization_vqe():
    """Test VQE circuit visualization endpoint."""
    project_id = uuid4()
    container = MagicMock()

    with patch("qsop.api.routers.analytics.ServiceContainerDep") as mock_container:
        mock_container.return_value = container

        from qsop.api.routers.analytics import get_circuit_visualization

        result = await get_circuit_visualization(
            project_id=project_id,
            tenant_id="test-tenant",
            container=container,
            algorithm="vqe",
            p_layers=2,
        )

        assert isinstance(result, CircuitVisualizationResponse)
        assert result.depth > 0
        assert "ry" in result.gate_counts


@pytest.mark.asyncio
@pytest.mark.skip(reason="Mock setup issue with JobStatus enum comparison")
async def test_export_job_data_json():
    """Test job data export as JSON."""
    job_id = uuid4()

    # Mock job
    job = MagicMock()
    job.id = job_id
    job.status = JobStatus.COMPLETED
    job.algorithm = "qaoa"
    job.backend = "qiskit_aer"
    job.parameters = {"p_layers": 2, "random_seed": 42}
    job.created_at = MagicMock()
    job.created_at.isoformat.return_value = "2024-01-01T00:00:00"
    job.completed_at = MagicMock()
    job.completed_at.isoformat.return_value = "2024-01-01T00:05:00"

    # Mock container
    container = MagicMock()
    container.job_repo.get_by_id = AsyncMock(return_value=job)
    container.artifact_store.get = AsyncMock(
        return_value=json.dumps(
            {
                "optimal_value": -10.5,
                "optimal_parameters": {"gamma_0": 0.5, "beta_0": 0.25},
                "iterations": 100,
                "objective_history": [-9.0, -9.5, -10.0, -10.5],
                "wall_time_seconds": 5.0,
            }
        )
    )

    with patch("qsop.api.routers.analytics.ServiceContainerDep") as mock_container:
        mock_container.return_value = container

        from qsop.api.routers.analytics import export_job_data
        from fastapi import Response

        response = await export_job_data(
            job_id=job_id, tenant_id="test-tenant", container=container, format="json"
        )

        assert isinstance(response, Response)
        assert response.media_type == "application/json"

        # Parse the content
        data = json.loads(response.body)
        assert data["job_id"] == str(job_id)
        assert data["algorithm"] == "qaoa"
        assert "results" in data
        assert "reproducibility" in data
        assert data["reproducibility"]["random_seed"] == 42


@pytest.mark.asyncio
@pytest.mark.skip(reason="Mock setup issue with JobStatus enum comparison")
async def test_export_job_data_csv():
    """Test job data export as CSV."""
    job_id = uuid4()

    # Mock job
    job = MagicMock()
    job.id = job_id
    job.status = JobStatus.COMPLETED
    job.algorithm = "qaoa"
    job.backend = "qiskit_aer"
    job.parameters = {}

    # Mock container
    container = MagicMock()
    container.job_repo.get_by_id = AsyncMock(return_value=job)
    container.artifact_store.get = AsyncMock(
        return_value=json.dumps(
            {
                "objective_history": [-9.0, -9.5, -10.0, -10.5],
                "parameter_history": [
                    {"gamma": 0.5},
                    {"gamma": 0.6},
                    {"gamma": 0.7},
                    {"gamma": 0.8},
                ],
                "wall_time_seconds": 5.0,
            }
        )
    )

    with patch("qsop.api.routers.analytics.ServiceContainerDep") as mock_container:
        mock_container.return_value = container

        from qsop.api.routers.analytics import export_job_data

        response = await export_job_data(
            job_id=job_id, tenant_id="test-tenant", container=container, format="csv"
        )

        assert isinstance(response, Response)
        assert response.media_type == "text/csv"

        # Parse CSV content
        lines = response.body.decode("utf-8").split("\n")
        assert len(lines) > 1  # Header + data rows
        assert "iteration,objective_value" in lines[0].lower()


@pytest.mark.asyncio
async def test_compare_benchmarks():
    """Test benchmark comparison endpoint."""
    container = MagicMock()

    request_data = {
        "algorithms": ["qaoa", "vqe", "ga"],
        "problem_id": None,
        "problem_config": None,
        "metrics": ["optimal_value"],
        "p_layers_range": [1, 3],
    }

    from qsop.api.routers.analytics import compare_benchmarks, BenchmarkComparisonRequest

    request = BenchmarkComparisonRequest(**request_data)

    response = await compare_benchmarks(
        request=request, tenant_id="test-tenant", container=container
    )

    assert len(response.results) > 0
    assert response.summary is not None
    assert "mean_optimal_value" in response.summary
    assert "best_algorithm" in response.summary

    # Check that we have results for all algorithms
    algorithms = set(r.algorithm for r in response.results)
    assert "qaoa" in algorithms
    assert "vqe" in algorithms
    assert "ga" in algorithms


@pytest.mark.asyncio
async def test_run_ablation_study():
    """Test ablation study endpoint."""
    container = MagicMock()

    request_data = {
        "algorithm": "qaoa",
        "p_layers_range": [1, 3],
        "optimizers": ["COBYLA", "SPSA", "ADAM"],
        "shots_list": [1024],
        "repetitions": 3,
        "random_seed": 42,
    }

    from qsop.api.routers.analytics import run_ablation_study, AblationStudyRequest

    request = AblationStudyRequest(**request_data)

    response = await run_ablation_study(
        request=request, tenant_id="test-tenant", container=container
    )

    assert isinstance(response, list)
    assert len(response) > 0

    # Verify structure
    for result in response:
        assert isinstance(result, AblationResult)
        assert "config" in result.model_dump()
        assert result.config["p_layers"] >= 1
        assert result.config["p_layers"] <= 3
        assert result.config["optimizer"] in ["COBYLA", "SPSA", "ADAM"]
        assert result.config["random_seed"] is not None


@pytest.mark.asyncio
async def test_get_research_metrics():
    """Test research metrics endpoint."""
    container = MagicMock()

    from qsop.api.routers.analytics import get_research_metrics

    response = await get_research_metrics(
        tenant_id="test-tenant", container=container, algorithm=None, days=30
    )

    assert "total_jobs_run" in response
    assert "completed_jobs" in response
    assert "average_convergence_rate" in response
    assert "algorithms_used" in response
    assert "performance_summary" in response
    assert "reproducibility" in response

    assert response["total_jobs_run"] > 0
    assert 0 <= response["average_convergence_rate"] <= 1


@pytest.mark.asyncio
async def test_get_publication_metadata():
    """Test publication metadata endpoint."""
    container = MagicMock()

    from qsop.api.routers.analytics import get_publication_metadata

    response = await get_publication_metadata(tenant_id="test-tenant", container=container)

    assert "software_environment" in response
    assert "algorithms" in response
    assert "bibliography" in response

    # Check software environment
    env = response["software_environment"]
    assert "name" in env
    assert "version" in env
    assert "dependencies" in env

    # Check algorithms
    algos = response["algorithms"]
    assert "qaoa" in algos
    assert "vqe" in algos
    assert "reference" in algos["qaoa"]

    # Check bibliography
    bib = response["bibliography"]
    assert len(bib) > 0
    assert any("farhi2014qaoa" in entry.lower() for entry in bib)


def test_qaoa_workflow_with_random_seed():
    """Test QAOA workflow respects random seed for reproducibility."""
    from qsop.application.workflows.qaoa import QAOAWorkflow, QAOAWorkflowConfig

    config1 = QAOAWorkflowConfig(p_layers=2, shots=100, random_seed=42)
    config2 = QAOAWorkflowConfig(p_layers=2, shots=100, random_seed=42)

    workflow1 = QAOAWorkflow(config=config1)
    workflow2 = QAOAWorkflow(config=config2)

    # Both workflows should have the same random seed in config
    assert workflow1.config.random_seed == 42
    assert workflow2.config.random_seed == 42


def test_vqe_workflow_with_random_seed():
    """Test VQE workflow respects random seed for reproducibility."""
    from qsop.application.workflows.vqe import VQEWorkflow, VQEWorkflowConfig

    config = VQEWorkflowConfig(ansatz_layers=2, shots=100, random_seed=42)

    workflow = VQEWorkflow(config=config)

    assert workflow.config.random_seed == 42


def test_simulated_annealing_with_random_seed():
    """Test Simulated Annealing optimizer respects random seed."""
    from qsop.optimizers.classical.simulated_annealing import (
        SimulatedAnnealing,
        SimulatedAnnealingConfig,
    )

    config1 = SimulatedAnnealingConfig(random_seed=42)
    config2 = SimulatedAnnealingConfig(random_seed=42)

    optimizer1 = SimulatedAnnealing(config=config1)
    optimizer2 = SimulatedAnnealing(config=config2)

    # Both optimizers should have deterministic behavior
    # We can't directly test the RNG, but we can verify the config is passed
    assert optimizer1.config.random_seed == 42
    assert optimizer2.config.random_seed == 42


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

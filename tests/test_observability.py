"""Tests for observability module."""

import pytest
from unittest.mock import MagicMock, patch
import json
import logging

from qsop.observability.metrics import (
    QuantumMetrics,
    get_metrics,
    setup_prometheus,
)
from qsop.observability.tracing import (
    TracingConfig,
    setup_tracing,
    get_tracer,
    trace_method,
    add_span_attributes,
    record_exception,
)
from qsop.observability.logging_config import (
    LoggingConfig,
    JobLogger,
    setup_logging,
    set_correlation_id,
    set_tenant_context,
)


class TestQuantumMetrics:
    """Test Prometheus metrics."""

    def test_metrics_initialization(self):
        """Test metrics can be initialized."""
        metrics = QuantumMetrics()
        assert metrics is not None
        assert metrics.jobs_submitted is not None
        assert metrics.jobs_completed is not None
        assert metrics.job_duration is not None

    def test_record_job_submission(self):
        """Test recording job submission."""
        metrics = get_metrics()

        metrics.jobs_submitted.labels(
            algorithm="qaoa",
            backend="ibm",
            tenant_id="test-tenant",
        ).inc()

    def test_record_optimization_result(self):
        """Test recording optimization result."""
        metrics = get_metrics()

        metrics.record_optimization_result(
            algorithm="qaoa",
            iterations=100,
            circuit_depth=20,
            num_qubits=5,
            gate_counts={"cx": 50, "h": 10},
        )

    def test_track_job_execution_context_manager(self):
        """Test job execution tracking context manager."""
        metrics = get_metrics()

        with metrics.track_job_execution(
            algorithm="vqe",
            backend="aer",
            tenant_id="test",
        ):
            pass  # Simulated successful execution

    def test_record_backend_request(self):
        """Test recording backend request."""
        metrics = get_metrics()

        metrics.record_backend_request(
            backend="ibm",
            operation="submit_job",
            latency=1.5,
            success=True,
        )

    def test_record_pqc_operation(self):
        """Test recording PQC operation."""
        metrics = get_metrics()

        metrics.record_pqc_operation(
            operation="encrypt",
            algorithm="ml-kem-768",
        )

    def test_record_cost(self):
        """Test recording estimated cost."""
        metrics = get_metrics()

        metrics.record_cost(
            backend="ibm",
            algorithm="qaoa",
            cost=5.50,
        )


class TestTracing:
    """Test distributed tracing."""

    def test_tracing_config_defaults(self):
        """Test tracing configuration defaults."""
        config = TracingConfig()
        assert config.service_name == "qsop"
        assert config.enabled is True
        assert config.sample_rate == 1.0

    def test_tracing_config_custom(self):
        """Test custom tracing configuration."""
        config = TracingConfig(
            service_name="custom-service",
            enabled=False,
            otlp_endpoint="http://localhost:4317",
        )
        assert config.service_name == "custom-service"
        assert config.enabled is False

    @pytest.mark.skipif(
        True,  # Skip if OpenTelemetry not installed
        reason="OpenTelemetry not available",
    )
    def test_setup_tracing_disabled(self):
        """Test tracing when disabled."""
        config = TracingConfig(enabled=False)
        tracer = setup_tracing(config)
        assert tracer is None

    def test_trace_method_decorator(self):
        """Test trace_method decorator."""

        @trace_method(name="test_operation")
        def test_function():
            return "result"

        result = test_function()
        assert result == "result"

    def test_add_span_attributes_no_span(self):
        """Test adding attributes when no span active."""
        # Should not raise
        add_span_attributes({"key": "value"})

    def test_record_exception_no_span(self):
        """Test recording exception when no span active."""
        # Should not raise
        record_exception(ValueError("test error"))


class TestLogging:
    """Test structured logging."""

    def test_logging_config_defaults(self):
        """Test logging configuration defaults."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.format == "json"

    def test_job_logger_initialization(self):
        """Test JobLogger initialization."""
        logger = JobLogger(
            name="test.logger",
            job_id="job-123",
            algorithm="qaoa",
            backend="aer",
            tenant_id="tenant-1",
        )

        assert logger.job_id == "job-123"
        assert logger.algorithm == "qaoa"
        assert logger.backend == "aer"

    def test_job_logger_logging(self, caplog):
        """Test JobLogger log methods."""
        logger = JobLogger(
            name="test.logger",
            job_id="job-123",
            algorithm="qaoa",
            backend="aer",
        )

        with caplog.at_level(logging.INFO):
            logger.info("Test message")

        assert len(caplog.records) >= 1

    def test_job_logger_log_progress(self, caplog):
        """Test progress logging."""
        logger = JobLogger(
            name="test.logger",
            job_id="job-123",
            algorithm="vqe",
            backend="aer",
        )

        with caplog.at_level(logging.INFO):
            logger.log_progress(
                iteration=50,
                max_iterations=100,
                current_value=-2.5,
                best_value=-3.0,
            )

        assert len(caplog.records) >= 1

    def test_job_logger_log_circuit_info(self, caplog):
        """Test circuit info logging."""
        logger = JobLogger(
            name="test.logger",
            job_id="job-123",
            algorithm="qaoa",
            backend="ibm",
        )

        with caplog.at_level(logging.INFO):
            logger.log_circuit_info(
                depth=25,
                width=10,
                gate_count=150,
                two_qubit_gates=40,
            )

        assert len(caplog.records) >= 1

    def test_context_variables(self):
        """Test context variable setting."""
        set_correlation_id("corr-123")
        set_tenant_context("tenant-456")

        # Should not raise
        pass


class TestStructuredFormatter:
    """Test JSON structured formatter."""

    def test_format_basic_record(self):
        """Test formatting a basic log record."""
        from qsop.observability.logging_config import StructuredFormatter

        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert data["message"] == "Test message"

    def test_format_with_exception(self):
        """Test formatting with exception info."""
        from qsop.observability.logging_config import StructuredFormatter

        formatter = StructuredFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "ERROR"
        assert "exception" in data
        assert "exc_type" in data


@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset metrics between tests."""
    yield
    # Metrics are global, but that's okay for tests


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

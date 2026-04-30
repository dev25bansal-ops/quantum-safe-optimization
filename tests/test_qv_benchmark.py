"""
Tests for Quantum Volume (QV) Benchmarking.
"""

import pytest

from api.quantum.qv_benchmark import (
    QuantumVolumeAssessment,
    QuantumVolumeResult,
    get_qv_assessment,
)


class TestQuantumVolumeAssessment:
    """Tests for Quantum Volume assessment functionality."""

    def test_assessment_initialization(self):
        """Test QV assessment can be initialized."""
        qv = QuantumVolumeAssessment()
        assert qv is not None
        assert qv._results == {}

    def test_get_assessment_singleton(self):
        """Test singleton getter returns consistent instance."""
        qv1 = get_qv_assessment()
        qv2 = get_qv_assessment()
        assert qv1 is qv2

    def test_measure_quantum_volume_basic(self):
        """Test basic QV measurement."""
        qv = QuantumVolumeAssessment()
        result = qv.measure_quantum_volume(
            backend_id="test_backend",
            max_qubits=4,
            trials_per_config=100,
        )

        assert result is not None
        assert result.backend_id == "test_backend"
        assert result.quantum_volume >= 1
        assert result.num_qubits_tested >= 2
        assert 0.0 <= result.success_rate <= 1.0
        assert result.trials > 0
        assert result.timestamp is not None

    def test_measure_quantum_volume_small_backend(self):
        """Test QV measurement for small backend."""
        qv = QuantumVolumeAssessment()
        result = qv.measure_quantum_volume(
            backend_id="small_backend",
            max_qubits=3,
            trials_per_config=50,
        )

        assert result.quantum_volume >= 1
        # Small backend should have limited QV
        assert result.quantum_volume <= 8  # Max 2^3

    def test_backend_history(self):
        """Test retrieving backend QV history."""
        qv = QuantumVolumeAssessment()
        qv.measure_quantum_volume("history_test", max_qubits=3, trials_per_config=20)
        qv.measure_quantum_volume("history_test", max_qubits=3, trials_per_config=20)

        history = qv.get_backend_history("history_test")

        assert history is not None
        assert history.backend_id == "history_test"
        assert len(history.measurements) == 2
        assert history.max_qv >= 1
        assert history.trend in ["improving", "declining", "stable", "new"]

    def test_backend_history_nonexistent(self):
        """Test retrieving history for nonexistent backend."""
        qv = QuantumVolumeAssessment()
        history = qv.get_backend_history("nonexistent_backend")
        assert history is None

    def test_compare_backends(self):
        """Test comparing QV across backends."""
        qv = QuantumVolumeAssessment()
        qv.measure_quantum_volume("backend_a", max_qubits=3, trials_per_config=20)
        qv.measure_quantum_volume("backend_b", max_qubits=4, trials_per_config=20)

        comparison = qv.compare_backends(["backend_a", "backend_b"])

        assert "backends" in comparison
        assert "ranking" in comparison
        assert len(comparison["ranking"]) == 2

    def test_estimate_capability(self):
        """Test capability estimation."""
        qv = QuantumVolumeAssessment()

        # Test with high QV
        capability = qv.estimate_capability(quantum_volume=64, problem_size=4)
        assert capability["can_handle"]
        assert capability["max_problem_size"] == 6  # log2(64)

        # Test with low QV
        capability = qv.estimate_capability(quantum_volume=4, problem_size=4)
        assert capability["max_problem_size"] == 2  # log2(4)

    def test_estimate_capability_edge_cases(self):
        """Test capability estimation edge cases."""
        qv = QuantumVolumeAssessment()

        # Zero QV
        capability = qv.estimate_capability(quantum_volume=0, problem_size=2)
        assert not capability["can_handle"]

        # QV equals problem size
        capability = qv.estimate_capability(quantum_volume=8, problem_size=3)
        assert capability["can_handle"]

    def test_get_all_results(self):
        """Test retrieving all QV results."""
        qv = QuantumVolumeAssessment()
        qv.measure_quantum_volume("result_test_1", max_qubits=2, trials_per_config=10)
        qv.measure_quantum_volume("result_test_2", max_qubits=2, trials_per_config=10)

        results = qv.get_all_results()

        assert isinstance(results, dict)
        assert len(results) >= 2


class TestQuantumVolumeResult:
    """Tests for Quantum Volume result dataclass."""

    def test_result_creation(self):
        """Test creating QV result."""
        result = QuantumVolumeResult(
            backend_id="test",
            quantum_volume=64,
            confidence_level=0.97,
            num_qubits_tested=6,
            depth=6,
            success_rate=0.75,
            trials=100,
            timestamp="2024-01-01T00:00:00Z",
        )

        assert result.backend_id == "test"
        assert result.quantum_volume == 64
        assert result.confidence_level == 0.97
        assert result.num_qubits_tested == 6
        assert result.success_rate == 0.75

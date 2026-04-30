"""
Tests for Quantum Error Correction (QEC) Simulator.
"""

import pytest

from api.quantum.qec_simulator import (
    QECSimulator,
    QECCodeType,
    QECParameters,
    get_qec_simulator,
)


class TestQECSimulator:
    """Tests for QEC simulator functionality."""

    def test_simulator_initialization(self):
        """Test QEC simulator can be initialized."""
        sim = QECSimulator()
        assert sim is not None
        assert sim._results == []

    def test_get_simulator_singleton(self):
        """Test singleton getter returns consistent instance."""
        sim1 = get_qec_simulator()
        sim2 = get_qec_simulator()
        assert sim1 is sim2

    def test_surface_code_simulation(self):
        """Test surface code simulation returns valid results."""
        sim = QECSimulator()
        result = sim.simulate_surface_code(
            distance=3,
            physical_error_rate=0.001,
            rounds=1000,
        )

        assert result is not None
        assert result.code_distance == 3
        assert result.num_physical_qubits == 9  # 3x3
        assert result.num_logical_qubits == 1
        assert 0.0 <= result.logical_error_rate <= 1.0
        assert result.threshold > 0
        assert result.overhead >= 1.0

    def test_surface_code_low_error_rate(self):
        """Test surface code with very low error rate."""
        sim = QECSimulator()
        result = sim.simulate_surface_code(
            distance=5,
            physical_error_rate=0.0001,
            rounds=1000,
        )

        # With low error rate, logical error rate should be very low
        assert result.logical_error_rate < 0.1

    def test_surface_code_high_error_rate(self):
        """Test surface code with high error rate."""
        sim = QECSimulator()
        result = sim.simulate_surface_code(
            distance=3,
            physical_error_rate=0.1,  # Above threshold
            rounds=1000,
        )

        # With high error rate, logical error rate should be higher
        assert result.logical_error_rate > 0.01

    def test_estimate_overhead(self):
        """Test resource overhead estimation."""
        sim = QECSimulator()
        overhead = sim.estimate_overhead(
            algorithm_qubits=10,
            target_error_rate=0.001,
            physical_error_rate=0.0001,
        )

        assert overhead["logical_qubits"] == 10
        assert overhead["code_distance"] >= 3
        assert overhead["physical_qubits_needed"] >= 10
        assert overhead["overhead_factor"] >= 1.0

    def test_get_threshold_curve(self):
        """Test threshold curve generation."""
        sim = QECSimulator()
        curve = sim.get_threshold_curve(
            code_type=QECCodeType.SURFACE,
            distances=[3, 5],
            error_rates=[0.001, 0.01],
        )

        assert "error_rates" in curve
        assert "distances" in curve
        assert len(curve["error_rates"]) == 2
        assert 3 in curve["distances"]
        assert 5 in curve["distances"]

    def test_get_results(self):
        """Test retrieving simulation results."""
        sim = QECSimulator()
        sim.simulate_surface_code(3, 0.001, 100)
        sim.simulate_surface_code(5, 0.001, 100)

        results = sim.get_results()
        assert len(results) == 2

    def test_count_physical_qubits(self):
        """Test physical qubit count for different codes."""
        sim = QECSimulator()

        assert sim._count_physical_qubits(QECCodeType.SURFACE, 3) == 9
        assert sim._count_physical_qubits(QECCodeType.SURFACE, 5) == 25
        assert sim._count_physical_qubits(QECCodeType.COLOR, 3) == 18
        assert sim._count_physical_qubits(QECCodeType.REPETITION, 5) == 5
        assert sim._count_physical_qubits(QECCodeType.STEANE, 7) == 7
        assert sim._count_physical_qubits(QECCodeType.SHOR, 9) == 9


class TestQECParameters:
    """Tests for QEC parameters dataclass."""

    def test_parameter_creation(self):
        """Test creating QEC parameters."""
        params = QECParameters(
            code_distance=3,
            code_type=QECCodeType.SURFACE,
            physical_error_rate=0.001,
        )

        assert params.code_distance == 3
        assert params.code_type == QECCodeType.SURFACE
        assert params.physical_error_rate == 0.001
        assert params.measurement_error_rate == 0.0
        assert params.rounds == 1000

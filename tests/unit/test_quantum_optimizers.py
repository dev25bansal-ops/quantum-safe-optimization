"""Tests for quantum optimization algorithms."""

import pytest
import numpy as np
from qsop.backends.simulators.statevector import StatevectorSimulator


class TestStatevectorSimulator:
    """Test the statevector simulator."""
    
    @pytest.fixture
    def simulator(self):
        """Create a simulator instance."""
        return StatevectorSimulator()
    
    def test_capabilities(self, simulator):
        """Test simulator capabilities."""
        caps = simulator.capabilities()
        
        assert caps["max_qubits"] > 0
        assert caps["supports_statevector"] is True
    
    def test_simple_circuit(self, simulator):
        """Test running a simple circuit."""
        # Internal format: (gate_name, qubits, params)
        circuit = [
            ("H", 0, []),
            ("MEASURE", 0, []),
        ]
        
        result = simulator.run(circuit, shots=1000)
        
        assert result["success"] is True
        assert "counts" in result
        
        # Should be roughly 50/50 distribution
        counts = result["counts"]
        assert len(counts) <= 2
    
    def test_bell_state(self, simulator):
        """Test creating a Bell state."""
        circuit = [
            ("H", 0, []),
            ("CNOT", [0, 1], []),
            ("MEASURE", 0, []),
            ("MEASURE", 1, []),
        ]
        
        result = simulator.run(circuit, shots=1000)
        
        counts = result["counts"]
        # Bell state should only give 00 or 11
        for bitstring in counts:
            assert bitstring in ["00", "11"]
    
    def test_parametric_gates(self, simulator):
        """Test parametric rotation gates."""
        theta = np.pi / 4
        
        circuit = [
            ("RY", 0, [theta]),
            ("RZ", 0, [theta]),
            ("MEASURE", 0, []),
        ]
        
        result = simulator.run(circuit, shots=1000)
        
        assert result["success"] is True
        assert len(result["counts"]) > 0
    
    def test_deterministic_seed(self, simulator):
        """Test that seeding gives reproducible results."""
        circuit = [
            ("H", 0, []),
            ("H", 1, []),
            ("MEASURE", 0, []),
            ("MEASURE", 1, []),
        ]
        
        result1 = simulator.run(circuit, shots=100, options={"seed": 42})
        result2 = simulator.run(circuit, shots=100, options={"seed": 42})
        
        assert result1["counts"] == result2["counts"]
    
    def test_multi_qubit(self, simulator):
        """Test multi-qubit circuit."""
        circuit = [
            ("H", 0, []),
            ("H", 1, []),
            ("H", 2, []),
            ("MEASURE", 0, []),
            ("MEASURE", 1, []),
            ("MEASURE", 2, []),
        ]
        
        result = simulator.run(circuit, shots=1000)
        
        # Should get roughly uniform distribution over 8 states
        assert len(result["counts"]) > 4


class TestQAOACircuitGeneration:
    """Test QAOA circuit generation."""
    
    def test_qaoa_imports(self):
        """Test that QAOA components can be imported."""
        from qsop.optimizers.quantum.qaoa import QAOAOptimizer
        from qsop.optimizers.hybrid.qaoa_hybrid import HybridQAOAOptimizer
        
        assert QAOAOptimizer is not None
        assert HybridQAOAOptimizer is not None
    
    def test_qaoa_config(self):
        """Test QAOA configuration."""
        from qsop.optimizers.hybrid.qaoa_hybrid import HybridQAOAConfig
        
        config = HybridQAOAConfig(
            p_layers=3,
            shots=2048,
            optimizer="COBYLA",
        )
        
        assert config.p_layers == 3
        assert config.shots == 2048


class TestVQECircuitGeneration:
    """Test VQE circuit generation."""
    
    def test_vqe_imports(self):
        """Test that VQE components can be imported."""
        from qsop.optimizers.quantum.vqe import VQEOptimizer
        from qsop.optimizers.hybrid.vqe_hybrid import (
            HybridVQEOptimizer,
            AnsatzType,
            GradientMethod,
        )
        
        assert VQEOptimizer is not None
        assert HybridVQEOptimizer is not None
    
    def test_ansatz_types(self):
        """Test ansatz type enumeration."""
        from qsop.optimizers.hybrid.vqe_hybrid import AnsatzType
        
        assert AnsatzType.RY.value == "ry"
        assert AnsatzType.HARDWARE_EFFICIENT.value == "hardware_efficient"
    
    def test_gradient_methods(self):
        """Test gradient method enumeration."""
        from qsop.optimizers.hybrid.vqe_hybrid import GradientMethod
        
        assert GradientMethod.PARAMETER_SHIFT.value == "parameter_shift"
        assert GradientMethod.SPSA.value == "spsa"


class TestGroverOptimizer:
    """Test Grover-based optimization."""
    
    def test_grover_imports(self):
        """Test that Grover components can be imported."""
        from qsop.optimizers.quantum.grover import GroverOptimizer
        
        assert GroverOptimizer is not None


class TestHybridWorkflows:
    """Test hybrid optimization workflows."""
    
    def test_hybrid_loop_config(self):
        """Test hybrid loop configuration."""
        from qsop.application.workflows.hybrid_loop import (
            HybridLoopConfig,
            LoopStatus,
        )
        
        config = HybridLoopConfig(
            max_iterations=50,
            convergence_threshold=1e-4,
        )
        
        assert config.max_iterations == 50
        assert config.convergence_threshold == 1e-4
    
    def test_loop_status(self):
        """Test loop status enumeration."""
        from qsop.application.workflows.hybrid_loop import LoopStatus
        
        assert LoopStatus.RUNNING.value == "running"
        assert LoopStatus.CONVERGED.value == "converged"

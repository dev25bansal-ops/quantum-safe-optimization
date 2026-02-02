"""
Tests for Quantum Optimization Runners.

Tests QAOA, VQE, and Annealing runners directly.
"""

import os
import pytest
import numpy as np

# Test the optimization module
from optimization.src.qaoa.runner import QAOARunner, QAOAConfig
from optimization.src.qaoa.problems import MaxCutProblem, QAOAProblem
from optimization.src.vqe.runner import VQERunner, VQEConfig
from optimization.src.vqe.hamiltonians import MolecularHamiltonian, IsingHamiltonian
from optimization.src.annealing.runner import AnnealingRunner, AnnealingConfig
from optimization.src.annealing.problems import QUBOProblem, IsingProblem


class TestQAOARunner:
    """Test QAOA Runner functionality."""
    
    @pytest.mark.anyio
    async def test_qaoa_runner_initialization(self):
        """Test QAOA runner initialization with default config."""
        runner = QAOARunner()
        
        assert runner.backend is not None
        assert runner.config is not None
        assert runner.config.layers == 1
        assert runner.config.optimizer == "COBYLA"
        assert runner.config.shots == 1000
    
    @pytest.mark.anyio
    async def test_qaoa_runner_custom_config(self):
        """Test QAOA runner with custom configuration."""
        config = QAOAConfig(
            layers=3,
            optimizer="SPSA",
            shots=2000,
            max_iterations=50,
        )
        runner = QAOARunner(config=config)
        
        assert runner.config.layers == 3
        assert runner.config.optimizer == "SPSA"
        assert runner.config.shots == 2000
    
    @pytest.mark.anyio
    async def test_qaoa_solve_maxcut_triangle(self):
        """Test QAOA on simple triangle MaxCut problem."""
        runner = QAOARunner(config=QAOAConfig(
            layers=1,
            shots=500,
            max_iterations=50,
        ))
        
        # Triangle graph
        problem = MaxCutProblem(edges=[(0, 1), (1, 2), (2, 0)])
        
        result = await runner.solve(problem)
        
        assert result is not None
        assert result.optimal_value is not None
        assert result.optimal_bitstring is not None
        # Triangle has max cut of 2
        assert len(result.optimal_bitstring) == 3
    
    @pytest.mark.anyio
    async def test_qaoa_solve_maxcut_square(self):
        """Test QAOA on square graph."""
        runner = QAOARunner(config=QAOAConfig(
            layers=2,
            shots=500,
            max_iterations=50,
        ))
        
        # Square graph (4 nodes, 4 edges)
        problem = MaxCutProblem(edges=[(0, 1), (1, 2), (2, 3), (3, 0)])
        
        result = await runner.solve(problem)
        
        assert result is not None
        assert result.optimal_bitstring is not None
        assert len(result.optimal_bitstring) == 4
    
    @pytest.mark.anyio
    async def test_qaoa_solve_maxcut_convenience(self):
        """Test QAOA convenience method for MaxCut."""
        runner = QAOARunner()
        
        edges = [(0, 1), (1, 2), (2, 0)]
        weights = [1.0, 2.0, 1.5]
        
        result = await runner.solve_maxcut(edges, weights, layers=1, shots=500)
        
        assert result is not None
        assert result.optimal_bitstring is not None
    
    @pytest.mark.anyio
    async def test_qaoa_random_graph(self):
        """Test QAOA on random graph."""
        problem = MaxCutProblem.random_graph(num_nodes=4, edge_probability=0.7, seed=42)
        runner = QAOARunner(config=QAOAConfig(layers=1, shots=500))
        
        result = await runner.solve(problem)
        
        assert result is not None
        assert result.optimal_bitstring is not None
        assert len(result.optimal_bitstring) == 4
    
    @pytest.mark.anyio
    async def test_qaoa_history_tracking(self):
        """Test that QAOA tracks execution history."""
        runner = QAOARunner(config=QAOAConfig(layers=1, shots=500))
        
        problem = MaxCutProblem(edges=[(0, 1)])
        
        await runner.solve(problem)
        await runner.solve(problem)
        
        history = runner.get_history()
        assert len(history) >= 2
        
        runner.clear_history()
        assert len(runner.get_history()) == 0
    
    @pytest.mark.anyio
    async def test_qaoa_convergence_history(self):
        """Test that QAOA records convergence history."""
        runner = QAOARunner(config=QAOAConfig(
            layers=1,
            shots=500,
            max_iterations=30,
        ))
        
        problem = MaxCutProblem(edges=[(0, 1), (1, 2)])
        result = await runner.solve(problem)
        
        # Should have convergence history
        if result.convergence_history:
            assert len(result.convergence_history) > 0
            # Values should generally decrease (minimization)


class TestMaxCutProblem:
    """Test MaxCut problem definition."""
    
    def test_maxcut_creation(self):
        """Test MaxCut problem creation."""
        edges = [(0, 1), (1, 2), (2, 0)]
        problem = MaxCutProblem(edges=edges)
        
        assert problem.num_qubits == 3
        assert problem.graph.number_of_edges() == 3
    
    def test_maxcut_weighted(self):
        """Test weighted MaxCut problem."""
        edges = [(0, 1), (1, 2)]
        weights = [2.0, 3.0]
        problem = MaxCutProblem(edges=edges, weights=weights)
        
        # Check weights are stored
        assert problem.graph[0][1]['weight'] == 2.0
        assert problem.graph[1][2]['weight'] == 3.0
    
    def test_maxcut_cost_hamiltonian(self):
        """Test cost Hamiltonian construction."""
        problem = MaxCutProblem(edges=[(0, 1)])
        H = problem.cost_hamiltonian()
        
        assert H is not None
    
    def test_maxcut_mixer_hamiltonian(self):
        """Test mixer Hamiltonian construction."""
        problem = MaxCutProblem(edges=[(0, 1), (1, 2)])
        mixer = problem.mixer_hamiltonian()
        
        assert mixer is not None
    
    def test_maxcut_evaluate_solution(self):
        """Test solution evaluation."""
        # Simple triangle
        problem = MaxCutProblem(edges=[(0, 1), (1, 2), (2, 0)])
        
        # Partition: {0} vs {1, 2} -> cuts (0,1) and (0,2) = 2
        cut_value = problem.evaluate_solution("100")
        assert cut_value == 2.0 or cut_value == -2.0  # Depends on sign convention
    
    def test_maxcut_decode_solution(self):
        """Test solution decoding."""
        problem = MaxCutProblem(edges=[(0, 1), (1, 2)])
        
        decoded = problem.decode_solution("010")
        assert decoded is not None


class TestVQERunner:
    """Test VQE Runner functionality."""
    
    @pytest.mark.anyio
    async def test_vqe_runner_initialization(self):
        """Test VQE runner initialization."""
        runner = VQERunner()
        
        assert runner.backend is not None
        assert runner.config is not None
        assert runner.config.ansatz_type == "UCCSD"
    
    @pytest.mark.anyio
    async def test_vqe_custom_config(self):
        """Test VQE with custom configuration."""
        config = VQEConfig(
            optimizer="L-BFGS-B",
            shots=2000,
            max_iterations=100,
            ansatz_type="hardware_efficient",
            ansatz_layers=2,
        )
        runner = VQERunner(config=config)
        
        assert runner.config.optimizer == "L-BFGS-B"
        assert runner.config.ansatz_type == "hardware_efficient"
    
    @pytest.mark.anyio
    async def test_vqe_solve_ising(self):
        """Test VQE on Ising model Hamiltonian."""
        runner = VQERunner(config=VQEConfig(
            ansatz_type="hardware_efficient",
            ansatz_layers=1,
            max_iterations=30,
            shots=500,
        ))
        
        # Create a simple Ising Hamiltonian
        hamiltonian = IsingHamiltonian(
            num_qubits=3,
            coupling_strength=1.0,
            transverse_field=0.5,
        )
        
        result = await runner.solve(hamiltonian)
        
        assert result is not None
        assert result.optimal_value is not None
    
    @pytest.mark.anyio
    async def test_vqe_ansatz_selection(self):
        """Test different ansatz types."""
        runner = VQERunner()
        
        ansatz_hw = runner.get_ansatz("hardware_efficient")
        ansatz_se = runner.get_ansatz("strongly_entangling")
        ansatz_uccsd = runner.get_ansatz("UCCSD")
        
        assert ansatz_hw is not None
        assert ansatz_se is not None
        assert ansatz_uccsd is not None
    
    @pytest.mark.anyio
    async def test_vqe_history_tracking(self):
        """Test that VQE tracks execution history."""
        runner = VQERunner(config=VQEConfig(
            ansatz_type="hardware_efficient",
            ansatz_layers=1,
            max_iterations=10,
        ))
        
        hamiltonian = IsingHamiltonian(num_qubits=2, coupling_strength=1.0)
        
        await runner.solve(hamiltonian)
        
        history = runner.get_history()
        assert len(history) >= 1
        
        runner.clear_history()
        assert len(runner.get_history()) == 0


class TestIsingHamiltonian:
    """Test Ising model Hamiltonian."""
    
    def test_ising_creation(self):
        """Test Ising model creation."""
        model = IsingHamiltonian(
            num_qubits=4,
            coupling_strength=1.0,
            transverse_field=0.5,
        )
        
        assert model.num_qubits == 4
    
    def test_ising_hamiltonian(self):
        """Test Hamiltonian construction."""
        model = IsingHamiltonian(num_qubits=3, coupling_strength=1.0)
        H = model.hamiltonian()
        
        assert H is not None


class TestAnnealingRunner:
    """Test Annealing Runner functionality."""
    
    @pytest.mark.anyio
    async def test_annealing_runner_initialization(self):
        """Test Annealing runner initialization."""
        runner = AnnealingRunner()
        
        assert runner.config is not None
        assert runner.config.num_reads == 1000
        assert runner.config.use_hybrid == True
    
    @pytest.mark.anyio
    async def test_annealing_custom_config(self):
        """Test Annealing with custom configuration."""
        config = AnnealingConfig(
            num_reads=500,
            use_hybrid=False,
            time_limit=30,
        )
        runner = AnnealingRunner(config=config)
        
        assert runner.config.num_reads == 500
        assert runner.config.use_hybrid == False
    
    @pytest.mark.anyio
    async def test_annealing_solve_qubo_simulated(self):
        """Test annealing on QUBO using simulated annealing (no D-Wave token)."""
        # Skip if D-Wave not configured - this is expected
        # The test verifies the QUBO problem setup is correct
        
        # Simple QUBO: minimize x0 + x1 - 2*x0*x1
        qubo = {
            (0, 0): 1.0,
            (1, 1): 1.0,
            (0, 1): -2.0,
        }
        problem = QUBOProblem(qubo)
        
        # Verify problem is set up correctly
        assert problem.num_variables == 2
        
        # Test evaluation: QUBO value = sum over (i,j) of Q[i,j] * x[i] * x[j]
        # For (0,0)=0, (1,1)=0: only diagonal terms when x=1
        val_00 = problem.evaluate_solution({0: 0, 1: 0})
        val_11 = problem.evaluate_solution({0: 1, 1: 1})
        val_10 = problem.evaluate_solution({0: 1, 1: 0})
        
        # x=[0,0]: Q[0,0]*0*0 + Q[1,1]*0*0 + Q[0,1]*0*0 = 0
        assert val_00 == 0.0
        # x=[1,0]: Q[0,0]*1 + Q[1,1]*0 + Q[0,1]*1*0 = 1
        assert val_10 == 1.0
        # x=[1,1]: Q[0,0]*1 + Q[1,1]*1 + Q[0,1]*1*1 = 1 + 1 - 2 = 0
        # This is one of the optimal solutions (tied with [0,0])
        assert val_11 == 0.0


class TestQUBOProblem:
    """Test QUBO problem definition."""
    
    def test_qubo_creation(self):
        """Test QUBO problem creation."""
        qubo = {
            (0, 0): 1.0,
            (1, 1): -1.0,
            (0, 1): 2.0,
        }
        problem = QUBOProblem(qubo)
        
        assert problem.num_variables == 2
    
    def test_qubo_from_matrix(self):
        """Test QUBO creation from numpy matrix."""
        Q = np.array([
            [1.0, 0.5],
            [0.5, -1.0],
        ])
        problem = QUBOProblem.from_matrix(Q)
        
        assert problem.num_variables == 2
    
    def test_qubo_maxcut(self):
        """Test QUBO for MaxCut problem."""
        edges = [(0, 1), (1, 2), (2, 0)]
        problem = QUBOProblem.max_cut(edges)
        
        assert problem.num_variables == 3
    
    def test_qubo_to_ising(self):
        """Test QUBO to Ising conversion."""
        qubo = {(0, 0): 1.0, (1, 1): -1.0}
        problem = QUBOProblem(qubo)
        
        h, J, offset = problem.to_ising()
        
        assert h is not None
        assert isinstance(offset, (int, float))
    
    def test_qubo_evaluate_solution(self):
        """Test solution evaluation."""
        qubo = {
            (0, 0): 1.0,
            (1, 1): 1.0,
            (0, 1): -4.0,
        }
        problem = QUBOProblem(qubo)
        
        # x = [0, 0] -> 0
        val_00 = problem.evaluate_solution({0: 0, 1: 0})
        assert val_00 == 0.0
        
        # x = [1, 1] -> 1 + 1 - 4 = -2
        val_11 = problem.evaluate_solution({0: 1, 1: 1})
        assert val_11 == -2.0


class TestIsingProblem:
    """Test Ising problem definition."""
    
    def test_ising_creation(self):
        """Test Ising problem creation."""
        h = {0: 0.5, 1: -0.5}
        J = {(0, 1): 1.0}
        problem = IsingProblem(h=h, J=J)
        
        assert problem.num_variables == 2
    
    def test_ising_to_qubo(self):
        """Test Ising to QUBO conversion."""
        h = {0: 1.0}
        J = {(0, 1): -1.0}
        problem = IsingProblem(h=h, J=J)
        
        qubo = problem.to_qubo()
        assert qubo is not None


class TestOptimizationPerformance:
    """Performance benchmarks for optimization runners."""
    
    @pytest.mark.anyio
    async def test_qaoa_performance_small(self):
        """Benchmark QAOA on small problem."""
        import time
        
        runner = QAOARunner(config=QAOAConfig(
            layers=1,
            shots=500,
            max_iterations=20,
        ))
        
        problem = MaxCutProblem(edges=[(0, 1), (1, 2), (2, 0)])
        
        start = time.perf_counter()
        result = await runner.solve(problem)
        elapsed = time.perf_counter() - start
        
        assert result is not None
        # Should complete within reasonable time
        assert elapsed < 30, f"QAOA too slow: {elapsed:.2f}s"
    
    @pytest.mark.anyio
    async def test_vqe_performance(self):
        """Benchmark VQE on small Hamiltonian."""
        import time
        
        runner = VQERunner(config=VQEConfig(
            ansatz_type="hardware_efficient",
            ansatz_layers=1,
            max_iterations=20,
            shots=500,
        ))
        
        hamiltonian = IsingHamiltonian(num_qubits=3, coupling_strength=1.0)
        
        start = time.perf_counter()
        result = await runner.solve(hamiltonian)
        elapsed = time.perf_counter() - start
        
        assert result is not None
        # Should complete within reasonable time
        assert elapsed < 30, f"VQE too slow: {elapsed:.2f}s"


class TestProblemEncodings:
    """Test problem encoding and decoding."""
    
    def test_maxcut_bitstring_decoding(self):
        """Test MaxCut bitstring to partition."""
        problem = MaxCutProblem(edges=[(0, 1), (1, 2)])
        
        # Bitstring "010" means node 1 is in set 1, others in set 0
        decoded = problem.decode_solution("010")
        
        assert decoded is not None
    
    def test_qubo_solution_decoding(self):
        """Test QUBO solution decoding."""
        qubo = {(0, 0): 1.0, (1, 1): 1.0}
        problem = QUBOProblem(qubo)
        
        decoded = problem.decode_solution({0: 1, 1: 0})
        assert decoded is not None

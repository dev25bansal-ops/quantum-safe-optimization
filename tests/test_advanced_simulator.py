"""
Tests for Advanced Local Simulator.

Tests the enhanced simulation features including:
- Multiple simulator types
- Noise models
- Error mitigation
- Advanced optimizers
"""

import os

import numpy as np
import pytest

# Disable rate limiting in test environment
os.environ["TESTING"] = "1"

from optimization.src.backends.advanced_simulator import (
    AdvancedLocalSimulator,
    AdvancedSimulatorConfig,
    GradientOptimizer,
    NoiseModel,
    OptimizerType,
    SimulatorType,
    create_advanced_simulator,
)
from optimization.src.backends.base import BackendConfig, BackendType, JobStatus


class TestAdvancedSimulatorConfig:
    """Test configuration options."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AdvancedSimulatorConfig()

        assert config.simulator_type == SimulatorType.STATEVECTOR
        assert config.noise_model == NoiseModel.IDEAL
        assert config.enable_readout_mitigation is False
        assert config.enable_zne is False
        assert config.max_parallel_circuits == 4

    def test_custom_config(self):
        """Test custom configuration."""
        config = AdvancedSimulatorConfig(
            simulator_type=SimulatorType.LIGHTNING,
            noise_model=NoiseModel.DEPOLARIZING,
            single_qubit_error_rate=0.005,
            enable_readout_mitigation=True,
            enable_zne=True,
        )

        assert config.simulator_type == SimulatorType.LIGHTNING
        assert config.noise_model == NoiseModel.DEPOLARIZING
        assert config.single_qubit_error_rate == 0.005
        assert config.enable_readout_mitigation is True


class TestGradientOptimizer:
    """Test custom gradient optimizers."""

    def test_adam_optimizer(self):
        """Test ADAM optimizer step."""
        opt = GradientOptimizer(
            OptimizerType.ADAM,
            learning_rate=0.1,
        )

        params = np.array([1.0, 2.0, 3.0])
        gradient = np.array([0.1, 0.2, 0.3])

        new_params = opt.step(params, gradient)

        # Parameters should change
        assert not np.allclose(new_params, params)
        # Should move in opposite direction of gradient
        assert np.all(new_params < params)

    def test_spsa_optimizer(self):
        """Test SPSA optimizer step."""
        opt = GradientOptimizer(
            OptimizerType.SPSA,
            learning_rate=0.1,
        )

        params = np.array([1.0, 2.0])
        gradient = np.array([0.5, 0.5])

        new_params = opt.step(params, gradient)

        assert not np.allclose(new_params, params)


class TestAdvancedSimulatorInitialization:
    """Test simulator initialization."""

    @pytest.mark.anyio
    async def test_basic_initialization(self):
        """Test basic initialization."""
        simulator = create_advanced_simulator()

        assert simulator is not None
        assert simulator.backend_type == BackendType.LOCAL_SIMULATOR
        assert not simulator.is_connected

    @pytest.mark.anyio
    async def test_connect_disconnect(self):
        """Test connection lifecycle."""
        simulator = create_advanced_simulator()

        await simulator.connect()
        assert simulator.is_connected

        await simulator.disconnect()
        assert not simulator.is_connected

    @pytest.mark.anyio
    async def test_get_available_devices(self):
        """Test device listing."""
        simulator = create_advanced_simulator()
        await simulator.connect()

        devices = await simulator.get_available_devices()

        assert len(devices) >= 4
        device_names = [d["name"] for d in devices]
        assert "statevector" in device_names
        assert "mps" in device_names
        assert "density_matrix" in device_names

        await simulator.disconnect()


class TestAdvancedVQE:
    """Test VQE with advanced features."""

    @pytest.mark.anyio
    async def test_vqe_cobyla(self):
        """Test VQE with COBYLA optimizer."""
        import pennylane as qml

        simulator = create_advanced_simulator()
        await simulator.connect()

        # Simple Hamiltonian
        H = qml.Hamiltonian([1.0], [qml.PauliZ(0)])

        def ansatz(params, wires):
            qml.RY(params[0], wires=0)

        result = await simulator.run_vqe(
            hamiltonian=H,
            ansatz=ansatz,
            optimizer="COBYLA",
            initial_params=np.array([0.5]),
            max_iterations=50,
        )

        assert result.status == JobStatus.COMPLETED
        assert result.optimal_value is not None
        # Ground state energy should be -1
        assert result.optimal_value < -0.9

        await simulator.disconnect()

    @pytest.mark.anyio
    async def test_vqe_adam(self):
        """Test VQE with ADAM optimizer."""
        import pennylane as qml

        simulator = create_advanced_simulator()
        await simulator.connect()

        H = qml.Hamiltonian([1.0], [qml.PauliZ(0)])

        def ansatz(params, wires):
            qml.RY(params[0], wires=0)

        result = await simulator.run_vqe(
            hamiltonian=H,
            ansatz=ansatz,
            optimizer="ADAM",
            initial_params=np.array([0.5]),
            max_iterations=100,
        )

        assert result.status == JobStatus.COMPLETED
        assert result.optimal_value < -0.5  # Should converge toward -1

        await simulator.disconnect()

    @pytest.mark.anyio
    async def test_vqe_convergence_history(self):
        """Test that convergence history is tracked."""
        import pennylane as qml

        simulator = create_advanced_simulator()
        await simulator.connect()

        H = qml.Hamiltonian([1.0], [qml.PauliZ(0)])

        def ansatz(params, wires):
            qml.RY(params[0], wires=0)

        result = await simulator.run_vqe(
            hamiltonian=H,
            ansatz=ansatz,
            optimizer="COBYLA",
            max_iterations=20,
        )

        assert result.convergence_history is not None
        assert len(result.convergence_history) > 0

        await simulator.disconnect()


class TestAdvancedQAOA:
    """Test QAOA with advanced features."""

    @pytest.mark.anyio
    async def test_qaoa_maxcut_basic(self):
        """Test QAOA on simple MaxCut problem."""
        import pennylane as qml

        simulator = create_advanced_simulator()
        await simulator.connect()

        # Simple triangle graph
        cost_h = qml.Hamiltonian(
            [-0.5, -0.5, -0.5],
            [
                qml.PauliZ(0) @ qml.PauliZ(1),
                qml.PauliZ(1) @ qml.PauliZ(2),
                qml.PauliZ(0) @ qml.PauliZ(2),
            ],
        )

        result = await simulator.run_qaoa(
            cost_hamiltonian=cost_h,
            mixer_hamiltonian=None,
            layers=1,
            optimizer="COBYLA",
            shots=500,
        )

        assert result.status == JobStatus.COMPLETED
        assert result.optimal_value is not None
        assert result.optimal_bitstring is not None
        assert result.counts is not None
        assert len(result.optimal_bitstring) == 3

        await simulator.disconnect()

    @pytest.mark.anyio
    async def test_qaoa_interp_initialization(self):
        """Test INTERP parameter initialization."""
        simulator = create_advanced_simulator()

        # Test initialization for different layers
        params_1 = simulator._interp_initialization(1)
        assert len(params_1) == 2  # 1 gamma + 1 beta

        params_3 = simulator._interp_initialization(3)
        assert len(params_3) == 6  # 3 gammas + 3 betas

    @pytest.mark.anyio
    async def test_qaoa_warm_start(self):
        """Test QAOA with warm start."""
        import pennylane as qml

        simulator = create_advanced_simulator()
        await simulator.connect()

        # Set warm start state
        simulator.set_warm_start("101")

        cost_h = qml.Hamiltonian(
            [-0.5, -0.5],
            [
                qml.PauliZ(0) @ qml.PauliZ(1),
                qml.PauliZ(1) @ qml.PauliZ(2),
            ],
        )

        result = await simulator.run_qaoa(
            cost_hamiltonian=cost_h,
            mixer_hamiltonian=None,
            layers=1,
            warm_start=True,
            shots=500,
        )

        assert result.status == JobStatus.COMPLETED

        await simulator.disconnect()


class TestAdvancedAnnealing:
    """Test annealing with advanced features."""

    @pytest.mark.anyio
    async def test_annealing_simple_qubo(self):
        """Test annealing on simple QUBO."""
        simulator = create_advanced_simulator()
        await simulator.connect()

        # Simple QUBO: minimize -x1 - x2 + 2*x1*x2
        qubo = np.array([[-1, 1], [1, -1]])

        result = await simulator.run_annealing(
            qubo_matrix=qubo,
            num_reads=100,
            annealing_time=10.0,
        )

        assert result.status == JobStatus.COMPLETED
        assert result.optimal_bitstring is not None
        assert result.optimal_value is not None
        assert result.counts is not None

        await simulator.disconnect()

    @pytest.mark.anyio
    async def test_annealing_custom_schedule(self):
        """Test annealing with custom schedule."""
        simulator = create_advanced_simulator()
        await simulator.connect()

        qubo = np.array([[-1, 0.5], [0.5, -1]])

        # Custom exponential schedule
        num_steps = 500
        schedule = [(i / num_steps, 0.1 * np.exp(i / num_steps * 3)) for i in range(num_steps + 1)]

        result = await simulator.run_annealing(
            qubo_matrix=qubo,
            num_reads=50,
            schedule=schedule,
        )

        assert result.status == JobStatus.COMPLETED

        await simulator.disconnect()


class TestErrorMitigation:
    """Test error mitigation features."""

    @pytest.mark.anyio
    async def test_readout_mitigation_setup(self):
        """Test that readout mitigation is set up correctly."""
        config = AdvancedSimulatorConfig(
            enable_readout_mitigation=True,
            readout_error_rate=0.02,
        )
        backend_config = BackendConfig(backend_type=BackendType.LOCAL_SIMULATOR)
        simulator = AdvancedLocalSimulator(backend_config, config)

        await simulator.connect()

        # Calibration matrix should be built
        assert simulator._calibration_matrix is not None

        await simulator.disconnect()

    def test_readout_mitigation_counts(self):
        """Test readout error mitigation on counts."""
        config = AdvancedSimulatorConfig(
            enable_readout_mitigation=True,
            readout_error_rate=0.1,
        )
        backend_config = BackendConfig(backend_type=BackendType.LOCAL_SIMULATOR)
        simulator = AdvancedLocalSimulator(backend_config, config)

        # Build calibration matrix manually for test
        err = 0.1
        simulator._calibration_matrix = np.array([[1 - err, err], [err, 1 - err]])

        # Test counts with errors
        counts = {"00": 80, "01": 10, "10": 10, "11": 0}
        mitigated = simulator._mitigate_readout(counts, 2)

        # Should have non-negative counts
        assert all(v >= 0 for v in mitigated.values())


class TestFactoryFunction:
    """Test the factory function."""

    def test_create_statevector(self):
        """Test creating statevector simulator."""
        sim = create_advanced_simulator(simulator_type="statevector")
        assert sim.advanced_config.simulator_type == SimulatorType.STATEVECTOR

    def test_create_lightning(self):
        """Test creating lightning simulator."""
        sim = create_advanced_simulator(simulator_type="lightning")
        assert sim.advanced_config.simulator_type == SimulatorType.LIGHTNING

    def test_create_with_noise(self):
        """Test creating noisy simulator."""
        sim = create_advanced_simulator(
            simulator_type="density_matrix",
            noise_model="depolarizing",
        )
        assert sim.advanced_config.simulator_type == SimulatorType.DENSITY_MATRIX
        assert sim.advanced_config.noise_model == NoiseModel.DEPOLARIZING

    def test_create_with_error_mitigation(self):
        """Test creating simulator with error mitigation."""
        sim = create_advanced_simulator(enable_error_mitigation=True)
        assert sim.advanced_config.enable_readout_mitigation is True
        assert sim.advanced_config.enable_zne is True


class TestSimulatorPerformance:
    """Test simulator performance characteristics."""

    @pytest.mark.anyio
    async def test_parallel_execution(self):
        """Test that parallel circuits can be configured."""
        config = AdvancedSimulatorConfig(max_parallel_circuits=8)
        backend_config = BackendConfig(backend_type=BackendType.LOCAL_SIMULATOR)
        simulator = AdvancedLocalSimulator(backend_config, config)

        assert simulator.advanced_config.max_parallel_circuits == 8

    @pytest.mark.anyio
    async def test_caching_enabled(self):
        """Test that caching is enabled by default."""
        simulator = create_advanced_simulator()
        assert simulator.advanced_config.use_caching is True


class TestOptimizerTypes:
    """Test all optimizer types work."""

    @pytest.mark.anyio
    async def test_scipy_optimizers(self):
        """Test various scipy optimizers."""
        import pennylane as qml

        simulator = create_advanced_simulator()
        await simulator.connect()

        H = qml.Hamiltonian([1.0], [qml.PauliZ(0)])

        def ansatz(params, wires):
            qml.RY(params[0], wires=0)

        # Test BFGS
        result = await simulator.run_vqe(
            hamiltonian=H,
            ansatz=ansatz,
            optimizer="BFGS",
            initial_params=np.array([0.5]),
            max_iterations=30,
        )
        assert result.status == JobStatus.COMPLETED

        # Test Nelder-Mead
        result = await simulator.run_vqe(
            hamiltonian=H,
            ansatz=ansatz,
            optimizer="Nelder-Mead",
            initial_params=np.array([0.5]),
            max_iterations=30,
        )
        assert result.status == JobStatus.COMPLETED

        await simulator.disconnect()

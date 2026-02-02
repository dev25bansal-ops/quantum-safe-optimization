# Quantum Optimization Module

Post-quantum secure optimization algorithms supporting QAOA, VQE, and Quantum Annealing.

## Features

- **QAOA** - Quantum Approximate Optimization Algorithm for combinatorial problems
- **VQE** - Variational Quantum Eigensolver for molecular simulation
- **Annealing** - Quantum annealing for QUBO/Ising problems
- **Advanced Local Simulator** - High-performance simulation with noise modeling

## Backends

- IBM Quantum
- AWS Braket
- Azure Quantum
- D-Wave
- Local Simulator (PennyLane)
- **Advanced Local Simulator** (NEW) - Enhanced simulation features

## Advanced Local Simulator

The new `AdvancedLocalSimulator` provides enhanced simulation capabilities:

### Simulator Types
- `statevector` - Full state vector simulation (default, up to 24 qubits)
- `mps` - Matrix Product State for larger systems (up to 100 qubits)
- `density_matrix` - Full noise modeling support (up to 12 qubits)
- `lightning` - High-performance C++ backend (up to 28 qubits)
- `gpu` - CUDA-accelerated simulation (if available)

### Noise Models
- `ideal` - Perfect quantum operations
- `depolarizing` - Depolarizing channel noise
- `amplitude_damping` - T1 relaxation noise
- `phase_damping` - T2 dephasing noise
- `thermal` - Thermal relaxation noise
- `realistic_superconducting` - Realistic superconducting qubit noise
- `realistic_ion_trap` - Realistic ion trap noise

### Optimizers
- **SciPy optimizers**: COBYLA, BFGS, L-BFGS-B, Powell, Nelder-Mead, SLSQP
- **Gradient-based**: ADAM with momentum, SPSA
- **Global optimizers**: Differential Evolution, Dual Annealing
- **Quantum-native**: Rotosolve for rotational gates

### Error Mitigation
- Readout error mitigation via calibration matrix inversion
- Zero-Noise Extrapolation (ZNE) with configurable scale factors

### Usage

```python
from optimization.src.backends import (
    create_advanced_simulator,
    AdvancedSimulatorConfig,
    SimulatorType,
    NoiseModel,
)

# Quick creation with factory function
simulator = create_advanced_simulator(
    simulator_type="statevector",
    noise_model="ideal",
    enable_error_mitigation=True,
)

# Or with full configuration
config = AdvancedSimulatorConfig(
    simulator_type=SimulatorType.LIGHTNING,
    noise_model=NoiseModel.DEPOLARIZING,
    single_qubit_error_rate=0.001,
    two_qubit_error_rate=0.01,
    enable_readout_mitigation=True,
    enable_zne=True,
    zne_scale_factors=[1.0, 2.0, 3.0],
    max_parallel_circuits=8,
)

# Run VQE with ADAM optimizer
result = await simulator.run_vqe(
    hamiltonian=H,
    ansatz=my_ansatz,
    optimizer="ADAM",
    max_iterations=100,
)

# Run QAOA with warm start
simulator.set_warm_start("101010")
result = await simulator.run_qaoa(
    cost_hamiltonian=cost_h,
    mixer_hamiltonian=None,
    layers=3,
    warm_start=True,
)

# Run annealing with custom schedule
schedule = [(t/1000, 0.1 * exp(t/1000 * 3)) for t in range(1001)]
result = await simulator.run_annealing(
    qubo_matrix=qubo,
    num_reads=1000,
    schedule=schedule,
)
```

### INTERP Parameter Initialization

For QAOA, the simulator uses INTERP initialization strategy which interpolates
optimal parameters from lower circuit depths, significantly improving convergence.

### Gradient Computation

Supports multiple gradient methods:
- `parameter-shift` - Exact gradients using parameter shift rule
- `adjoint` - Memory-efficient adjoint differentiation
- `finite-diff` - Numerical finite differences (fallback)

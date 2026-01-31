import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

import pytest
import numpy as np
from qsop.optimizers.hybrid.qaoa_hybrid import HybridQAOAOptimizer, HybridQAOAConfig
from qsop.domain.models.problem import OptimizationProblem, Variable, VariableType
from qsop.backends.simulators.statevector import StatevectorSimulator

def test_adaptive_shots_logic():
    """Verify that shot counts are dynamically adjusted during optimization."""
    # Simple problem setup
    variables = [
        Variable(name="x0", var_type=VariableType.BINARY, lower_bound=0, upper_bound=1),
        Variable(name="x1", var_type=VariableType.BINARY, lower_bound=0, upper_bound=1),
    ]
    
    # dummy objective
    def objective(x):
        return float(x["x0"] + x["x1"])

    problem = OptimizationProblem(
        variables=variables,
        objective=objective,
        metadata={"type": "maxcut"}
    )
    
    # Setup adaptive config
    min_shots = 100
    max_shots = 1000
    max_iterations = 5
    
    config = HybridQAOAConfig(
        adaptive_shots=True,
        min_shots=min_shots,
        max_shots=max_shots,
        max_iterations=max_iterations,
        optimizer="COBYLA"
    )
    
    backend = StatevectorSimulator()
    optimizer = HybridQAOAOptimizer(config=config, backend=backend)
    
    result = optimizer.optimize(problem)
    
    # Verify total shots used is recorded
    total_shots = result.metadata["total_shots"]
    assert total_shots > 0
    
    # In COBYLA, nit might not be present, so we use result.iterations
    iterations = result.iterations
    
    # Check that average shots per iteration reflects adaptation
    # Minimum total shots if it stayed at min_shots: min_shots * iterations
    # Maximum total shots if it stayed at max_shots: max_shots * iterations
    assert total_shots >= min_shots * iterations
    assert total_shots <= max_shots * iterations
    
    # Check that some iterations used more than min_shots if we progressed
    if iterations > 1:
        # Since we record each iteration's shots in history would be better,
        # but for now we'll just check if total_shots > min_shots * iterations
        # (it should be since shots increase linearly with iterations)
        assert total_shots > min_shots * iterations

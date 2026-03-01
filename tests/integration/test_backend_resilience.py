from dataclasses import dataclass

import pytest

from qsop.backends.pool import BackendPool
from qsop.backends.providers.mock_aws_azure import AWSBraketMock, AzureQuantumMock
from qsop.backends.router import (
    BackendRouter,
    DepthAwareStrategy,
    FailoverRouter,
)
from qsop.backends.simulators.statevector import StatevectorSimulator


@dataclass
class MockCircuit:
    num_qubits: int
    _depth: int

    def depth(self) -> int:
        return self._depth


def test_backend_pool_filtering():
    pool = BackendPool()
    aws = AWSBraketMock(num_qubits=80)
    azure = AzureQuantumMock(num_qubits=40)
    sim = StatevectorSimulator()

    pool.register(aws)
    pool.register(azure)
    pool.register(sim)

    # Test qubit filtering
    large_backends = pool.list_backends(min_qubits=50)
    assert len(large_backends) == 1
    assert large_backends[0].name == aws.name

    # Test simulator filtering
    sims = pool.list_backends(simulator=True)
    assert len(sims) == 1
    assert sims[0].name == sim.name

    # Test capability criteria
    matches = pool.get_backends_by_capability(num_qubits=40, simulator=False)
    assert len(matches) == 1
    assert matches[0].name == azure.name


def test_depth_aware_routing():
    pool = BackendPool()
    # AWS has 5 pending jobs, Azure has 10 (from mocks)
    aws = AWSBraketMock()
    azure = AzureQuantumMock()
    sim = StatevectorSimulator()  # Simulator is usually local and least busy in mock

    pool.register(aws)
    pool.register(azure)
    pool.register(sim)

    router = BackendRouter(pool, default_strategy=DepthAwareStrategy())

    # 1. Shallow circuit should pick least busy hardware (AWS)
    shallow_circuit = MockCircuit(num_qubits=20, _depth=10)
    selected = router.route(shallow_circuit)
    assert selected.name == aws.name

    # 2. Deep circuit should prefer simulator
    deep_circuit = MockCircuit(num_qubits=20, _depth=100)
    selected = router.route(deep_circuit)
    assert selected.capabilities.simulator is True


def test_failover_routing():
    pool = BackendPool()
    # Create a backend that is offline
    AWSBraketMock(name="offline_aws")
    # We'll manually set it offline for this test
    # Note: BackendCapabilities is frozen, so we'd need to re-init or mock

    # Instead, let's just register a "bad" one and see if we can failover
    # if the strategy returns None (e.g. no hardware matches)
    sim = StatevectorSimulator()
    pool.register(sim)

    # DepthAwareStrategy will fail if we ask for 100 qubits and only have 20-30
    router = FailoverRouter(pool, default_strategy=DepthAwareStrategy())

    huge_circuit = MockCircuit(num_qubits=100, _depth=10)

    # Standard route should fail
    with pytest.raises(RuntimeError, match="No online quantum backends available"):
        router.route(huge_circuit)

    # route_with_failover should fallback to least busy (the simulator)
    selected = router.route_with_failover(huge_circuit)
    assert selected.name == sim.name

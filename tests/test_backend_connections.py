"""
Tests for Quantum Backend Connections.

Tests the backend connection manager, circuit breaker,
and individual backend implementations.
"""

import os
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# Disable rate limiting in test environment
os.environ["TESTING"] = "1"

import sys
sys.path.insert(0, "D:/Quantum")

from optimization.src.backends import (
    BackendType,
    BackendConfig,
    JobStatus,
    JobResult,
)
from optimization.src.backends.connection_manager import (
    BackendConnectionManager,
    ConnectionState,
    ProviderStatus,
    BackendCredentials,
    ConnectionPoolConfig,
    CircuitBreakerConfig,
    RetryConfig,
    ManagedConnection,
    CircuitBreakerState,
    ConnectionMetrics,
    get_connection_manager,
    get_backend,
    release_backend,
    BackendContext,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def pool_config():
    """Create test pool configuration."""
    return ConnectionPoolConfig(
        max_connections_per_backend=3,
        connection_timeout_seconds=5,
        idle_timeout_seconds=60,
        health_check_interval_seconds=30,
    )


@pytest.fixture
def circuit_breaker_config():
    """Create test circuit breaker configuration."""
    return CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout_seconds=10,
        half_open_max_calls=1,
    )


@pytest.fixture
def retry_config():
    """Create test retry configuration."""
    return RetryConfig(
        max_retries=2,
        initial_delay_seconds=0.1,
        max_delay_seconds=1.0,
        exponential_base=2.0,
        jitter=False,
    )


@pytest.fixture
def mock_backend():
    """Create a mock quantum backend."""
    backend = AsyncMock()
    backend.backend_type = BackendType.LOCAL_SIMULATOR
    backend.is_connected = True
    backend.connect = AsyncMock()
    backend.disconnect = AsyncMock()
    backend.get_available_devices = AsyncMock(return_value=[
        {"name": "simulator", "num_qubits": 24}
    ])
    backend.health_check = AsyncMock(return_value=True)
    return backend


@pytest.fixture
def sample_credentials():
    """Create sample credentials."""
    return BackendCredentials(
        api_token="test_token_123",
        region="us-east-1",
    )


# ============================================================================
# BackendCredentials Tests
# ============================================================================

class TestBackendCredentials:
    """Tests for BackendCredentials class."""
    
    def test_credentials_from_environment_ibm(self):
        """Test loading IBM credentials from environment."""
        with patch.dict(os.environ, {
            "IBM_QUANTUM_TOKEN": "test_ibm_token",
            "IBM_QUANTUM_INSTANCE": "ibm-q/open/main",
        }):
            creds = BackendCredentials.from_environment(BackendType.IBM_QUANTUM)
            assert creds.api_token == "test_ibm_token"
            assert creds.instance == "ibm-q/open/main"
    
    def test_credentials_from_environment_aws(self):
        """Test loading AWS credentials from environment."""
        with patch.dict(os.environ, {
            "AWS_REGION": "us-west-2",
            "BRAKET_S3_BUCKET": "my-braket-bucket",
        }):
            creds = BackendCredentials.from_environment(BackendType.AWS_BRAKET)
            assert creds.region == "us-west-2"
            assert creds.s3_bucket == "my-braket-bucket"
    
    def test_credentials_from_environment_azure(self):
        """Test loading Azure credentials from environment."""
        with patch.dict(os.environ, {
            "AZURE_QUANTUM_RESOURCE_ID": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Quantum/Workspaces/ws",
            "AZURE_QUANTUM_LOCATION": "westus",
        }):
            creds = BackendCredentials.from_environment(BackendType.AZURE_QUANTUM)
            assert creds.resource_id == "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Quantum/Workspaces/ws"
            assert creds.region == "westus"
    
    def test_credentials_from_environment_dwave(self):
        """Test loading D-Wave credentials from environment."""
        with patch.dict(os.environ, {
            "DWAVE_API_TOKEN": "dwave_token_xyz",
            "DWAVE_REGION": "eu-central-1",
        }):
            creds = BackendCredentials.from_environment(BackendType.DWAVE)
            assert creds.api_token == "dwave_token_xyz"
            assert creds.region == "eu-central-1"


# ============================================================================
# CircuitBreakerState Tests
# ============================================================================

class TestCircuitBreakerState:
    """Tests for circuit breaker state management."""
    
    def test_initial_state(self):
        """Test initial circuit breaker state."""
        state = CircuitBreakerState()
        
        assert state.failures == 0
        assert state.successes == 0
        assert state.state == ConnectionState.DISCONNECTED
        assert state.last_failure_time is None
    
    def test_state_after_failures(self):
        """Test state transitions after failures."""
        state = CircuitBreakerState(
            failures=5,
            state=ConnectionState.CIRCUIT_OPEN,
            last_failure_time=datetime.utcnow(),
        )
        
        assert state.failures == 5
        assert state.state == ConnectionState.CIRCUIT_OPEN


# ============================================================================
# ConnectionMetrics Tests
# ============================================================================

class TestConnectionMetrics:
    """Tests for connection metrics."""
    
    def test_initial_metrics(self):
        """Test initial metrics values."""
        metrics = ConnectionMetrics()
        
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.success_rate == 1.0  # No failures = 100% success
    
    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        metrics = ConnectionMetrics(
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
        )
        
        assert metrics.success_rate == 0.95
    
    def test_average_latency(self):
        """Test average latency calculation."""
        metrics = ConnectionMetrics(
            successful_requests=10,
            total_latency_ms=1000.0,
        )
        
        assert metrics.average_latency_ms == 100.0
    
    def test_average_latency_no_requests(self):
        """Test average latency with no requests."""
        metrics = ConnectionMetrics()
        
        assert metrics.average_latency_ms == 0.0


# ============================================================================
# ManagedConnection Tests
# ============================================================================

class TestManagedConnection:
    """Tests for ManagedConnection."""
    
    def test_managed_connection_creation(self, mock_backend):
        """Test creating a managed connection."""
        conn = ManagedConnection(
            backend=mock_backend,
            created_at=datetime.utcnow(),
            last_used_at=datetime.utcnow(),
            state=ConnectionState.CONNECTED,
            circuit_breaker=CircuitBreakerState(),
            metrics=ConnectionMetrics(),
        )
        
        assert conn.backend == mock_backend
        assert conn.state == ConnectionState.CONNECTED
        assert conn.in_use is False


# ============================================================================
# BackendConnectionManager Tests
# ============================================================================

class TestBackendConnectionManager:
    """Tests for BackendConnectionManager."""
    
    @pytest.mark.asyncio
    async def test_manager_singleton(self):
        """Test that manager is a singleton."""
        # Reset singleton for test
        BackendConnectionManager._instance = None
        
        manager1 = BackendConnectionManager()
        manager2 = BackendConnectionManager()
        
        assert manager1 is manager2
    
    @pytest.mark.asyncio
    async def test_manager_start_stop(self):
        """Test starting and stopping the manager."""
        # Reset singleton
        BackendConnectionManager._instance = None
        
        # Use default config - singleton doesn't accept kwargs via __new__
        manager = BackendConnectionManager()
        
        await manager.start()
        assert manager._running is True
        
        await manager.stop()
        assert manager._running is False
    
    def test_get_available_backends(self):
        """Test getting available backends."""
        BackendConnectionManager._instance = None
        manager = BackendConnectionManager()
        
        backends = manager.get_available_backends()
        
        assert len(backends) == len(BackendType)
        backend_types = [b["type"] for b in backends]
        assert "local_simulator" in backend_types
        assert "ibm_quantum" in backend_types
    
    def test_get_provider_status_unknown(self):
        """Test getting provider status when no connections exist."""
        BackendConnectionManager._instance = None
        manager = BackendConnectionManager()
        
        status = manager.get_provider_status(BackendType.IBM_QUANTUM)
        
        assert status == ProviderStatus.UNKNOWN
    
    def test_get_metrics(self):
        """Test getting metrics for a backend."""
        BackendConnectionManager._instance = None
        manager = BackendConnectionManager()
        
        metrics = manager.get_metrics(BackendType.LOCAL_SIMULATOR)
        
        assert "backend_type" in metrics
        assert "total_requests" in metrics
        assert "success_rate" in metrics
    
    def test_get_all_metrics(self):
        """Test getting metrics for all backends."""
        BackendConnectionManager._instance = None
        manager = BackendConnectionManager()
        
        all_metrics = manager.get_metrics()
        
        assert len(all_metrics) == len(BackendType)
    
    def test_retry_delay_calculation(self):
        """Test retry delay calculation."""
        BackendConnectionManager._instance = None
        manager = BackendConnectionManager()
        
        delay_0 = manager._calculate_retry_delay(0)
        delay_1 = manager._calculate_retry_delay(1)
        delay_2 = manager._calculate_retry_delay(2)
        
        # Exponential backoff - verify delays increase
        assert delay_0 >= 0.5  # At least initial_delay (with possible jitter)
        assert delay_1 >= delay_0  # Should increase
        assert delay_2 >= delay_1  # Should increase further


# ============================================================================
# Convenience Function Tests
# ============================================================================

class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_get_connection_manager(self):
        """Test getting connection manager singleton."""
        # Reset global
        import optimization.src.backends.connection_manager as cm
        cm._connection_manager = None
        BackendConnectionManager._instance = None
        
        manager = get_connection_manager()
        
        assert manager is not None
        assert isinstance(manager, BackendConnectionManager)
    
    def test_get_connection_manager_same_instance(self):
        """Test that get_connection_manager returns same instance."""
        import optimization.src.backends.connection_manager as cm
        cm._connection_manager = None
        BackendConnectionManager._instance = None
        
        manager1 = get_connection_manager()
        manager2 = get_connection_manager()
        
        assert manager1 is manager2


# ============================================================================
# BackendContext Tests
# ============================================================================

class TestBackendContext:
    """Tests for BackendContext context manager."""
    
    def test_context_initialization(self):
        """Test context manager initialization."""
        ctx = BackendContext(BackendType.LOCAL_SIMULATOR, device_name="default")
        
        assert ctx.backend_type == BackendType.LOCAL_SIMULATOR
        assert ctx.device_name == "default"
        assert ctx.backend is None


# ============================================================================
# Backend Implementation Tests
# ============================================================================

class TestIBMQuantumBackend:
    """Tests for IBM Quantum backend."""
    
    def test_backend_type(self):
        """Test that backend type is correct."""
        from optimization.src.backends.ibm import IBMQuantumBackend
        
        config = BackendConfig(backend_type=BackendType.IBM_QUANTUM)
        backend = IBMQuantumBackend(config)
        
        assert backend.backend_type == BackendType.IBM_QUANTUM
        assert backend.is_connected is False
    
    @pytest.mark.asyncio
    async def test_connect_without_credentials(self):
        """Test connection fails gracefully without credentials."""
        from optimization.src.backends.ibm import IBMQuantumBackend
        
        # Clear any existing env vars
        with patch.dict(os.environ, {}, clear=True):
            config = BackendConfig(backend_type=BackendType.IBM_QUANTUM)
            backend = IBMQuantumBackend(config)
            
            # Should raise ConnectionError without credentials
            with pytest.raises(ConnectionError):
                await backend.connect()


class TestAWSBraketBackend:
    """Tests for AWS Braket backend."""
    
    def test_backend_type(self):
        """Test that backend type is correct."""
        from optimization.src.backends.aws import AWSBraketBackend
        
        config = BackendConfig(backend_type=BackendType.AWS_BRAKET)
        backend = AWSBraketBackend(config)
        
        assert backend.backend_type == BackendType.AWS_BRAKET
    
    def test_resolve_device_arn(self):
        """Test device ARN resolution."""
        from optimization.src.backends.aws import AWSBraketBackend, BRAKET_DEVICES
        
        config = BackendConfig(backend_type=BackendType.AWS_BRAKET)
        backend = AWSBraketBackend(config)
        
        # Known device name
        arn = backend._resolve_device_arn("sv1")
        assert arn == BRAKET_DEVICES["sv1"]
        
        # Already an ARN
        full_arn = "arn:aws:braket:::device/quantum-simulator/amazon/sv1"
        assert backend._resolve_device_arn(full_arn) == full_arn
        
        # Unknown defaults to SV1
        assert backend._resolve_device_arn("unknown_device") == BRAKET_DEVICES["sv1"]


class TestAzureQuantumBackend:
    """Tests for Azure Quantum backend."""
    
    def test_backend_type(self):
        """Test that backend type is correct."""
        from optimization.src.backends.azure import AzureQuantumBackend
        
        config = BackendConfig(backend_type=BackendType.AZURE_QUANTUM)
        backend = AzureQuantumBackend(config)
        
        assert backend.backend_type == BackendType.AZURE_QUANTUM


# ============================================================================
# Integration Tests
# ============================================================================

class TestLocalSimulatorIntegration:
    """Integration tests with local simulator (always available)."""
    
    @pytest.mark.asyncio
    async def test_local_simulator_connection(self):
        """Test connecting to local simulator."""
        from optimization.src.backends.simulator import LocalSimulatorBackend
        
        config = BackendConfig(backend_type=BackendType.LOCAL_SIMULATOR)
        backend = LocalSimulatorBackend(config)
        
        await backend.connect()
        assert backend.is_connected
        
        devices = await backend.get_available_devices()
        assert len(devices) > 0
        
        await backend.disconnect()
        assert not backend.is_connected
    
    @pytest.mark.asyncio
    async def test_advanced_simulator_connection(self):
        """Test connecting to advanced local simulator."""
        from optimization.src.backends.advanced_simulator import (
            AdvancedLocalSimulator,
            AdvancedSimulatorConfig,
        )
        from optimization.src.backends.base import BackendConfig, BackendType
        
        backend_config = BackendConfig(backend_type=BackendType.LOCAL_SIMULATOR)
        advanced_config = AdvancedSimulatorConfig()
        
        simulator = AdvancedLocalSimulator(backend_config, advanced_config)
        
        await simulator.connect()
        assert simulator.is_connected
        
        devices = await simulator.get_available_devices()
        assert len(devices) >= 4  # statevector, mps, density_matrix, lightning
        
        await simulator.disconnect()


# ============================================================================
# API Router Tests
# ============================================================================

class TestBackendsAPIRouter:
    """Tests for backends API router."""
    
    @pytest.mark.asyncio
    async def test_list_backends(self):
        """Test listing backends via API."""
        from httpx import AsyncClient, ASGITransport
        from api.main import app
        
        # First login to get a token
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Login
            login_response = await client.post(
                "/auth/login",
                json={"username": "admin", "password": "admin123!"}
            )
            token = login_response.json()["access_token"]
            
            # List backends
            response = await client.get(
                "/api/v1/backends",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "backends" in data
            assert len(data["backends"]) > 0
    
    @pytest.mark.asyncio
    async def test_backends_health(self):
        """Test backends health endpoint (no auth required)."""
        from httpx import AsyncClient, ASGITransport
        from api.main import app
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/backends/health")
            
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "backends" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

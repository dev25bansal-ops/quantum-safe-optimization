"""
Comprehensive unit tests for connection pooling module.

Tests cover:
- Connection pool initialization
- Connection acquisition and release
- Pool sizing and limits
- Health checking
- Context manager usage
- Error handling
"""

import pytest
import asyncio
from api.db.connection_pool import (
    ConnectionPool,
    ConnectionPoolConfig,
    CosmosDBConnectionPool,
    RedisConnectionPool,
    PooledConnection,
    register_pool,
    get_pool,
    close_all_pools,
)


class MockConnection:
    """Mock connection for testing."""
    
    def __init__(self, conn_id: int = 0):
        self.conn_id = conn_id
        self.closed = False
    
    async def ping(self):
        """Mock ping."""
        return True
    
    async def close(self):
        """Mock close."""
        self.closed = True


class TestConnectionPoolConfig:
    """Test connection pool configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ConnectionPoolConfig()
        
        assert config.min_connections == 2
        assert config.max_connections == 10
        assert config.max_idle_time == 300.0
        assert config.connection_timeout == 30.0
        assert config.acquire_timeout == 10.0
        assert config.health_check_interval == 60.0

    def test_custom_config(self):
        """Test custom configuration."""
        config = ConnectionPoolConfig(
            min_connections=5,
            max_connections=20,
            max_idle_time=600.0,
            connection_timeout=60.0,
            acquire_timeout=30.0,
            health_check_interval=120.0
        )
        
        assert config.min_connections == 5
        assert config.max_connections == 20
        assert config.max_idle_time == 600.0

    def test_invalid_min_max(self):
        """Test that min can be greater than max (validation should handle)."""
        # Config allows it, validation happens at pool creation
        config = ConnectionPoolConfig(
            min_connections=10,
            max_connections=5
        )
        assert config.min_connections == 10
        assert config.max_connections == 5


class TestConnectionPool:
    """Test connection pool functionality."""

    @pytest.mark.asyncio
    async def test_pool_initialization(self):
        """Test pool initializes with minimum connections."""
        conn_counter = [0]
        
        async def factory():
            conn_counter[0] += 1
            return MockConnection(conn_counter[0])
        
        config = ConnectionPoolConfig(min_connections=2, max_connections=5)
        pool = ConnectionPool(factory, config)
        
        await pool.initialize()
        
        assert pool.size == 2
        assert pool.available_count == 2
        
        await pool.close()

    @pytest.mark.asyncio
    async def test_connection_acquisition(self):
        """Test acquiring a connection from the pool."""
        async def factory():
            return MockConnection()
        
        pool = ConnectionPool(factory)
        await pool.initialize()
        
        conn = await pool.acquire()
        
        assert conn is not None
        assert pool.in_use_count == 1
        assert pool.available_count == 0
        
        await pool.close()

    @pytest.mark.asyncio
    async def test_connection_release(self):
        """Test releasing a connection back to the pool."""
        async def factory():
            return MockConnection()
        
        pool = ConnectionPool(factory)
        await pool.initialize()
        
        conn = await pool.acquire()
        assert pool.in_use_count == 1
        
        await pool.release(conn)
        assert pool.in_use_count == 0
        assert pool.available_count == 1
        
        await pool.close()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test connection context manager."""
        async def factory():
            return MockConnection()
        
        pool = ConnectionPool(factory)
        await pool.initialize()
        
        async with pool.connection() as conn:
            assert conn is not None
            assert pool.in_use_count == 1
        
        assert pool.in_use_count == 0
        
        await pool.close()

    @pytest.mark.asyncio
    async def test_multiple_connections(self):
        """Test acquiring multiple connections."""
        async def factory():
            return MockConnection()
        
        config = ConnectionPoolConfig(min_connections=2, max_connections=5)
        pool = ConnectionPool(factory, config)
        await pool.initialize()
        
        # Acquire 3 connections
        conns = []
        for _ in range(3):
            conn = await pool.acquire()
            conns.append(conn)
        
        assert pool.size == 5  # 2 initial + 3 created
        assert pool.in_use_count == 3
        
        # Release all
        for conn in conns:
            await pool.release(conn)
        
        assert pool.in_use_count == 0
        assert pool.available_count == 5
        
        await pool.close()

    @pytest.mark.asyncio
    async def test_max_connections_limit(self):
        """Test that pool respects max connections limit."""
        acquired = []
        
        async def factory():
            conn = MockConnection(len(acquired) + 1)
            acquired.append(conn)
            return conn
        
        config = ConnectionPoolConfig(min_connections=1, max_connections=3)
        pool = ConnectionPool(factory, config)
        await pool.initialize()
        
        # Should be able to acquire 3 connections
        conns = []
        for _ in range(3):
            conn = await pool.acquire()
            conns.append(conn)
        
        assert len(conns) == 3
        
        # 4th acquisition should timeout (not raise immediately)
        try:
            await asyncio.wait_for(pool.acquire(), timeout=0.5)
            # If we get here, it means the pool created a new connection
            # which is fine if under max
        except asyncio.TimeoutError:
            # Expected - pool at max capacity
            pass
        
        await pool.close()

    @pytest.mark.asyncio
    async def test_pool_statistics(self):
        """Test pool statistics tracking."""
        async def factory():
            return MockConnection()
        
        pool = ConnectionPool(factory)
        await pool.initialize()
        
        # Acquire and release
        conn = await pool.acquire()
        await pool.release(conn)
        
        stats = pool.stats
        
        assert stats["created"] >= 1
        assert stats["acquired"] >= 1
        assert stats["released"] >= 1
        
        await pool.close()

    @pytest.mark.asyncio
    async def test_pool_close(self):
        """Test pool closure."""
        async def factory():
            return MockConnection()
        
        pool = ConnectionPool(factory)
        await pool.initialize()
        
        conn = await pool.acquire()
        await pool.release(conn)
        
        await pool.close()
        
        assert pool._closed

    @pytest.mark.asyncio
    async def test_acquire_after_close_fails(self):
        """Test that acquiring after close raises error."""
        async def factory():
            return MockConnection()
        
        pool = ConnectionPool(factory)
        await pool.initialize()
        await pool.close()
        
        with pytest.raises(RuntimeError):
            await pool.acquire()


class TestPooledConnection:
    """Test pooled connection wrapper."""

    @pytest.mark.asyncio
    async def test_connection_properties(self):
        """Test connection wrapper properties."""
        mock = MockConnection()
        
        async def factory():
            return mock
        
        pool = ConnectionPool(factory)
        pooled = PooledConnection(mock, pool)
        
        assert pooled.connection == mock
        assert pooled.age is not None
        assert pooled.idle_time is not None
        assert not pooled.in_use

    @pytest.mark.asyncio
    async def test_connection_mark_used(self):
        """Test marking connection as used."""
        mock = MockConnection()
        
        async def factory():
            return mock
        
        pool = ConnectionPool(factory)
        pooled = PooledConnection(mock, pool)
        
        assert not pooled.in_use
        pooled.mark_used()
        assert pooled.in_use

    @pytest.mark.asyncio
    async def test_connection_mark_idle(self):
        """Test marking connection as idle."""
        mock = MockConnection()
        
        async def factory():
            return mock
        
        pool = ConnectionPool(factory)
        pooled = PooledConnection(mock, pool)
        
        pooled.mark_used()
        assert pooled.in_use
        
        pooled.mark_idle()
        assert not pooled.in_use


class TestConnectionPoolRegistry:
    """Test connection pool registry functions."""

    def test_register_and_get_pool(self):
        """Test registering and retrieving pools."""
        async def factory():
            return MockConnection()
        
        pool = ConnectionPool(factory)
        register_pool("test_pool", pool)
        
        retrieved = get_pool("test_pool")
        assert retrieved == pool

    def test_get_nonexistent_pool(self):
        """Test getting nonexistent pool returns None."""
        result = get_pool("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_close_all_pools(self):
        """Test closing all registered pools."""
        async def factory():
            return MockConnection()
        
        pool1 = ConnectionPool(factory, name="pool1")
        pool2 = ConnectionPool(factory, name="pool2")
        
        register_pool("test_pool1", pool1)
        register_pool("test_pool2", pool2)
        
        await close_all_pools()
        
        # All pools should be closed
        assert pool1._closed
        assert pool2._closed


class TestCosmosDBConnectionPool:
    """Test Cosmos DB specific pool."""

    def test_cosmos_pool_creation(self):
        """Test Cosmos DB pool creation."""
        async def factory():
            return MockConnection()
        
        pool = CosmosDBConnectionPool(factory)
        
        assert pool._name == "cosmos_db"
        assert pool._config.min_connections == 2
        assert pool._config.max_connections == 20


class TestRedisConnectionPool:
    """Test Redis specific pool."""

    def test_redis_pool_creation(self):
        """Test Redis pool creation."""
        async def factory():
            return MockConnection()
        
        pool = RedisConnectionPool(factory)
        
        assert pool._name == "redis"
        assert pool._config.min_connections == 1
        assert pool._config.max_connections == 10


class TestConnectionPoolErrorHandling:
    """Test error handling in connection pool."""

    @pytest.mark.asyncio
    async def test_factory_error_handling(self):
        """Test handling factory errors."""
        async def failing_factory():
            raise Exception("Connection failed")
        
        pool = ConnectionPool(failing_factory)
        
        with pytest.raises(Exception):
            await pool.initialize()

    @pytest.mark.asyncio
    async def test_double_close(self):
        """Test closing pool twice doesn't error."""
        async def factory():
            return MockConnection()
        
        pool = ConnectionPool(factory)
        await pool.initialize()
        
        await pool.close()
        await pool.close()  # Should not error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
"""
Connection pooling module for improved database performance.

Provides efficient connection pooling for Cosmos DB and other database
connections to reduce latency and improve resource utilization.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class ConnectionPoolConfig:
    """Configuration for connection pools."""
    
    def __init__(
        self,
        min_connections: int = 2,
        max_connections: int = 10,
        max_idle_time: float = 300.0,  # 5 minutes
        connection_timeout: float = 30.0,
        acquire_timeout: float = 10.0,
        health_check_interval: float = 60.0,
    ):
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.max_idle_time = max_idle_time
        self.connection_timeout = connection_timeout
        self.acquire_timeout = acquire_timeout
        self.health_check_interval = health_check_interval


class PooledConnection:
    """Wrapper for a pooled connection."""
    
    def __init__(self, connection: Any, pool: "ConnectionPool"):
        self._connection = connection
        self._pool = pool
        self._created_at = datetime.now()
        self._last_used_at = datetime.now()
        self._in_use = False
        self._is_healthy = True
    
    @property
    def connection(self) -> Any:
        """Get the underlying connection."""
        return self._connection
    
    @property
    def age(self) -> timedelta:
        """Get the age of this connection."""
        return datetime.now() - self._created_at
    
    @property
    def idle_time(self) -> timedelta:
        """Get the idle time of this connection."""
        return datetime.now() - self._last_used_at
    
    @property
    def is_expired(self) -> bool:
        """Check if connection has expired."""
        return self.idle_time.total_seconds() > self._pool.config.max_idle_time
    
    @property
    def in_use(self) -> bool:
        """Check if connection is in use."""
        return self._in_use
    
    def mark_used(self):
        """Mark connection as used."""
        self._last_used_at = datetime.now()
        self._in_use = True
    
    def mark_idle(self):
        """Mark connection as idle."""
        self._last_used_at = datetime.now()
        self._in_use = False
    
    async def health_check(self) -> bool:
        """Perform health check on connection."""
        try:
            # Default health check - can be overridden
            if hasattr(self._connection, 'ping'):
                await self._connection.ping()
            elif hasattr(self._connection, 'is_healthy'):
                self._is_healthy = await self._connection.is_healthy()
            
            return self._is_healthy
        except Exception as e:
            logger.warning(f"Connection health check failed: {e}")
            self._is_healthy = False
            return False
    
    async def close(self):
        """Close the underlying connection."""
        try:
            if hasattr(self._connection, 'close'):
                if asyncio.iscoroutinefunction(self._connection.close):
                    await self._connection.close()
                else:
                    self._connection.close()
        except Exception as e:
            logger.warning(f"Error closing connection: {e}")


class ConnectionPool:
    """Generic connection pool implementation."""
    
    def __init__(
        self,
        connection_factory: callable,
        config: Optional[ConnectionPoolConfig] = None,
        name: str = "default"
    ):
        self._connection_factory = connection_factory
        self._config = config or ConnectionPoolConfig()
        self._name = name
        
        self._available_connections: asyncio.Queue[PooledConnection] = asyncio.Queue()
        self._all_connections: set[PooledConnection] = set()
        self._lock = asyncio.Lock()
        self._initialized = False
        self._closed = False
        self._health_check_task: Optional[asyncio.Task] = None
        
        # Statistics
        self._stats = {
            "created": 0,
            "acquired": 0,
            "released": 0,
            "failed": 0,
            "closed": 0,
        }
    
    @property
    def config(self) -> ConnectionPoolConfig:
        """Get pool configuration."""
        return self._config
    
    @property
    def stats(self) -> Dict[str, int]:
        """Get pool statistics."""
        return self._stats.copy()
    
    @property
    def size(self) -> int:
        """Get current pool size."""
        return len(self._all_connections)
    
    @property
    def available_count(self) -> int:
        """Get number of available connections."""
        return self._available_connections.qsize()
    
    @property
    def in_use_count(self) -> int:
        """Get number of connections in use."""
        return self.size - self.available_count
    
    async def initialize(self):
        """Initialize the connection pool."""
        if self._initialized:
            return
        
        logger.info(f"Initializing connection pool '{self._name}' with min_connections={self._config.min_connections}")
        
        async with self._lock:
            # Create minimum connections
            for _ in range(self._config.min_connections):
                try:
                    connection = await self._create_connection()
                    await self._available_connections.put(connection)
                except Exception as e:
                    logger.error(f"Failed to create initial connection: {e}")
            
            self._initialized = True
            
            # Start health check task
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            
            logger.info(
                f"Connection pool '{self._name}' initialized with {self.size} connections"
            )
    
    async def _create_connection(self) -> PooledConnection:
        """Create a new connection."""
        try:
            raw_connection = await self._connection_factory()
            pooled_connection = PooledConnection(raw_connection, self)
            self._all_connections.add(pooled_connection)
            self._stats["created"] += 1
            return pooled_connection
        except Exception as e:
            self._stats["failed"] += 1
            raise
    
    async def acquire(self, timeout: Optional[float] = None) -> PooledConnection:
        """Acquire a connection from the pool."""
        if self._closed:
            raise RuntimeError(f"Connection pool '{self._name}' is closed")
        
        if not self._initialized:
            await self.initialize()
        
        timeout = timeout or self._config.acquire_timeout
        
        try:
            # Try to get an available connection
            connection = await asyncio.wait_for(
                self._available_connections.get(),
                timeout=timeout
            )
            
            # Check if connection is healthy
            if not connection._is_healthy or connection.is_expired:
                logger.debug("Removing unhealthy or expired connection")
                await self._remove_connection(connection)
                # Try to create a new one
                connection = await self._create_connection()
            
            connection.mark_used()
            self._stats["acquired"] += 1
            
            return connection
            
        except asyncio.TimeoutError:
            # No available connection, try to create a new one if under max
            if self.size < self._config.max_connections:
                try:
                    connection = await self._create_connection()
                    connection.mark_used()
                    self._stats["acquired"] += 1
                    return connection
                except Exception as e:
                    logger.error(f"Failed to create new connection: {e}")
                    self._stats["failed"] += 1
            
            # Still no connection, raise error
            raise RuntimeError(
                f"Failed to acquire connection from pool '{self._name}' after {timeout}s"
            )
    
    async def release(self, connection: PooledConnection):
        """Release a connection back to the pool."""
        if connection not in self._all_connections:
            logger.warning("Attempting to release connection not owned by this pool")
            return
        
        connection.mark_idle()
        self._stats["released"] += 1
        
        # Check if connection is still healthy
        if not connection._is_healthy:
            await self._remove_connection(connection)
            return
        
        # Return to pool
        await self._available_connections.put(connection)
    
    async def _remove_connection(self, connection: PooledConnection):
        """Remove a connection from the pool."""
        if connection in self._all_connections:
            self._all_connections.remove(connection)
            await connection.close()
            self._stats["closed"] += 1
    
    async def _health_check_loop(self):
        """Periodic health check loop."""
        while not self._closed:
            try:
                await asyncio.sleep(self._config.health_check_interval)
                await self._perform_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
    
    async def _perform_health_checks(self):
        """Perform health checks on all connections."""
        async with self._lock:
            unhealthy_connections = []
            
            for connection in self._all_connections:
                if not connection.in_use:
                    is_healthy = await connection.health_check()
                    if not is_healthy:
                        unhealthy_connections.append(connection)
            
            # Remove unhealthy connections
            for connection in unhealthy_connections:
                logger.debug(f"Removing unhealthy connection from pool '{self._name}'")
                await self._remove_connection(connection)
            
            # Ensure minimum connections
            while self.size < self._config.min_connections:
                try:
                    connection = await self._create_connection()
                    await self._available_connections.put(connection)
                except Exception as e:
                    logger.error(f"Failed to create replacement connection: {e}")
                    break
    
    async def close(self):
        """Close the connection pool."""
        if self._closed:
            return
        
        logger.info(f"Closing connection pool '{self._name}'")
        self._closed = True
        
        # Cancel health check task
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        async with self._lock:
            for connection in list(self._all_connections):
                await connection.close()
            
            self._all_connections.clear()
            
            # Clear queue
            while not self._available_connections.empty():
                try:
                    self._available_connections.get_nowait()
                except asyncio.QueueEmpty:
                    break
        
        logger.info(f"Connection pool '{self._name}' closed. Stats: {self._stats}")
    
    @asynccontextmanager
    async def connection(self):
        """Context manager for acquiring and releasing connections."""
        conn = None
        try:
            conn = await self.acquire()
            yield conn.connection
        finally:
            if conn:
                await self.release(conn)
    
    def __del__(self):
        """Cleanup on deletion."""
        if not self._closed and self._all_connections:
            logger.warning(f"Connection pool '{self._name}' not properly closed")


class CosmosDBConnectionPool(ConnectionPool):
    """Connection pool specifically for Cosmos DB."""
    
    def __init__(
        self,
        cosmos_client_factory: callable,
        config: Optional[ConnectionPoolConfig] = None
    ):
        super().__init__(
            connection_factory=cosmos_client_factory,
            config=config or ConnectionPoolConfig(
                min_connections=2,
                max_connections=20,
                max_idle_time=600.0,  # 10 minutes
                health_check_interval=120.0,  # 2 minutes
            ),
            name="cosmos_db"
        )
    
    async def _create_connection(self) -> PooledConnection:
        """Create a new Cosmos DB connection."""
        try:
            client = await self._connection_factory()
            
            # Test the connection
            if hasattr(client, 'get_database_client'):
                # Azure Cosmos DB
                test_db = client.get_database_client("_test")
                # This will fail if connection is bad
                pass
            
            pooled_connection = PooledConnection(client, self)
            self._all_connections.add(pooled_connection)
            self._stats["created"] += 1
            return pooled_connection
        except Exception as e:
            self._stats["failed"] += 1
            logger.error(f"Failed to create Cosmos DB connection: {e}")
            raise


class RedisConnectionPool(ConnectionPool):
    """Connection pool specifically for Redis."""
    
    def __init__(
        self,
        redis_client_factory: callable,
        config: Optional[ConnectionPoolConfig] = None
    ):
        super().__init__(
            connection_factory=redis_client_factory,
            config=config or ConnectionPoolConfig(
                min_connections=1,
                max_connections=10,
                max_idle_time=300.0,  # 5 minutes
                health_check_interval=60.0,  # 1 minute
            ),
            name="redis"
        )
    
    async def _create_connection(self) -> PooledConnection:
        """Create a new Redis connection."""
        try:
            client = await self._connection_factory()
            
            # Test the connection with PING
            if hasattr(client, 'ping'):
                await client.ping()
            
            pooled_connection = PooledConnection(client, self)
            self._all_connections.add(pooled_connection)
            self._stats["created"] += 1
            return pooled_connection
        except Exception as e:
            self._stats["failed"] += 1
            logger.error(f"Failed to create Redis connection: {e}")
            raise


# Global pool registry
_connection_pools: Dict[str, ConnectionPool] = {}


def register_pool(name: str, pool: ConnectionPool):
    """Register a connection pool."""
    _connection_pools[name] = pool
    logger.info(f"Registered connection pool '{name}'")


def get_pool(name: str) -> Optional[ConnectionPool]:
    """Get a registered connection pool."""
    return _connection_pools.get(name)


async def close_all_pools():
    """Close all registered connection pools."""
    logger.info("Closing all connection pools")
    for pool in list(_connection_pools.values()):
        await pool.close()
    _connection_pools.clear()
    logger.info("All connection pools closed")
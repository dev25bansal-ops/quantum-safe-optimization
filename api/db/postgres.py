"""PostgreSQL Database Module for QSOP.

Alternative to Cosmos DB for deployments without Azure.
Uses SQLAlchemy with asyncpg for async operations.

Usage:
    # In docker-compose, uncomment the postgres service
    # Set DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/qsop

Required: pip install sqlalchemy[asyncio] asyncpg
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://qsop:qsop@localhost:5432/qsop")


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class PostgresManager:
    """Async PostgreSQL connection manager."""

    _instance: Optional["PostgresManager"] = None

    def __init__(self):
        self._engine = None
        self._session_factory = None
        self._initialized = False

    async def initialize(self, database_url: str | None = None):
        """Initialize database engine and session factory."""
        if self._initialized:
            return

        url = database_url or DATABASE_URL
        self._engine = create_async_engine(
            url,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=3600,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self._initialized = True
        logger.info("postgres_initialized", url=url.split("@")[-1] if "@" in url else url)

    async def close(self):
        """Close database connections."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._initialized = False
            logger.info("postgres_closed")

    @asynccontextmanager
    async def session(self):
        """Get a database session context manager."""
        if not self._initialized:
            await self.initialize()

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def create_tables(self):
        """Create all tables defined in models."""
        if not self._initialized:
            await self.initialize()

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("postgres_tables_created")

    async def health_check(self) -> dict[str, Any]:
        """Check database connectivity."""
        import time

        start = time.time()
        try:
            async with self._session_factory() as session:
                from sqlalchemy import text

                await session.execute(text("SELECT 1"))
            latency_ms = (time.time() - start) * 1000
            return {
                "healthy": True,
                "latency_ms": round(latency_ms, 2),
                "database": "postgresql",
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "database": "postgresql",
            }


# Global instance
postgres_manager = PostgresManager()


async def init_postgres(database_url: str | None = None):
    """Initialize PostgreSQL connection."""
    await postgres_manager.initialize(database_url=database_url)
    await postgres_manager.create_tables()


async def close_postgres():
    """Close PostgreSQL connection."""
    await postgres_manager.close()


# SQLAlchemly models for QSOP tables

from datetime import UTC, datetime
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, Index, JSON


class JobModel(Base):
    """SQLAlchemy model for jobs table."""

    __tablename__ = "jobs"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    problem_type = Column(String(32), nullable=False)
    problem_config = Column(JSON, nullable=False)
    parameters = Column(JSON, nullable=True)
    backend = Column(String(64), nullable=False)
    priority = Column(Integer, default=5)
    status = Column(String(32), nullable=False, default="queued", index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    result = Column(JSON, nullable=True)
    encrypted_result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_user_status", "user_id", "status"),
        Index("idx_user_created", "user_id", "created_at"),
    )


class UserModel(Base):
    """SQLAlchemy model for users table."""

    __tablename__ = "users"

    id = Column(String(64), primary_key=True)
    username = Column(String(128), unique=True, nullable=False, index=True)
    email = Column(String(256), unique=True, nullable=True)
    password_hash = Column(String(256), nullable=False)
    roles = Column(JSON, default=["user"])
    is_active = Column(Integer, default=1)
    kem_public_key = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)


class AuditLogModel(Base):
    """SQLAlchemy model for audit_logs table."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True)
    user_id = Column(String(64), nullable=True, index=True)
    action = Column(String(128), nullable=False)
    resource = Column(String(256), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(64), nullable=True)

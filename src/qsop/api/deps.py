"""Dependency injection setup for FastAPI."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from qsop.infrastructure.persistence.sqlalchemy.job_repo import SQLAlchemyJobRepository
from qsop.infrastructure.persistence.sqlalchemy.key_repo import SQLAlchemyKeyRepository
from qsop.infrastructure.keystore.local_dev import LocalDevKeyStore
from qsop.infrastructure.artifact_store.filesystem import FilesystemArtifactStore
from qsop.infrastructure.events.inmem import InMemoryEventBus


class Settings:
    """Application settings loaded from environment."""

    def __init__(self) -> None:
        self.database_url: str = os.getenv(
            "DATABASE_URL", "sqlite+aiosqlite:///./qsop.db"
        )
        self.redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.vault_url: str = os.getenv("VAULT_URL", "")
        self.s3_bucket: str = os.getenv("S3_BUCKET", "")
        self.artifact_path: str = os.getenv("ARTIFACT_PATH", "./artifacts")
        self.jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-change-in-prod")
        self.jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
        self.rate_limit_requests: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
        self.rate_limit_window: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
        self.environment: str = os.getenv("ENVIRONMENT", "development")


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


_engine = None
_session_factory = None


def get_engine(settings: Settings | None = None):
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        settings = settings or get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.environment == "development",
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_session_factory(settings: Settings | None = None) -> async_sessionmaker[AsyncSession]:
    """Get or create the session factory."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine(settings)
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Database session dependency."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


class ServiceContainer:
    """Container for application services (singleton per request context)."""

    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self._job_repo: SQLAlchemyJobRepository | None = None
        self._key_repo: SQLAlchemyKeyRepository | None = None
        self._keystore: LocalDevKeyStore | None = None
        self._artifact_store: FilesystemArtifactStore | None = None
        self._event_bus: InMemoryEventBus | None = None

    @property
    def job_repo(self) -> SQLAlchemyJobRepository:
        if self._job_repo is None:
            self._job_repo = SQLAlchemyJobRepository(self.db)
        return self._job_repo

    @property
    def key_repo(self) -> SQLAlchemyKeyRepository:
        if self._key_repo is None:
            self._key_repo = SQLAlchemyKeyRepository(self.db)
        return self._key_repo

    @property
    def keystore(self) -> LocalDevKeyStore:
        if self._keystore is None:
            self._keystore = LocalDevKeyStore(self.settings.artifact_path)
        return self._keystore

    @property
    def artifact_store(self) -> FilesystemArtifactStore:
        if self._artifact_store is None:
            self._artifact_store = FilesystemArtifactStore(self.settings.artifact_path)
        return self._artifact_store

    @property
    def event_bus(self) -> InMemoryEventBus:
        if self._event_bus is None:
            self._event_bus = InMemoryEventBus()
        return self._event_bus


async def get_service_container(
    db: DatabaseSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ServiceContainer:
    """Get the service container for the current request."""
    return ServiceContainer(db, settings)


ServiceContainerDep = Annotated[ServiceContainer, Depends(get_service_container)]


async def get_job_service(container: ServiceContainerDep) -> SQLAlchemyJobRepository:
    """Get the job repository."""
    return container.job_repo


async def get_key_service(container: ServiceContainerDep) -> SQLAlchemyKeyRepository:
    """Get the key repository."""
    return container.key_repo


def get_current_tenant(request: Request) -> str:
    """Extract current tenant from request state (set by auth middleware)."""
    return getattr(request.state, "tenant_id", "default")


CurrentTenant = Annotated[str, Depends(get_current_tenant)]


@asynccontextmanager
async def lifespan_context(settings: Settings | None = None):
    """Application lifespan context manager for startup/shutdown."""
    settings = settings or get_settings()
    engine = get_engine(settings)
    
    # Import models to ensure they're registered
    from qsop.infrastructure.persistence.sqlalchemy.models import Base
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    await engine.dispose()

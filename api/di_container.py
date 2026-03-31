"""
Dependency Injection Container for QSOP.

Provides centralized management of dependencies.
"""

import os
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

T = TypeVar("T")


@dataclass
class ServiceDescriptor:
    """Describes a registered service."""

    service_type: type
    factory: Callable[[], Any] | None = None
    instance: Any = None
    singleton: bool = True


class DIContainer:
    """
    Simple dependency injection container.

    Usage:
        container = DIContainer()
        container.register(DatabaseService, lambda: DatabaseService(url=os.getenv("DB_URL")))
        container.register(UserRepository, lambda: UserRepository(container.get(DatabaseService)))

        db = container.get(DatabaseService)
    """

    def __init__(self):
        self._services: dict[type, ServiceDescriptor] = {}
        self._instances: dict[type, Any] = {}

    def register(
        self,
        service_type: type[T],
        factory: Callable[[], T] | None = None,
        singleton: bool = True,
    ) -> None:
        """Register a service type with an optional factory."""
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            factory=factory,
            singleton=singleton,
        )

    def register_instance(self, service_type: type[T], instance: T) -> None:
        """Register an existing instance."""
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            instance=instance,
            singleton=True,
        )
        self._instances[service_type] = instance

    def get(self, service_type: type[T]) -> T:
        """Get or create a service instance."""
        if service_type in self._instances:
            return self._instances[service_type]

        if service_type not in self._services:
            raise KeyError(f"Service {service_type.__name__} not registered")

        descriptor = self._services[service_type]

        if descriptor.instance is not None:
            return descriptor.instance

        if descriptor.factory is not None:
            instance = descriptor.factory()
            if descriptor.singleton:
                self._instances[service_type] = instance
            return instance

        raise ValueError(f"No factory or instance for {service_type.__name__}")

    def try_get(self, service_type: type[T]) -> T | None:
        """Try to get a service, returning None if not found."""
        try:
            return self.get(service_type)
        except (KeyError, ValueError):
            return None

    def clear(self) -> None:
        """Clear all registrations."""
        self._services.clear()
        self._instances.clear()


container = DIContainer()


def init_container() -> DIContainer:
    """Initialize the container with all application services."""
    global container
    container.clear()

    from api.db.repository import UserRepository, JobRepository, KeyRepository
    from api.security.token_revocation import TokenRevocationService

    container.register(
        TokenRevocationService,
        lambda: TokenRevocationService(redis_url=os.getenv("REDIS_URL")),
        singleton=True,
    )

    return container


def get_container() -> DIContainer:
    """Get the global container instance."""
    return container

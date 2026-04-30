"""
Dependency Injection Container for improved testability and loose coupling.

Provides a centralized dependency management system following the
Dependency Inversion Principle for better maintainability and testing.
"""

import logging
from typing import Any, Callable, Dict, Optional, Type, TypeVar, get_type_hints
from functools import wraps
from inspect import signature, Parameter
import asyncio

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ServiceLifetime:
    """Service lifetime options."""
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"


class ServiceDescriptor:
    """Descriptor for a registered service."""
    
    def __init__(
        self,
        factory: Callable,
        lifetime: str = ServiceLifetime.TRANSIENT,
        interface: Optional[Type] = None
    ):
        self.factory = factory
        self.lifetime = lifetime
        self.interface = interface
        self._instance: Optional[Any] = None
    
    def get_instance(self, container: "DIContainer") -> Any:
        """Get or create service instance."""
        if self.lifetime == ServiceLifetime.SINGLETON:
            if self._instance is None:
                self._instance = self._create_instance(container)
            return self._instance
        elif self.lifetime == ServiceLifetime.SCOPED:
            return self._create_instance(container)
        else:  # TRANSIENT
            return self._create_instance(container)
    
    def _create_instance(self, container: "DIContainer") -> Any:
        """Create a new instance with dependency injection."""
        # Get factory signature
        sig = signature(self.factory)
        
        # Resolve dependencies
        kwargs = {}
        for name, param in sig.parameters.items():
            if name == 'self':
                continue
            
            # Skip if no type hint
            if param.annotation == Parameter.empty:
                continue
            
            # Resolve dependency
            dependency = container.resolve(param.annotation)
            if dependency is not None:
                kwargs[name] = dependency
        
        # Create instance
        return self.factory(**kwargs)


class DIContainer:
    """Dependency Injection Container."""
    
    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._scoped_instances: Dict[Type, Any] = {}
        self._lock = asyncio.Lock()
    
    def register(
        self,
        interface: Type[T],
        factory: Callable[..., T],
        lifetime: str = ServiceLifetime.TRANSIENT
    ) -> None:
        """Register a service.
        
        Args:
            interface: The interface type to register
            factory: Factory function to create instances
            lifetime: Service lifetime (singleton, transient, scoped)
        """
        descriptor = ServiceDescriptor(
            factory=factory,
            lifetime=lifetime,
            interface=interface
        )
        
        self._services[interface] = descriptor
        logger.debug(f"Registered service: {interface.__name__} ({lifetime})")
    
    def register_singleton(
        self,
        interface: Type[T],
        factory: Callable[..., T]
    ) -> None:
        """Register a singleton service."""
        self.register(interface, factory, ServiceLifetime.SINGLETON)
    
    def register_transient(
        self,
        interface: Type[T],
        factory: Callable[..., T]
    ) -> None:
        """Register a transient service."""
        self.register(interface, factory, ServiceLifetime.TRANSIENT)
    
    def register_scoped(
        self,
        interface: Type[T],
        factory: Callable[..., T]
    ) -> None:
        """Register a scoped service."""
        self.register(interface, factory, ServiceLifetime.SCOPED)
    
    def register_instance(
        self,
        interface: Type[T],
        instance: T
    ) -> None:
        """Register an existing instance as a singleton."""
        descriptor = ServiceDescriptor(
            factory=lambda: instance,
            lifetime=ServiceLifetime.SINGLETON,
            interface=interface
        )
        descriptor._instance = instance
        self._services[interface] = descriptor
        logger.debug(f"Registered instance: {interface.__name__}")
    
    def resolve(self, interface: Type[T]) -> Optional[T]:
        """Resolve a service instance.
        
        Args:
            interface: The interface type to resolve
            
        Returns:
            Service instance or None if not registered
        """
        descriptor = self._services.get(interface)
        if descriptor is None:
            logger.warning(f"Service not registered: {interface.__name__}")
            return None
        
        return descriptor.get_instance(self)
    
    def resolve_required(self, interface: Type[T]) -> T:
        """Resolve a required service instance.
        
        Args:
            interface: The interface type to resolve
            
        Returns:
            Service instance
            
        Raises:
            ValueError: If service is not registered
        """
        instance = self.resolve(interface)
        if instance is None:
            raise ValueError(f"Required service not registered: {interface.__name__}")
        return instance
    
    async def create_scope(self) -> "DIScope":
        """Create a new scope for scoped services."""
        return DIScope(self)
    
    def is_registered(self, interface: Type) -> bool:
        """Check if a service is registered."""
        return interface in self._services
    
    def clear(self) -> None:
        """Clear all registered services."""
        self._services.clear()
        self._scoped_instances.clear()
        logger.debug("Cleared all services")


class DIScope:
    """Scope for scoped service instances."""
    
    def __init__(self, container: DIContainer):
        self._container = container
        self._instances: Dict[Type, Any] = {}
    
    def resolve(self, interface: Type[T]) -> Optional[T]:
        """Resolve a service within this scope."""
        descriptor = self._container._services.get(interface)
        if descriptor is None:
            return None
        
        if descriptor.lifetime == ServiceLifetime.SCOPED:
            if interface not in self._instances:
                self._instances[interface] = descriptor._create_instance(self._container)
            return self._instances[interface]
        
        return descriptor.get_instance(self._container)
    
    def dispose(self) -> None:
        """Dispose all scoped instances."""
        for instance in self._instances.values():
            if hasattr(instance, 'dispose'):
                try:
                    instance.dispose()
                except Exception as e:
                    logger.error(f"Error disposing instance: {e}")
        self._instances.clear()


def inject(*dependencies: Type):
    """Decorator for dependency injection.
    
    Usage:
        @inject(DatabaseService, CacheService)
        class MyService:
            def __init__(self, db: DatabaseService, cache: CacheService):
                self.db = db
                self.cache = cache
    """
    def decorator(cls):
        original_init = cls.__init__
        
        @wraps(original_init)
        def new_init(self, *args, **kwargs):
            # Get container from kwargs or use global
            container = kwargs.pop('container', None)
            if container is None:
                from .di_container import get_container
                container = get_container()
            
            # Resolve dependencies
            for dep_type in dependencies:
                dep_name = dep_type.__name__.lower()
                if dep_name not in kwargs:
                    instance = container.resolve(dep_type)
                    if instance is not None:
                        kwargs[dep_name] = instance
            
            original_init(self, *args, **kwargs)
        
        cls.__init__ = new_init
        return cls
    
    return decorator


def factory(interface: Type[T]):
    """Decorator for factory functions.
    
    Usage:
        @factory(IMyService)
        def create_my_service(db: DatabaseService) -> IMyService:
            return MyService(db)
    """
    def decorator(func):
        func._interface = interface
        return func
    return decorator


# Global container instance
_global_container: Optional[DIContainer] = None


def get_container() -> DIContainer:
    """Get the global DI container."""
    global _global_container
    if _global_container is None:
        _global_container = DIContainer()
    return _global_container


def set_container(container: DIContainer) -> None:
    """Set the global DI container."""
    global _global_container
    _global_container = container


def configure_services(configurator: Callable[[DIContainer], None]) -> None:
    """Configure services with a configurator function.
    
    Usage:
        def configure(container: DIContainer):
            container.register_singleton(IDatabase, Database)
            container.register_transient(ICache, Cache)
        
        configure_services(configure)
    """
    container = get_container()
    configurator(container)


class ServiceProvider:
    """Service provider for accessing services."""
    
    def __init__(self, container: DIContainer):
        self._container = container
    
    def get_service(self, interface: Type[T]) -> Optional[T]:
        """Get a service by interface."""
        return self._container.resolve(interface)
    
    def get_required_service(self, interface: Type[T]) -> T:
        """Get a required service by interface."""
        return self._container.resolve_required(interface)
    
    def get_services(self, interface: Type[T]) -> list[T]:
        """Get all services implementing an interface."""
        # This would require multiple registration support
        # For now, return single service or empty list
        service = self._container.resolve(interface)
        return [service] if service else []


def create_service_provider() -> ServiceProvider:
    """Create a new service provider."""
    return ServiceProvider(get_container())
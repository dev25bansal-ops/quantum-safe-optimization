"""
Centralized configuration management module.

Provides a unified configuration system with environment variable support,
validation, and type safety for all application settings.
"""

import os
import logging
from typing import Any, Dict, Optional, Type, TypeVar, get_type_hints
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

T = TypeVar('T')


class Environment(str, Enum):
    """Application environment types."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class LogLevel(str, Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class DatabaseConfig:
    """Database configuration."""
    
    # Cosmos DB
    cosmos_endpoint: str = "https://localhost:8081"
    cosmos_key: str = "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="
    cosmos_database: str = "quantum_optimization"
    use_managed_identity: bool = False
    
    # Connection pooling
    db_min_connections: int = 2
    db_max_connections: int = 20
    db_connection_timeout: float = 30.0
    db_max_idle_time: float = 600.0
    
    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Create configuration from environment variables."""
        return cls(
            cosmos_endpoint=os.getenv("COSMOS_ENDPOINT", cls.cosmos_endpoint),
            cosmos_key=os.getenv("COSMOS_KEY", cls.cosmos_key),
            cosmos_database=os.getenv("COSMOS_DATABASE", cls.cosmos_database),
            use_managed_identity=os.getenv("USE_MANAGED_IDENTITY", "false").lower() == "true",
            db_min_connections=int(os.getenv("DB_MIN_CONNECTIONS", str(cls.db_min_connections))),
            db_max_connections=int(os.getenv("DB_MAX_CONNECTIONS", str(cls.db_max_connections))),
            db_connection_timeout=float(os.getenv("DB_CONNECTION_TIMEOUT", str(cls.db_connection_timeout))),
            db_max_idle_time=float(os.getenv("DB_MAX_IDLE_TIME", str(cls.db_max_idle_time))),
        )


@dataclass
class RedisConfig:
    """Redis configuration."""
    
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 10
    redis_socket_timeout: float = 5.0
    redis_socket_connect_timeout: float = 5.0
    
    @classmethod
    def from_env(cls) -> "RedisConfig":
        """Create configuration from environment variables."""
        return cls(
            redis_url=os.getenv("REDIS_URL", cls.redis_url),
            redis_max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", str(cls.redis_max_connections))),
            redis_socket_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT", str(cls.redis_socket_timeout))),
            redis_socket_connect_timeout=float(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", str(cls.redis_socket_connect_timeout))),
        )


@dataclass
class SecurityConfig:
    """Security configuration."""
    
    # JWT
    jwt_secret: str = "your-super-secret-jwt-key-change-in-production"
    access_token_expire: int = 3600
    refresh_token_expire: int = 604800
    
    # PQC
    pqc_key_path: str = "./keys"
    pqc_key_max_age_days: int = 90
    pqc_key_rotate_before_days: int = 7
    enable_pqc_encryption: bool = True
    
    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60
    
    # Security features
    enable_request_signing: bool = False
    enable_audit_logging: bool = True
    enable_csrf_protection: bool = True
    
    @classmethod
    def from_env(cls) -> "SecurityConfig":
        """Create configuration from environment variables."""
        return cls(
            jwt_secret=os.getenv("JWT_SECRET", cls.jwt_secret),
            access_token_expire=int(os.getenv("ACCESS_TOKEN_EXPIRE", str(cls.access_token_expire))),
            refresh_token_expire=int(os.getenv("REFRESH_TOKEN_EXPIRE", str(cls.refresh_token_expire))),
            pqc_key_path=os.getenv("PQC_KEY_PATH", cls.pqc_key_path),
            pqc_key_max_age_days=int(os.getenv("PQC_KEY_MAX_AGE_DAYS", str(cls.pqc_key_max_age_days))),
            pqc_key_rotate_before_days=int(os.getenv("PQC_KEY_ROTATE_BEFORE_DAYS", str(cls.pqc_key_rotate_before_days))),
            enable_pqc_encryption=os.getenv("ENABLE_PQC_ENCRYPTION", "true").lower() == "true",
            rate_limit_requests=int(os.getenv("RATE_LIMIT_REQUESTS", str(cls.rate_limit_requests))),
            rate_limit_window=int(os.getenv("RATE_LIMIT_WINDOW", str(cls.rate_limit_window))),
            enable_request_signing=os.getenv("ENABLE_REQUEST_SIGNING", "false").lower() == "true",
            enable_audit_logging=os.getenv("ENABLE_AUDIT_LOGGING", "true").lower() == "true",
            enable_csrf_protection=os.getenv("ENABLE_CSRF_PROTECTION", "true").lower() == "true",
        )


@dataclass
class QuantumConfig:
    """Quantum backend configuration."""
    
    # IBM Quantum
    ibm_quantum_token: Optional[str] = None
    ibm_quantum_instance: str = "ibm-q/open/main"
    
    # AWS Braket
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    aws_braket_s3_bucket: Optional[str] = None
    
    # Azure Quantum
    azure_quantum_subscription_id: Optional[str] = None
    azure_quantum_resource_group: Optional[str] = None
    azure_quantum_workspace: Optional[str] = None
    azure_quantum_location: str = "eastus"
    
    # D-Wave
    dwave_api_token: Optional[str] = None
    dwave_solver: str = "Advantage_system6.4"
    
    # Feature flags
    enable_quantum_backends: bool = True
    
    @classmethod
    def from_env(cls) -> "QuantumConfig":
        """Create configuration from environment variables."""
        return cls(
            ibm_quantum_token=os.getenv("IBM_QUANTUM_TOKEN"),
            ibm_quantum_instance=os.getenv("IBM_QUANTUM_INSTANCE", cls.ibm_quantum_instance),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_region=os.getenv("AWS_REGION", cls.aws_region),
            aws_braket_s3_bucket=os.getenv("AWS_BRAKET_S3_BUCKET"),
            azure_quantum_subscription_id=os.getenv("AZURE_QUANTUM_SUBSCRIPTION_ID"),
            azure_quantum_resource_group=os.getenv("AZURE_QUANTUM_RESOURCE_GROUP"),
            azure_quantum_workspace=os.getenv("AZURE_QUANTUM_WORKSPACE"),
            azure_quantum_location=os.getenv("AZURE_QUANTUM_LOCATION", cls.azure_quantum_location),
            dwave_api_token=os.getenv("DWAVE_API_TOKEN"),
            dwave_solver=os.getenv("DWAVE_SOLVER", cls.dwave_solver),
            enable_quantum_backends=os.getenv("ENABLE_QUANTUM_BACKENDS", "true").lower() == "true",
        )


@dataclass
class APIConfig:
    """API server configuration."""
    
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    cors_origins: str = "http://localhost:3000,http://localhost:8080"
    
    @classmethod
    def from_env(cls) -> "APIConfig":
        """Create configuration from environment variables."""
        return cls(
            api_host=os.getenv("API_HOST", cls.api_host),
            api_port=int(os.getenv("API_PORT", str(cls.api_port))),
            api_workers=int(os.getenv("API_WORKERS", str(cls.api_workers))),
            cors_origins=os.getenv("CORS_ORIGINS", cls.cors_origins),
        )


@dataclass
class MonitoringConfig:
    """Monitoring and observability configuration."""
    
    # OpenTelemetry
    otlp_enabled: bool = False
    otlp_endpoint: str = "http://localhost:4317"
    otlp_service_name: str = "quantum-optimization-api"
    otlp_service_version: str = "0.1.0"
    otlp_sample_rate: float = 1.0
    otlp_console_export: bool = False
    
    # Application Insights
    appinsights_connection_string: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "MonitoringConfig":
        """Create configuration from environment variables."""
        return cls(
            otlp_enabled=os.getenv("OTEL_ENABLED", "false").lower() == "true",
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", cls.otlp_endpoint),
            otlp_service_name=os.getenv("OTEL_SERVICE_NAME", cls.otlp_service_name),
            otlp_service_version=os.getenv("OTEL_SERVICE_VERSION", cls.otlp_service_version),
            otlp_sample_rate=float(os.getenv("OTEL_TRACES_SAMPLER_ARG", str(cls.otlp_sample_rate))),
            otlp_console_export=os.getenv("OTEL_CONSOLE_EXPORT", "false").lower() == "true",
            appinsights_connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"),
        )


@dataclass
class AppConfig:
    """Main application configuration."""
    
    # Environment
    app_env: Environment = Environment.DEVELOPMENT
    log_level: LogLevel = LogLevel.INFO
    debug: bool = False
    
    # Sub-configurations
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    quantum: QuantumConfig = field(default_factory=QuantumConfig)
    api: APIConfig = field(default_factory=APIConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    
    # Feature flags
    use_celery: bool = False
    demo_mode: bool = False
    
    @classmethod
    def from_env(cls) -> "AppConfig":
        """Create configuration from environment variables."""
        env_str = os.getenv("APP_ENV", "development").lower()
        try:
            app_env = Environment(env_str)
        except ValueError:
            logger.warning(f"Invalid APP_ENV: {env_str}, using development")
            app_env = Environment.DEVELOPMENT
        
        log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
        try:
            log_level = LogLevel(log_level_str)
        except ValueError:
            logger.warning(f"Invalid LOG_LEVEL: {log_level_str}, using INFO")
            log_level = LogLevel.INFO
        
        is_production = app_env == Environment.PRODUCTION
        
        return cls(
            app_env=app_env,
            log_level=log_level,
            debug=os.getenv("DEBUG", "false").lower() == "true",
            database=DatabaseConfig.from_env(),
            redis=RedisConfig.from_env(),
            security=SecurityConfig.from_env(),
            quantum=QuantumConfig.from_env(),
            api=APIConfig.from_env(),
            monitoring=MonitoringConfig.from_env(),
            use_celery=os.getenv("USE_CELERY", "true" if is_production else "false").lower() == "true",
            demo_mode=os.getenv("DEMO_MODE", "false").lower() == "true",
        )
    
    def validate(self) -> None:
        """Validate configuration settings."""
        # Validate production settings
        if self.app_env == Environment.PRODUCTION:
            if self.debug:
                logger.warning("DEBUG should not be enabled in production")
            
            if self.security.jwt_secret == "your-super-secret-jwt-key-change-in-production":
                logger.critical("SECURITY: JWT_SECRET must be changed in production")
            
            if not self.use_celery:
                logger.warning("USE_CELERY should be enabled in production")
        
        # Validate database settings
        if self.database.db_min_connections > self.database.db_max_connections:
            raise ValueError("DB_MIN_CONNECTIONS cannot be greater than DB_MAX_CONNECTIONS")
        
        # Validate security settings
        if self.security.rate_limit_requests <= 0:
            raise ValueError("RATE_LIMIT_REQUESTS must be positive")
        
        if self.security.rate_limit_window <= 0:
            raise ValueError("RATE_LIMIT_WINDOW must be positive")
        
        # Validate API settings
        if self.api.api_port < 1 or self.api.api_port > 65535:
            raise ValueError("API_PORT must be between 1 and 65535")
        
        logger.info("Configuration validated successfully")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary (excluding secrets)."""
        return {
            "app_env": self.app_env.value,
            "log_level": self.log_level.value,
            "debug": self.debug,
            "database": {
                "cosmos_endpoint": self.database.cosmos_endpoint,
                "cosmos_database": self.database.cosmos_database,
                "use_managed_identity": self.database.use_managed_identity,
                "db_min_connections": self.database.db_min_connections,
                "db_max_connections": self.database.db_max_connections,
            },
            "redis": {
                "redis_url": self.database.cosmos_endpoint,  # Don't expose full URL
                "redis_max_connections": self.redis.redis_max_connections,
            },
            "security": {
                "access_token_expire": self.security.access_token_expire,
                "refresh_token_expire": self.security.refresh_token_expire,
                "enable_pqc_encryption": self.security.enable_pqc_encryption,
                "rate_limit_requests": self.security.rate_limit_requests,
                "rate_limit_window": self.security.rate_limit_window,
                "enable_request_signing": self.security.enable_request_signing,
                "enable_audit_logging": self.security.enable_audit_logging,
            },
            "quantum": {
                "ibm_quantum_instance": self.quantum.ibm_quantum_instance,
                "aws_region": self.quantum.aws_region,
                "azure_quantum_location": self.quantum.azure_quantum_location,
                "dwave_solver": self.quantum.dwave_solver,
                "enable_quantum_backends": self.quantum.enable_quantum_backends,
            },
            "api": {
                "api_host": self.api.api_host,
                "api_port": self.api.api_port,
                "api_workers": self.api.api_workers,
                "cors_origins": self.api.cors_origins,
            },
            "monitoring": {
                "otlp_enabled": self.monitoring.otlp_enabled,
                "otlp_endpoint": self.monitoring.otlp_endpoint,
                "otlp_service_name": self.monitoring.otlp_service_name,
            },
            "use_celery": self.use_celery,
            "demo_mode": self.demo_mode,
        }


# Global configuration instance
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get the global application configuration."""
    global _config
    if _config is None:
        _config = AppConfig.from_env()
        _config.validate()
    return _config


def set_config(config: AppConfig) -> None:
    """Set the global application configuration."""
    global _config
    config.validate()
    _config = config


def reload_config() -> AppConfig:
    """Reload configuration from environment variables."""
    global _config
    _config = AppConfig.from_env()
    _config.validate()
    logger.info("Configuration reloaded")
    return _config


def load_config_from_file(file_path: str) -> AppConfig:
    """Load configuration from a file (e.g., .env)."""
    from dotenv import load_dotenv
    
    load_dotenv(file_path)
    return reload_config()


def is_production() -> bool:
    """Check if running in production environment."""
    return get_config().app_env == Environment.PRODUCTION


def is_development() -> bool:
    """Check if running in development environment."""
    return get_config().app_env == Environment.DEVELOPMENT


def is_test() -> bool:
    """Check if running in test environment."""
    return get_config().app_env == Environment.TEST


def get_log_level() -> str:
    """Get the current log level."""
    return get_config().log_level.value
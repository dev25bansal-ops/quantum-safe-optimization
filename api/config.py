"""
Centralized Configuration Management.

Features:
- Environment-specific settings (dev, staging, prod)
- Validation with Pydantic
- Singleton pattern for app-wide access
- Integration with Azure Key Vault
"""

from enum import Enum
from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings


class Environment(str, Enum):
    """Application environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class LogLevel(str, Enum):
    """Logging level."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DatabaseSettings(BaseSettings):
    """Cosmos DB configuration."""

    endpoint: str = Field(
        default="https://localhost:8081",
        alias="COSMOS_ENDPOINT",
        description="Cosmos DB endpoint URL",
    )
    key: str | None = Field(
        default=None,
        alias="COSMOS_KEY",
        description="Cosmos DB primary key (for local development)",
    )
    database: str = Field(
        default="quantum_optimization",
        alias="COSMOS_DATABASE",
        description="Database name",
    )
    use_managed_identity: bool = Field(
        default=False,
        alias="USE_MANAGED_IDENTITY",
        description="Use Azure Managed Identity for auth",
    )

    # Connection pool settings
    max_connections: int = Field(default=100, ge=10, le=1000)
    max_connections_per_host: int = Field(default=30, ge=5, le=100)
    connection_timeout_seconds: int = Field(default=30, ge=5, le=120)
    read_timeout_seconds: int = Field(default=60, ge=10, le=300)

    class Config:
        env_prefix = ""
        extra = "ignore"


class RedisSettings(BaseSettings):
    """Redis configuration."""

    url: str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
        description="Redis connection URL",
    )
    password: str | None = Field(
        default=None,
        alias="REDIS_PASSWORD",
        description="Redis password (if required)",
    )
    ssl: bool = Field(
        default=False,
        alias="REDIS_SSL",
        description="Use SSL for Redis connection",
    )
    max_connections: int = Field(default=50, ge=5, le=500)

    class Config:
        env_prefix = ""
        extra = "ignore"


class SecuritySettings(BaseSettings):
    """Security configuration."""

    jwt_secret: str = Field(
        default="development-secret-change-in-production",
        alias="JWT_SECRET",
        description="JWT signing secret",
    )
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(
        default=60,
        alias="ACCESS_TOKEN_EXPIRE",
        ge=5,
        le=1440,
    )
    refresh_token_expire_days: int = Field(
        default=7,
        alias="REFRESH_TOKEN_EXPIRE",
        ge=1,
        le=30,
    )

    # Key Vault
    key_vault_uri: str | None = Field(
        default=None,
        alias="KEY_VAULT_URI",
        description="Azure Key Vault URI",
    )

    # Rate limiting
    rate_limit_requests: int = Field(
        default=100,
        alias="RATE_LIMIT_REQUESTS",
        ge=10,
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        alias="RATE_LIMIT_WINDOW",
        ge=10,
    )

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
    )

    class Config:
        env_prefix = ""
        extra = "ignore"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


class TelemetrySettings(BaseSettings):
    """Observability configuration."""

    enabled: bool = Field(
        default=True,
        alias="OTEL_ENABLED",
        description="Enable OpenTelemetry",
    )
    service_name: str = Field(
        default="quantum-api",
        alias="OTEL_SERVICE_NAME",
    )
    otlp_endpoint: str | None = Field(
        default=None,
        alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )
    sample_rate: float = Field(
        default=1.0,
        alias="OTEL_TRACES_SAMPLER_ARG",
        ge=0.0,
        le=1.0,
    )
    console_export: bool = Field(
        default=False,
        alias="OTEL_CONSOLE_EXPORT",
    )

    # Application Insights (Azure)
    app_insights_connection: str | None = Field(
        default=None,
        alias="APPLICATIONINSIGHTS_CONNECTION_STRING",
    )

    class Config:
        env_prefix = ""
        extra = "ignore"


class QuantumBackendSettings(BaseSettings):
    """Quantum computing backend configuration."""

    # IBM Quantum
    ibm_token: str | None = Field(
        default=None,
        alias="IBM_QUANTUM_TOKEN",
    )
    ibm_instance: str = Field(
        default="ibm-q/open/main",
        alias="IBM_QUANTUM_INSTANCE",
    )

    # AWS Braket
    aws_access_key: str | None = Field(
        default=None,
        alias="AWS_ACCESS_KEY_ID",
    )
    aws_secret_key: str | None = Field(
        default=None,
        alias="AWS_SECRET_ACCESS_KEY",
    )
    aws_region: str = Field(
        default="us-east-1",
        alias="AWS_REGION",
    )
    aws_braket_bucket: str | None = Field(
        default=None,
        alias="AWS_BRAKET_S3_BUCKET",
    )

    # Azure Quantum
    azure_subscription_id: str | None = Field(
        default=None,
        alias="AZURE_QUANTUM_SUBSCRIPTION_ID",
    )
    azure_resource_group: str | None = Field(
        default=None,
        alias="AZURE_QUANTUM_RESOURCE_GROUP",
    )
    azure_workspace: str | None = Field(
        default=None,
        alias="AZURE_QUANTUM_WORKSPACE",
    )

    # D-Wave
    dwave_token: str | None = Field(
        default=None,
        alias="DWAVE_API_TOKEN",
    )
    dwave_solver: str = Field(
        default="Advantage_system6.4",
        alias="DWAVE_SOLVER",
    )

    class Config:
        env_prefix = ""
        extra = "ignore"


class FeatureFlags(BaseSettings):
    """Feature flag configuration."""

    enable_quantum_backends: bool = Field(
        default=True,
        alias="ENABLE_QUANTUM_BACKENDS",
    )
    enable_pqc_encryption: bool = Field(
        default=True,
        alias="ENABLE_PQC_ENCRYPTION",
    )
    enable_audit_logging: bool = Field(
        default=True,
        alias="ENABLE_AUDIT_LOGGING",
    )
    enable_websocket: bool = Field(
        default=True,
        alias="ENABLE_WEBSOCKET",
    )
    enable_rate_limiting: bool = Field(
        default=True,
        alias="ENABLE_RATE_LIMITING",
    )

    class Config:
        env_prefix = ""
        extra = "ignore"


class AppSettings(BaseSettings):
    """Main application settings."""

    # Core settings
    name: str = Field(default="Quantum-Safe Optimization Platform")
    version: str = Field(default="0.1.0", alias="APP_VERSION")
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        alias="APP_ENV",
    )
    debug: bool = Field(default=False, alias="DEBUG")

    # Server settings
    host: str = Field(default="0.0.0.0", alias="API_HOST")
    port: int = Field(default=8000, alias="API_PORT", ge=1, le=65535)
    workers: int = Field(default=4, alias="API_WORKERS", ge=1, le=32)

    # Logging
    log_level: LogLevel = Field(default=LogLevel.INFO, alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")

    # Nested settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    telemetry: TelemetrySettings = Field(default_factory=TelemetrySettings)
    quantum: QuantumBackendSettings = Field(default_factory=QuantumBackendSettings)
    features: FeatureFlags = Field(default_factory=FeatureFlags)

    class Config:
        env_prefix = ""
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @model_validator(mode="after")
    def validate_production_settings(self):
        """Validate settings for production environment."""
        if self.environment == Environment.PRODUCTION:
            # Require Key Vault in production
            if not self.security.key_vault_uri:
                import warnings

                warnings.warn(
                    "KEY_VAULT_URI not set in production - using local secrets", stacklevel=2
                )

            # Require managed identity or strong JWT secret
            if (
                not self.database.use_managed_identity
                and self.security.jwt_secret == "development-secret-change-in-production"
            ):
                raise ValueError("Must change JWT_SECRET from default in production")

            # Enforce HTTPS origins
            for origin in self.security.cors_origins:
                if origin.startswith("http://") and "localhost" not in origin:
                    import warnings

                    warnings.warn(f"Non-HTTPS origin in production: {origin}", stacklevel=2)

        return self

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == Environment.DEVELOPMENT

    def get_available_quantum_backends(self) -> list[str]:
        """Get list of configured quantum backends."""
        backends = ["local_simulator"]  # Always available

        if self.features.enable_quantum_backends:
            if self.quantum.ibm_token:
                backends.append("ibm_quantum")
            if self.quantum.dwave_token:
                backends.append("dwave")
            if self.quantum.aws_access_key and self.quantum.aws_secret_key:
                backends.append("aws_braket")
            if self.quantum.azure_subscription_id:
                backends.append("azure_quantum")

        return backends


@lru_cache
def get_settings() -> AppSettings:
    """
    Get application settings (cached singleton).

    Usage:
        from api.config import get_settings
        settings = get_settings()

        print(settings.database.endpoint)
        print(settings.security.jwt_secret)
    """
    return AppSettings()


def reload_settings() -> AppSettings:
    """Reload settings (clears cache)."""
    get_settings.cache_clear()
    return get_settings()

"""Application settings using Pydantic Settings."""

from enum import Enum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class LogFormat(str, Enum):
    JSON = "json"
    CONSOLE = "console"


class PQCKemAlgorithm(str, Enum):
    KYBER512 = "Kyber512"
    KYBER768 = "Kyber768"
    KYBER1024 = "Kyber1024"


class PQCSigAlgorithm(str, Enum):
    DILITHIUM2 = "Dilithium2"
    DILITHIUM3 = "Dilithium3"
    DILITHIUM5 = "Dilithium5"


class QuantumBackend(str, Enum):
    AER_SIMULATOR = "aer_simulator"
    STATEVECTOR = "statevector_simulator"
    QASM = "qasm_simulator"
    IBM_QUANTUM = "ibm_quantum"


class APISettings(BaseSettings):
    """API server configuration."""

    model_config = SettingsConfigDict(env_prefix="QSOP_API_")

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    reload: bool = False
    title: str = "Quantum-Safe Secure Optimization Platform"
    version: str = "0.1.0"


class CORSSettings(BaseSettings):
    """CORS configuration."""

    model_config = SettingsConfigDict(env_prefix="QSOP_CORS_")

    origins: list[str] = ["http://localhost:3000"]
    allow_credentials: bool = True
    allow_methods: list[str] = ["*"]
    allow_headers: list[str] = ["*"]

    @field_validator("origins", mode="before")
    @classmethod
    def parse_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


class CryptoSettings(BaseSettings):
    """Cryptography configuration."""

    model_config = SettingsConfigDict(env_prefix="QSOP_PQC_")

    kem_algorithm: PQCKemAlgorithm = PQCKemAlgorithm.KYBER512
    sig_algorithm: PQCSigAlgorithm = PQCSigAlgorithm.DILITHIUM2
    hybrid_mode: bool = True


class ClassicalCryptoSettings(BaseSettings):
    """Classical cryptography fallback settings."""

    model_config = SettingsConfigDict(env_prefix="QSOP_CLASSICAL_")

    algorithm: str = "AES-256-GCM"


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(env_prefix="QSOP_DATABASE_")

    url: str = "sqlite+aiosqlite:///./data/qsop.db"
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = False


class RedisSettings(BaseSettings):
    """Redis configuration."""

    model_config = SettingsConfigDict(env_prefix="QSOP_REDIS_")

    url: str = "redis://localhost:6379/0"
    password: SecretStr | None = None
    ssl: bool = False
    pool_size: int = 10


class CacheSettings(BaseSettings):
    """Cache configuration."""

    model_config = SettingsConfigDict(env_prefix="QSOP_CACHE_")

    ttl: int = 3600
    prefix: str = "qsop:"


class QuantumSettings(BaseSettings):
    """Quantum backend configuration."""

    model_config = SettingsConfigDict(env_prefix="QSOP_QUANTUM_")

    backend: QuantumBackend = QuantumBackend.AER_SIMULATOR
    shots: int = 1024
    optimization_level: int = 3


class IBMQuantumSettings(BaseSettings):
    """IBM Quantum configuration."""

    model_config = SettingsConfigDict(env_prefix="QSOP_IBM_QUANTUM_")

    token: SecretStr | None = None
    hub: str = "ibm-q"
    group: str = "open"
    project: str = "main"


class OptimizerSettings(BaseSettings):
    """Optimization algorithm settings."""

    model_config = SettingsConfigDict(env_prefix="QSOP_OPTIMIZER_")

    max_iterations: int = 1000
    convergence_threshold: float = 1e-6
    timeout: int = 300


class OTELSettings(BaseSettings):
    """OpenTelemetry configuration."""

    model_config = SettingsConfigDict(env_prefix="QSOP_OTEL_")

    enabled: bool = True
    service_name: str = "qsop"
    exporter_endpoint: str = "http://localhost:4317"


class MetricsSettings(BaseSettings):
    """Prometheus metrics configuration."""

    model_config = SettingsConfigDict(env_prefix="QSOP_METRICS_")

    enabled: bool = True
    path: str = "/metrics"


class RateLimitSettings(BaseSettings):
    """Rate limiting configuration."""

    model_config = SettingsConfigDict(env_prefix="QSOP_RATE_LIMIT_")

    requests: int = 100
    window: int = 60


class HTTPClientSettings(BaseSettings):
    """HTTP client configuration."""

    model_config = SettingsConfigDict(env_prefix="QSOP_HTTP_")

    timeout: int = 30
    max_retries: int = 3
    retry_backoff: float = 1.0


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_prefix="QSOP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Environment = Environment.DEV
    debug: bool = False
    log_level: str = "INFO"
    log_format: LogFormat = LogFormat.JSON
    log_include_trace_id: bool = True
    secret_key: Annotated[SecretStr, Field(min_length=32)]
    health_check_timeout: int = 5

    api: APISettings = APISettings()
    cors: CORSSettings = CORSSettings()
    crypto: CryptoSettings = CryptoSettings()
    classical_crypto: ClassicalCryptoSettings = ClassicalCryptoSettings()
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    cache: CacheSettings = CacheSettings()
    quantum: QuantumSettings = QuantumSettings()
    ibm_quantum: IBMQuantumSettings = IBMQuantumSettings()
    optimizer: OptimizerSettings = OptimizerSettings()
    otel: OTELSettings = OTELSettings()
    metrics: MetricsSettings = MetricsSettings()
    rate_limit: RateLimitSettings = RateLimitSettings()
    http_client: HTTPClientSettings = HTTPClientSettings()

    @property
    def is_production(self) -> bool:
        return self.env == Environment.PROD

    @property
    def is_development(self) -> bool:
        return self.env == Environment.DEV


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

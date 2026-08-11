"""Validated process configuration for Gateway application bootstrap."""

from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

from pydantic import (
    AnyUrl,
    Field,
    SecretStr,
    TypeAdapter,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProcessName(StrEnum):
    """Supported Gateway process identities."""

    GATEWAY_API = "gateway-api"
    USAGE_WORKER = "usage-worker"
    WS_USAGE_GATEWAY = "ws-usage-gateway"


class RuntimeEnvironment(StrEnum):
    """Supported runtime environments."""

    LOCAL = "local"
    TEST = "test"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """Supported logging severity thresholds."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(StrEnum):
    """Supported logging output formats."""

    TEXT = "text"
    JSON = "json"


class StorageBackend(StrEnum):
    """Supported storage configuration placeholders."""

    LOCAL = "local"


_LOCAL_INFRASTRUCTURE_DEFAULTS: dict[str, str | Path] = {
    "database_url": (
        "postgresql+psycopg://gateway_local:gateway_local@localhost:5432/gateway"
    ),
    "redis_url": "redis://localhost:6379/0",
    "celery_broker_url": "redis://localhost:6379/1",
    "storage_root": Path(".local/storage"),
}
_URL_ADAPTER = TypeAdapter(AnyUrl)
_DATABASE_SCHEMES = frozenset({"postgresql", "postgresql+psycopg"})
_REDIS_SCHEMES = frozenset({"redis", "rediss"})
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _parse_url(value: SecretStr, *, field_name: str, schemes: frozenset[str]) -> AnyUrl:
    parsed = _URL_ADAPTER.validate_python(value.get_secret_value())
    if parsed.scheme not in schemes:
        allowed = ", ".join(sorted(f"{scheme}://" for scheme in schemes))
        raise ValueError(f"{field_name} must use one of: {allowed}")
    if parsed.host is None:
        raise ValueError(f"{field_name} must include a host")
    return parsed


def _is_loopback_host(host: str) -> bool:
    return host.removeprefix("[").removesuffix("]").lower() in _LOOPBACK_HOSTS


class Settings(BaseSettings):
    """Single authoritative, immutable Gateway settings contract."""

    model_config = SettingsConfigDict(
        env_prefix="GATEWAY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        validate_default=True,
        hide_input_in_errors=True,
        frozen=True,
    )

    process_name: ProcessName = ProcessName.GATEWAY_API
    environment: RuntimeEnvironment = RuntimeEnvironment.LOCAL
    log_level: LogLevel = LogLevel.INFO
    log_format: LogFormat = LogFormat.TEXT
    database_url: SecretStr
    redis_url: SecretStr
    celery_broker_url: SecretStr
    worker_queue_name: str = Field(
        default="gateway-usage",
        pattern=r"^[a-z0-9][a-z0-9._-]{0,62}$",
    )
    worker_concurrency: int = Field(default=2, ge=1, le=32)
    storage_backend: StorageBackend = StorageBackend.LOCAL
    storage_root: Path

    @model_validator(mode="before")
    @classmethod
    def apply_nonproduction_defaults(cls, values: Any) -> Any:
        """Add local defaults only when merged configuration did not supply them."""
        if not isinstance(values, Mapping):
            return values

        data = dict(values)
        environment = data.get("environment", RuntimeEnvironment.LOCAL)
        environment_value = (
            environment.value
            if isinstance(environment, RuntimeEnvironment)
            else str(environment)
        )
        if environment_value != RuntimeEnvironment.PRODUCTION:
            for field_name, default in _LOCAL_INFRASTRUCTURE_DEFAULTS.items():
                data.setdefault(field_name, default)
        return data

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        """Validate the configured PostgreSQL URL without exposing credentials."""
        parsed = _parse_url(
            value,
            field_name="database_url",
            schemes=_DATABASE_SCHEMES,
        )
        if parsed.path in {None, "", "/"}:
            raise ValueError("database_url must include a database name")
        return value

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, value: SecretStr) -> SecretStr:
        """Validate the Redis startup URL without exposing credentials."""
        _parse_url(value, field_name="redis_url", schemes=_REDIS_SCHEMES)
        return value

    @field_validator("celery_broker_url")
    @classmethod
    def validate_celery_broker_url(cls, value: SecretStr) -> SecretStr:
        """Validate the Redis-backed broker URL without exposing credentials."""
        _parse_url(value, field_name="celery_broker_url", schemes=_REDIS_SCHEMES)
        return value

    @model_validator(mode="after")
    def validate_production_policy(self) -> Self:
        """Apply production policy after every field is independently valid."""
        if self.environment is not RuntimeEnvironment.PRODUCTION:
            return self

        configured_urls = (
            ("database_url", self.database_url, _DATABASE_SCHEMES),
            ("redis_url", self.redis_url, _REDIS_SCHEMES),
            ("celery_broker_url", self.celery_broker_url, _REDIS_SCHEMES),
        )
        for field_name, value, schemes in configured_urls:
            parsed = _parse_url(value, field_name=field_name, schemes=schemes)
            if parsed.host is not None and _is_loopback_host(parsed.host):
                raise ValueError(
                    f"{field_name} cannot use a loopback host in production"
                )

        if not self.storage_root.is_absolute():
            raise ValueError("storage_root must be absolute in production")
        return self

"""Tests for authoritative Aegis process configuration."""

import socket
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from aegis.config import (
    LogFormat,
    LogLevel,
    ProcessName,
    RuntimeEnvironment,
    Settings,
    StorageBackend,
)


PRODUCTION_VALUES: dict[str, object] = {
    "environment": "production",
    "database_url": "postgresql+psycopg://user:database-canary@db.internal/aegis",
    "redis_url": "rediss://user:redis-canary@redis.internal/0",
    "celery_broker_url": "rediss://user:broker-canary@broker.internal/1",
    "storage_root": "/var/lib/aegis/storage",
}
KNOWN_ENVIRONMENT_VARIABLES = (
    "AEGIS_PROCESS_NAME",
    "AEGIS_ENVIRONMENT",
    "AEGIS_LOG_LEVEL",
    "AEGIS_LOG_FORMAT",
    "AEGIS_DATABASE_URL",
    "AEGIS_REDIS_URL",
    "AEGIS_CELERY_BROKER_URL",
    "AEGIS_WORKER_QUEUE_NAME",
    "AEGIS_WORKER_CONCURRENCY",
    "AEGIS_STORAGE_BACKEND",
    "AEGIS_STORAGE_ROOT",
)


@pytest.fixture(autouse=True)
def isolate_settings_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in KNOWN_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(variable, raising=False)


def make_settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_safe_local_defaults() -> None:
    settings = make_settings()

    assert settings.process_name is ProcessName.GATEWAY_API
    assert settings.environment is RuntimeEnvironment.LOCAL
    assert settings.log_level is LogLevel.INFO
    assert settings.log_format is LogFormat.TEXT
    assert settings.database_url.get_secret_value().startswith(
        "postgresql+psycopg://aegis_local:"
    )
    assert settings.redis_url.get_secret_value() == "redis://localhost:6379/0"
    assert settings.celery_broker_url.get_secret_value() == (
        "redis://localhost:6379/1"
    )
    assert settings.worker_queue_name == "aegis-usage"
    assert settings.worker_concurrency == 2
    assert settings.storage_backend is StorageBackend.LOCAL
    assert settings.storage_root == Path(".local/storage")


def test_safe_test_defaults() -> None:
    settings = make_settings(environment="test")

    assert settings.environment is RuntimeEnvironment.TEST
    assert settings.storage_root == Path(".local/storage")


def test_explicit_environment_overrides_are_typed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AEGIS_PROCESS_NAME", "usage-worker")
    monkeypatch.setenv("AEGIS_ENVIRONMENT", "test")
    monkeypatch.setenv("AEGIS_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("AEGIS_LOG_FORMAT", "json")
    monkeypatch.setenv("AEGIS_DATABASE_URL", "postgresql://user:pass@db/aegis")
    monkeypatch.setenv("AEGIS_REDIS_URL", "rediss://user:pass@redis/0")
    monkeypatch.setenv("AEGIS_CELERY_BROKER_URL", "redis://broker/1")
    monkeypatch.setenv("AEGIS_WORKER_QUEUE_NAME", "usage.events")
    monkeypatch.setenv("AEGIS_WORKER_CONCURRENCY", "4")
    monkeypatch.setenv("AEGIS_STORAGE_BACKEND", "local")
    monkeypatch.setenv("AEGIS_STORAGE_ROOT", "/tmp/aegis-test-storage")

    settings = Settings(_env_file=None)

    assert settings.process_name is ProcessName.USAGE_WORKER
    assert settings.environment is RuntimeEnvironment.TEST
    assert settings.log_level is LogLevel.DEBUG
    assert settings.log_format is LogFormat.JSON
    assert isinstance(settings.database_url, SecretStr)
    assert settings.worker_concurrency == 4
    assert settings.storage_root == Path("/tmp/aegis-test-storage")


@pytest.mark.parametrize("environment", ("local", "test", "production"))
def test_supported_environments(environment: str) -> None:
    values = dict(PRODUCTION_VALUES) if environment == "production" else {}
    values["environment"] = environment

    assert make_settings(**values).environment.value == environment


def test_invalid_environment_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_settings(environment="staging")


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("process_name", "scheduler"),
        ("log_level", "TRACE"),
        ("log_format", "yaml"),
        ("storage_backend", "s3"),
        ("worker_queue_name", "Invalid Queue"),
        ("worker_concurrency", 0),
        ("worker_concurrency", 33),
    ),
)
def test_invalid_scalar_values_are_rejected(field_name: str, value: object) -> None:
    with pytest.raises(ValidationError):
        make_settings(**{field_name: value})


@pytest.mark.parametrize(
    "missing_field",
    ("database_url", "redis_url", "celery_broker_url", "storage_root"),
)
def test_production_requires_each_infrastructure_value(missing_field: str) -> None:
    values = dict(PRODUCTION_VALUES)
    del values[missing_field]

    with pytest.raises(ValidationError) as error:
        make_settings(**values)

    assert (missing_field,) in {item["loc"] for item in error.value.errors()}


def test_production_succeeds_when_all_required_values_are_explicit() -> None:
    settings = make_settings(**PRODUCTION_VALUES)

    assert settings.environment is RuntimeEnvironment.PRODUCTION


def test_production_values_can_be_supplied_entirely_by_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AEGIS_ENVIRONMENT", "production")
    monkeypatch.setenv(
        "AEGIS_DATABASE_URL",
        "postgresql+psycopg://user:pass@db.internal/aegis",
    )
    monkeypatch.setenv("AEGIS_REDIS_URL", "rediss://user:pass@redis.internal/0")
    monkeypatch.setenv(
        "AEGIS_CELERY_BROKER_URL",
        "rediss://user:pass@broker.internal/1",
    )
    monkeypatch.setenv("AEGIS_STORAGE_ROOT", "/var/lib/aegis/storage")

    settings = Settings(_env_file=None)

    assert settings.environment is RuntimeEnvironment.PRODUCTION
    assert settings.storage_root == Path("/var/lib/aegis/storage")


@pytest.mark.parametrize(
    "database_url",
    (
        "postgresql://user:pass@db.internal/aegis",
        "postgresql+psycopg://user:pass@db.internal/aegis",
    ),
)
def test_accepted_database_schemes(database_url: str) -> None:
    assert make_settings(database_url=database_url).database_url.get_secret_value() == (
        database_url
    )


@pytest.mark.parametrize(
    "database_url",
    (
        "mysql://user:pass@db.internal/aegis",
        "postgresql+asyncpg://user:pass@db.internal/aegis",
        "postgresql://db.internal",
        "not-a-url",
    ),
)
def test_invalid_database_urls_are_rejected(database_url: str) -> None:
    with pytest.raises(ValidationError):
        make_settings(database_url=database_url)


@pytest.mark.parametrize("scheme", ("redis", "rediss"))
@pytest.mark.parametrize("field_name", ("redis_url", "celery_broker_url"))
def test_accepted_redis_schemes(field_name: str, scheme: str) -> None:
    url = f"{scheme}://user:pass@redis.internal/0"

    assert make_settings(**{field_name: url}).__getattribute__(
        field_name
    ).get_secret_value() == url


@pytest.mark.parametrize("field_name", ("redis_url", "celery_broker_url"))
@pytest.mark.parametrize("url", ("http://redis.internal/0", "not-a-url"))
def test_invalid_redis_urls_are_rejected(field_name: str, url: str) -> None:
    with pytest.raises(ValidationError):
        make_settings(**{field_name: url})


@pytest.mark.parametrize("host", ("localhost", "127.0.0.1", "[::1]"))
@pytest.mark.parametrize(
    "field_name",
    ("database_url", "redis_url", "celery_broker_url"),
)
def test_production_rejects_literal_loopback_hosts(
    field_name: str, host: str
) -> None:
    values = dict(PRODUCTION_VALUES)
    scheme = "postgresql" if field_name == "database_url" else "redis"
    path = "aegis" if field_name == "database_url" else "0"
    values[field_name] = f"{scheme}://user:canary@{host}/{path}"

    with pytest.raises(ValidationError):
        make_settings(**values)


def test_url_validation_performs_no_dns_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_resolution(*args: object, **kwargs: object) -> None:
        raise AssertionError("DNS resolution must not occur")

    monkeypatch.setattr(socket, "getaddrinfo", fail_resolution)

    assert make_settings(**PRODUCTION_VALUES).environment is (
        RuntimeEnvironment.PRODUCTION
    )


def test_secret_values_are_redacted_from_representations() -> None:
    settings = make_settings(**PRODUCTION_VALUES)
    rendered = (repr(settings), str(settings), settings.model_dump_json())

    for canary in ("database-canary", "redis-canary", "broker-canary"):
        assert all(canary not in representation for representation in rendered)


def test_secret_value_is_redacted_from_validation_errors() -> None:
    canary = "validation-secret-canary"

    with pytest.raises(ValidationError) as error:
        make_settings(database_url=f"mysql://user:{canary}@db.internal/aegis")

    assert canary not in str(error.value)


def test_settings_are_frozen() -> None:
    settings = make_settings()

    with pytest.raises(ValidationError):
        settings.log_level = LogLevel.ERROR


def test_settings_instances_are_independent() -> None:
    first = make_settings(log_level="INFO")
    second = make_settings(log_level="DEBUG")

    assert first is not second
    assert first.log_level is LogLevel.INFO
    assert second.log_level is LogLevel.DEBUG


def test_explicit_dotenv_source_is_supported(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("AEGIS_LOG_LEVEL=WARNING\n", encoding="utf-8")

    settings = Settings(_env_file=dotenv)

    assert settings.log_level is LogLevel.WARNING

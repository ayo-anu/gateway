"""Smoke tests for the minimal gateway API."""

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from pydantic import ValidationError

from gateway.config import Settings
from gateway.gateway_api.app import create_app


def get(path: str, settings: Settings | None = None) -> Response:
    async def request() -> Response:
        transport = ASGITransport(app=create_app(settings))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)

    return asyncio.run(request())


def test_create_app_returns_distinct_fastapi_instances() -> None:
    settings = Settings(_env_file=None)
    first_app = create_app(settings)
    second_app = create_app(settings)

    assert isinstance(first_app, FastAPI)
    assert isinstance(second_app, FastAPI)
    assert first_app is not second_app
    assert not hasattr(first_app.state, "settings")


def test_create_app_constructs_settings_for_each_factory_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import gateway.gateway_api.app as app_module

    settings = Settings(_env_file=None)
    calls = 0

    def settings_factory() -> Settings:
        nonlocal calls
        calls += 1
        return settings

    monkeypatch.setattr(app_module, "Settings", settings_factory)

    app_module.create_app()
    app_module.create_app()

    assert calls == 2


def test_invalid_startup_configuration_prevents_app_creation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GATEWAY_ENVIRONMENT", "production")

    with pytest.raises(ValidationError):
        create_app()


def test_valid_production_configuration_allows_app_creation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GATEWAY_ENVIRONMENT", "production")
    monkeypatch.setenv(
        "GATEWAY_DATABASE_URL",
        "postgresql+psycopg://user:pass@db.internal/gateway",
    )
    monkeypatch.setenv("GATEWAY_REDIS_URL", "rediss://user:pass@redis.internal/0")
    monkeypatch.setenv(
        "GATEWAY_CELERY_BROKER_URL",
        "rediss://user:pass@broker.internal/1",
    )
    monkeypatch.setenv("GATEWAY_STORAGE_ROOT", "/var/lib/gateway/storage")

    app = create_app()

    assert isinstance(app, FastAPI)
    assert not hasattr(app.state, "settings")


def test_root_is_inert_and_deterministic() -> None:
    response = get("/", Settings(_env_file=None))

    assert response.status_code == 200
    assert response.json() == {"name": "Gateway", "status": "ok"}


def test_liveness_is_inert_and_deterministic() -> None:
    response = get("/health/live", Settings(_env_file=None))

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_unknown_route_returns_not_found() -> None:
    response = get("/business", Settings(_env_file=None))

    assert response.status_code == 404

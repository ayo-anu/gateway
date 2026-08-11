"""Tests for inert executable process boundaries."""

import ast
import signal
from pathlib import Path
from threading import Event
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.routing import APIWebSocketRoute
from httpx import ASGITransport, AsyncClient

from gateway.config import Settings
from gateway.gateway_api.app import create_app as create_api_app
from gateway.usage_aggregator import process as worker_process
from gateway.ws_usage_gateway.app import create_app as create_ws_app


def make_settings(process_name: str) -> Settings:
    return Settings(_env_file=None, process_name=process_name)


def test_api_process_factory_remains_executable() -> None:
    app = create_api_app(make_settings("gateway-api"))

    assert isinstance(app, FastAPI)


def test_worker_run_uses_the_supplied_stop_event() -> None:
    stop_event = Event()
    stop_event.set()

    worker_process.run(
        make_settings("usage-worker"),
        stop_event=stop_event,
    )


def test_worker_rejects_another_process_identity() -> None:
    with pytest.raises(ValueError, match="process_name=usage-worker"):
        worker_process.run(
            make_settings("gateway-api"),
            stop_event=Event(),
        )


@pytest.mark.parametrize("shutdown_signal", (signal.SIGTERM, signal.SIGINT))
def test_worker_main_translates_signals_into_normal_shutdown(
    monkeypatch: pytest.MonkeyPatch,
    shutdown_signal: signal.Signals,
) -> None:
    handlers: dict[signal.Signals, Any] = {}

    def register_handler(
        registered_signal: signal.Signals,
        handler: Any,
    ) -> None:
        handlers[registered_signal] = handler

    def run_until_signalled(
        settings: Settings | None = None,
        *,
        stop_event: Event | None = None,
    ) -> None:
        assert settings is None
        assert stop_event is not None
        assert not stop_event.is_set()
        handler = handlers[shutdown_signal]
        handler(shutdown_signal, None)
        assert stop_event.is_set()

    monkeypatch.setattr(signal, "signal", register_handler)
    monkeypatch.setattr(worker_process, "run", run_until_signalled)

    worker_process.main()

    assert set(handlers) == {signal.SIGTERM, signal.SIGINT}


def test_websocket_gateway_factory_returns_distinct_inert_apps() -> None:
    settings = make_settings("ws-usage-gateway")
    first = create_ws_app(settings)
    second = create_ws_app(settings)

    assert isinstance(first, FastAPI)
    assert isinstance(second, FastAPI)
    assert first is not second
    assert not any(isinstance(route, APIWebSocketRoute) for route in first.routes)


def test_websocket_gateway_rejects_another_process_identity() -> None:
    with pytest.raises(ValueError, match="process_name=ws-usage-gateway"):
        create_ws_app(make_settings("gateway-api"))


def test_websocket_gateway_liveness() -> None:
    async def request() -> None:
        transport = ASGITransport(app=create_ws_app(make_settings("ws-usage-gateway")))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/live")

        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

    import asyncio

    asyncio.run(request())


@pytest.mark.parametrize(
    "module_path",
    (
        Path("src/gateway/usage_aggregator/process.py"),
        Path("src/gateway/ws_usage_gateway/app.py"),
    ),
)
def test_process_modules_do_not_parse_environment_directly(module_path: Path) -> None:
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert "GATEWAY_" not in source
    assert not any(
        (
            isinstance(node, ast.Import)
            and any(alias.name == "os" for alias in node.names)
        )
        or (isinstance(node, ast.ImportFrom) and node.module == "os")
        for node in ast.walk(tree)
    )

"""Smoke tests for the minimal gateway API."""

import asyncio

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from aegis.gateway_api.app import create_app


def get(path: str) -> Response:
    async def request() -> Response:
        transport = ASGITransport(app=create_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)

    return asyncio.run(request())


def test_create_app_returns_distinct_fastapi_instances() -> None:
    first_app = create_app()
    second_app = create_app()

    assert isinstance(first_app, FastAPI)
    assert isinstance(second_app, FastAPI)
    assert first_app is not second_app


def test_root_is_inert_and_deterministic() -> None:
    response = get("/")

    assert response.status_code == 200
    assert response.json() == {"name": "Aegis API Platform", "status": "ok"}


def test_liveness_is_inert_and_deterministic() -> None:
    response = get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_unknown_route_returns_not_found() -> None:
    response = get("/business")

    assert response.status_code == 404

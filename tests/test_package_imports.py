"""Smoke tests for the required package boundaries."""

from importlib import import_module

import pytest


@pytest.mark.parametrize(
    "module_name",
    (
        "aegis",
        "aegis.gateway_api",
        "aegis.key_management",
        "aegis.usage_aggregator",
        "aegis.ws_usage_gateway",
        "aegis.infrastructure",
    ),
)
def test_required_package_is_importable(module_name: str) -> None:
    assert import_module(module_name) is not None


def test_application_factory_is_importable() -> None:
    module = import_module("aegis.gateway_api.app")

    assert callable(module.create_app)

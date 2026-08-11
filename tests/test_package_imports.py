"""Smoke tests for the required package boundaries."""

from importlib import import_module

import pytest


@pytest.mark.parametrize(
    "module_name",
    (
        "gateway",
        "gateway.gateway_api",
        "gateway.key_management",
        "gateway.usage_aggregator",
        "gateway.ws_usage_gateway",
        "gateway.infrastructure",
    ),
)
def test_required_package_is_importable(module_name: str) -> None:
    assert import_module(module_name) is not None


def test_application_factory_is_importable() -> None:
    module = import_module("gateway.gateway_api.app")

    assert callable(module.create_app)

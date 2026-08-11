"""Tests for side-effect-free database infrastructure construction."""

import ast
import importlib
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import URL, Engine
from sqlalchemy.orm import Session

from gateway.config import Settings
from gateway.infrastructure.database.metadata import NAMING_CONVENTION, Base
from gateway.infrastructure.database.session import (
    create_database_engine,
    create_session_factory,
    database_url_from_settings,
)

EXPECTED_NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def make_settings(database_url: str) -> Settings:
    return Settings(_env_file=None, database_url=database_url)


def test_metadata_is_empty_and_uses_the_authoritative_naming_convention() -> None:
    assert NAMING_CONVENTION == EXPECTED_NAMING_CONVENTION
    assert Base.metadata.naming_convention == EXPECTED_NAMING_CONVENTION
    assert Base.metadata.tables == {}


def test_generic_postgresql_url_selects_psycopg_and_preserves_credentials() -> None:
    url = database_url_from_settings(
        make_settings(
            "postgresql://user:p%40ss@db.internal:5433/gateway?sslmode=require"
        )
    )

    assert url.drivername == "postgresql+psycopg"
    assert url.username == "user"
    assert url.password == "p@ss"
    assert url.host == "db.internal"
    assert url.port == 5433
    assert url.database == "gateway"
    assert url.query == {"sslmode": "require"}


def test_explicit_psycopg_url_is_retained() -> None:
    url = database_url_from_settings(
        make_settings("postgresql+psycopg://user:pass@db.internal/gateway")
    )

    assert url.drivername == "postgresql+psycopg"


def test_engine_and_session_factory_construction_do_not_connect(
    monkeypatch: Any,
) -> None:
    connect = Mock(side_effect=AssertionError("construction must not connect"))
    monkeypatch.setattr(psycopg, "connect", connect)

    engine = create_database_engine(
        make_settings("postgresql+psycopg://user:pass@unreachable.invalid/gateway")
    )
    session_factory = create_session_factory(engine)
    session = session_factory()

    assert isinstance(engine, Engine)
    assert isinstance(session, Session)
    assert not session.in_transaction()
    connect.assert_not_called()

    session.close()
    engine.dispose()


def test_importing_database_modules_does_not_connect(monkeypatch: Any) -> None:
    connect = Mock(side_effect=AssertionError("imports must not connect"))
    monkeypatch.setattr(psycopg, "connect", connect)

    import gateway.infrastructure.database.metadata as metadata_module
    import gateway.infrastructure.database.session as session_module

    importlib.reload(metadata_module)
    importlib.reload(session_module)

    connect.assert_not_called()


def test_alembic_uses_authoritative_settings_for_its_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = Config("alembic.ini", stdout=StringIO())
    observed_settings: list[Settings] = []

    def observe_database_url(settings: Settings) -> URL:
        observed_settings.append(settings)
        return database_url_from_settings(settings)

    monkeypatch.setenv(
        "GATEWAY_DATABASE_URL",
        "postgresql+psycopg://user:pass@unreachable.invalid/gateway",
    )
    monkeypatch.setattr(
        "gateway.infrastructure.database.session.database_url_from_settings",
        observe_database_url,
    )

    command.upgrade(config, "head", sql=True)

    assert len(observed_settings) == 1
    assert isinstance(observed_settings[0], Settings)
    assert not config.get_main_option("sqlalchemy.url")

    env_source = Path("migrations/env.py").read_text(encoding="utf-8")
    env_tree = ast.parse(env_source)
    assert "GATEWAY_DATABASE_URL" not in env_source
    assert not any(
        (
            isinstance(node, ast.Import)
            and any(alias.name == "os" for alias in node.names)
        )
        or (isinstance(node, ast.ImportFrom) and node.module == "os")
        for node in ast.walk(env_tree)
    )

"""Real-PostgreSQL verification for the empty Alembic baseline."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from gateway.config import Settings
from gateway.infrastructure.database.metadata import Base
from gateway.infrastructure.database.session import create_database_engine

pytestmark = pytest.mark.postgresql

EXPECTED_HEAD = "0001_empty_baseline"


def test_empty_postgresql_database_upgrades_to_head() -> None:
    config = Config(Path("alembic.ini"))
    settings = Settings(_env_file=None)
    engine = create_database_engine(settings)

    assert not config.get_main_option("sqlalchemy.url")
    assert Base.metadata.tables == {}

    try:
        with engine.connect() as connection:
            assert inspect(connection).get_table_names(schema="public") == []

        command.upgrade(config, "head")

        with engine.connect() as connection:
            assert inspect(connection).get_table_names(schema="public") == [
                "alembic_version"
            ]
            current_revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            assert current_revision == EXPECTED_HEAD
    finally:
        engine.dispose()

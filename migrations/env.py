"""Alembic environment backed by Gateway's authoritative settings."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from gateway.config import Settings
from gateway.infrastructure.database.metadata import Base
from gateway.infrastructure.database.session import database_url_from_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def configured_database_url():
    """Load and parse the migration URL through validated Gateway settings."""
    return database_url_from_settings(Settings())


def run_migrations_offline() -> None:
    """Render migrations without constructing an engine or connection."""
    context.configure(
        url=configured_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a one-shot, migration-owned engine."""
    engine = create_engine(configured_database_url(), poolclass=NullPool)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

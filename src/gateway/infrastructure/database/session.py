"""Side-effect-free synchronous engine and session-factory construction."""

from sqlalchemy import URL, Engine, create_engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from gateway.config import Settings


def database_url_from_settings(settings: Settings) -> URL:
    """Return the validated database URL configured for the Psycopg driver."""
    url = make_url(settings.database_url.get_secret_value())
    if url.drivername == "postgresql":
        return url.set(drivername="postgresql+psycopg")
    return url


def create_database_engine(settings: Settings) -> Engine:
    """Construct a caller-owned lazy runtime engine without connecting."""
    return create_engine(database_url_from_settings(settings))


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Construct a caller-owned session factory without creating a session."""
    return sessionmaker(bind=engine)

"""FastAPI application factory for the HTTP gateway."""

from fastapi import FastAPI

from aegis.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the minimal Aegis gateway application."""
    if settings is None:
        Settings()
    app = FastAPI(title="Aegis API Platform")

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"name": "Aegis API Platform", "status": "ok"}

    @app.get("/health/live")
    async def liveness() -> dict[str, str]:
        return {"status": "alive"}

    return app

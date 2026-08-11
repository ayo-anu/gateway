"""FastAPI application factory for the HTTP gateway."""

from fastapi import FastAPI

from gateway.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the minimal Gateway gateway application."""
    if settings is None:
        Settings()
    app = FastAPI(title="Gateway")

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"name": "Gateway", "status": "ok"}

    @app.get("/health/live")
    async def liveness() -> dict[str, str]:
        return {"status": "alive"}

    return app

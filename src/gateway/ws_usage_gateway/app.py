"""Inert ASGI application factory for the WebSocket gateway process."""

from fastapi import FastAPI

from gateway.config import ProcessName, Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create a liveness-only WebSocket gateway process boundary."""
    resolved_settings = settings if settings is not None else Settings()
    if resolved_settings.process_name is not ProcessName.WS_USAGE_GATEWAY:
        raise ValueError("WebSocket gateway requires process_name=ws-usage-gateway")

    app = FastAPI(title="Gateway WebSocket Gateway")

    @app.get("/health/live")
    async def liveness() -> dict[str, str]:
        return {"status": "alive"}

    return app

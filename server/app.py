"""FastAPI application (PRD/02 §2, PRD/09). Run: uv run --env-file .env uvicorn server.app:app --port 8000"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.config import Settings, load_settings
from server.errors import install_error_handlers
from server.events import EventBus
from server.routes import events
from server.storage import Storage


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.bus.bind_loop(asyncio.get_running_loop())
        yield

    app = FastAPI(title="Floorplan3D", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)
    app.state.settings = settings
    app.state.storage = Storage(settings.data_dir)
    app.state.bus = EventBus(app.state.storage)
    install_error_handlers(app)
    app.include_router(events.router)
    return app


app = create_app()

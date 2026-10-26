"""FastAPI application (PRD/02 §2, PRD/09). Run: uv run --env-file .env uvicorn server.app:app --port 8000"""

from fastapi import FastAPI

from core.config import Settings, load_settings
from server.errors import install_error_handlers
from server.storage import Storage


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="Floorplan3D", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.settings = settings
    app.state.storage = Storage(settings.data_dir)
    install_error_handlers(app)
    return app


app = create_app()

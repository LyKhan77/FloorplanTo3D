"""FastAPI application (PRD/02 §2, PRD/09). Run: uv run --env-file .env uvicorn server.app:app --port 8000"""

import asyncio
import fcntl
import signal
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core.config import Settings, load_settings
from server.errors import ApiError, install_error_handlers
from server.events import EventBus
from server.orchestrator import Orchestrator
from server.routes import events, outputs, projects, runs, specs, system, templates
from server.storage import Storage


def lock_data_dir(root: Path):
    """One server process per DATA_DIR (PRD/02 §5): two orchestrators would run the same queue twice and write
    events.jsonl side by side. Taken before recovery, which uvicorn runs before it binds the port."""
    root.mkdir(parents=True, exist_ok=True)
    f = open(root / ".server.lock", "w")  # noqa: SIM115 - held open for the life of the app
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        raise RuntimeError(f"another server is already serving {root}") from None
    return f


def close_bus_on_exit_signal(bus: EventBus) -> None:
    """Chain onto the server's SIGINT/SIGTERM handlers: close SSE streams first so graceful shutdown can finish
    (same idea as sse-starlette). Signals can only be set from the main thread; TestClient runs elsewhere."""
    if threading.current_thread() is not threading.main_thread():
        return
    for sig in (signal.SIGINT, signal.SIGTERM):
        previous = signal.getsignal(sig)
        if not callable(previous):
            continue

        def handler(s, frame, previous=previous):
            bus.close()
            previous(s, frame)

        signal.signal(sig, handler)


def create_app(settings: Settings | None = None, stage_impls: dict | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        lock = lock_data_dir(app.state.storage.root)
        app.state.bus.bind_loop(asyncio.get_running_loop())
        await app.state.orchestrator.start()
        close_bus_on_exit_signal(app.state.bus)
        yield
        await app.state.orchestrator.stop()
        app.state.bus.close()
        lock.close()

    app = FastAPI(title="Floorplan3D", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)
    app.state.settings = settings
    app.state.storage = Storage(settings.data_dir)
    app.state.bus = EventBus(app.state.storage)
    app.state.orchestrator = Orchestrator(app.state.storage, app.state.bus, settings, stage_impls)
    install_error_handlers(app)
    app.include_router(events.router)
    app.include_router(projects.router)
    app.include_router(specs.router)
    app.include_router(runs.router)
    app.include_router(outputs.router)
    app.include_router(templates.router)
    app.include_router(system.router)
    _mount_web(app)
    return app


def _mount_web(app: FastAPI) -> None:
    """Serve the built dashboard (web/dist) at / with SPA fallback, when it exists."""
    dist = Path(__file__).resolve().parents[1] / "web" / "dist"
    if not (dist / "index.html").exists():
        return
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise ApiError(404, "not_found", "unknown API path")
        f = (dist / path).resolve()
        if path and f.is_file() and f.is_relative_to(dist.resolve()):
            return FileResponse(f)
        return FileResponse(dist / "index.html")


app = create_app()

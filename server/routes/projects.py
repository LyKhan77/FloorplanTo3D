"""/api/projects (PRD/09 §2.1)."""

import json
import shutil
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.extraction.profiles import ProfileNotFound, load_profile
from core.spec.store import SpecStore
from server.errors import ApiError
from server.projects import (
    create_project,
    latest_run,
    latest_stage_file,
    output_versions,
    summary,
    touch,
)

router = APIRouter(prefix="/api/projects")
CHUNK = 1024 * 1024


async def _read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    data = bytearray()
    while chunk := await upload.read(CHUNK):
        data += chunk
        if len(data) > max_bytes:  # stop reading as soon as the limit is passed
            raise ApiError(413, "file_too_large", f"upload exceeds {max_bytes // CHUNK} MB")
    return bytes(data)


@router.post("", status_code=201)
async def create(request: Request, file: Annotated[UploadFile, File()], name: Annotated[str | None, Form()] = None,
                 prompt: Annotated[str, Form()] = "", params: Annotated[str | None, Form()] = None,
                 page: Annotated[int | None, Form()] = None, start: Annotated[bool, Form()] = True,
                 profile_id: Annotated[str | None, Form()] = None):
    try:
        parsed = json.loads(params) if params else {}
    except json.JSONDecodeError:
        parsed = None
    if not isinstance(parsed, dict):
        raise ApiError(400, "bad_request", "params must be a JSON object")
    if profile_id:
        try:
            load_profile(request.app.state.storage, profile_id)
        except ProfileNotFound as e:
            raise ApiError(404, "not_found", str(e)) from None
    settings = request.app.state.settings
    data = await _read_limited(file, settings.max_upload_mb * CHUNK)
    project = create_project(request.app.state.storage, data, file.filename or "upload", name, prompt, parsed, page,
                             settings.max_upload_mb * CHUNK)
    run_id = None
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if start and orchestrator is not None:
        run_id = orchestrator.start_run(project["project_id"], "full", profile_id=profile_id)["run_id"]
    return {"project_id": project["project_id"], "run_id": run_id, "status": "queued" if run_id else "new"}


@router.get("")
def list_projects(request: Request, q: str | None = None, status: str | None = None, limit: int = 50, offset: int = 0):
    st = request.app.state.storage
    if not st.projects_dir.exists():
        return {"items": [], "total": 0}
    items = [summary(st, p.name) for p in st.projects_dir.iterdir() if (p / "project.json").exists()]
    if q:
        items = [i for i in items if q.lower() in i["name"].lower() or q.lower() in i["project_id"]]
    if status:
        items = [i for i in items if i["status"] == status]
    items.sort(key=lambda i: i["updated_at"], reverse=True)
    return {"items": items[offset:offset + limit], "total": len(items)}


@router.get("/{pid}")
def detail(pid: str, request: Request):
    st = request.app.state.storage
    d = st.project_dir(pid)
    project = st.read_json(d / "project.json")
    return project | {"latest_run": latest_run(st, pid), "head": SpecStore(d / "specs").head(),
                      "outputs": output_versions(st, pid), "summary": summary(st, pid)}


class ProjectPatch(BaseModel):
    name: str | None = None
    params: dict | None = None


@router.patch("/{pid}")
def patch(pid: str, body: ProjectPatch, request: Request):
    changes = body.model_dump(exclude_none=True)
    return touch(request.app.state.storage, pid, **changes)


@router.delete("/{pid}")
def delete(pid: str, request: Request, confirm: bool = False):
    d = request.app.state.storage.project_dir(pid)
    if not confirm:
        raise ApiError(400, "confirmation_required", "add ?confirm=true to delete a project")
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is not None and orchestrator.active_run(pid):
        raise ApiError(409, "run_in_progress", "cancel the active run before deleting the project")
    shutil.rmtree(d)
    return {"deleted": pid}


@router.get("/{pid}/input")
def original(pid: str, request: Request):
    d = request.app.state.storage.project_dir(pid) / "input"
    f = next(d.glob("original.*"), None)
    if f is None:
        raise ApiError(404, "not_found", "original file missing")
    return FileResponse(f)


class SnapBody(BaseModel):
    a: tuple[float, float]
    b: tuple[float, float]


@router.post("/{pid}/snap")
def snap(pid: str, body: SnapBody, request: Request):
    """M8 guide line: the rough line (mm) moved onto the double line of the newest run's binary page."""
    import cv2

    from core.extraction.snap import snap_wall

    storage = request.app.state.storage
    storage.project_dir(pid)
    page, grid = latest_stage_file(storage, pid, "01_preprocess/bin.png"), latest_stage_file(storage, pid, "02_grid/grid.json")
    if not page or not grid:
        raise ApiError(404, "no_run", "no extraction run with a page image")
    found = snap_wall(cv2.imread(str(page), cv2.IMREAD_GRAYSCALE), json.loads(grid.read_text())["px_to_mm"], body.a, body.b)
    if found is None:
        raise ApiError(422, "no_line", "tidak ada garis ganda di dekat garis ini")
    return found


@router.get("/{pid}/backdrop")
def backdrop(pid: str, request: Request):
    """M8 review canvas: the newest page image and the px -> mm transform that lays it under the spec."""
    storage = request.app.state.storage
    storage.project_dir(pid)
    page, grid = latest_stage_file(storage, pid, "01_preprocess/page.png"), latest_stage_file(storage, pid, "02_grid/grid.json")
    if not page or not grid or page.parents[2] != grid.parents[2]:
        raise ApiError(404, "no_run", "no extraction run with a page image")
    rid = page.parents[2].name
    return {"url": f"/api/projects/{pid}/runs/{rid}/artifacts/01_preprocess/page.png",
            "px_to_mm": json.loads(grid.read_text())["px_to_mm"]}

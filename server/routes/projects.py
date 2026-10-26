"""/api/projects (PRD/09 §2.1)."""

import json
import shutil

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.spec.store import SpecStore
from server.errors import ApiError
from server.projects import create_project, latest_run, output_versions, summary, touch

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
async def create(request: Request, file: UploadFile = File(...), name: str | None = Form(None),
                 prompt: str = Form(""), params: str | None = Form(None), page: int | None = Form(None),
                 start: bool = Form(True)):
    try:
        parsed = json.loads(params) if params else {}
    except json.JSONDecodeError:
        parsed = None
    if not isinstance(parsed, dict):
        raise ApiError(400, "bad_request", "params must be a JSON object")
    settings = request.app.state.settings
    data = await _read_limited(file, settings.max_upload_mb * CHUNK)
    project = create_project(request.app.state.storage, data, file.filename or "upload", name, prompt, parsed, page,
                             settings.max_upload_mb * CHUNK)
    run_id = None
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if start and orchestrator is not None:
        run_id = orchestrator.start_run(project["project_id"], "full")["run_id"]
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

"""Installation layer API (M12a, design §6): start, edit with ops, dry-run validate, rebase, snap to the drawing."""

import json
from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.installation.derive import drops, lengths, rack_categories
from core.installation.models import Installation
from core.installation.ops import apply
from core.installation.store import InstallationStore
from core.installation.validate import validate_installation
from core.spec.ops import OpError
from core.spec.store import SpecStore, ValidationFailed, VersionConflict
from server.errors import ApiError
from server.projects import latest_stage_file, touch

router = APIRouter(prefix="/api/projects/{pid}/installations")
RACK_MATCH_MM = 100


class StartBody(BaseModel):
    ceiling_height: int | None = None
    raised_floor_height: int | None = None
    default_mounting: Literal["overhead", "underfloor"] = "overhead"


class OpsBody(BaseModel):
    base_version: int
    ops: list[dict]
    message: str = ""


class BuildBody(BaseModel):
    version: int | Literal["HEAD"] = "HEAD"


class SnapTrayBody(BaseModel):
    points: list[tuple[float, float]]


class SnapBoxBody(BaseModel):
    at: tuple[float, float]


class FitBoxBody(BaseModel):
    a: tuple[float, float]
    b: tuple[float, float]


def _store(request: Request, pid: str) -> InstallationStore:
    return InstallationStore(request.app.state.storage.project_dir(pid) / "installations")


def _specs(request: Request, pid: str) -> SpecStore:
    return SpecStore(request.app.state.storage.project_dir(pid) / "specs")


def _templates(request: Request) -> dict[str, str]:
    return rack_categories(request.app.state.storage.templates_dir)


def _head(store: InstallationStore) -> Installation:
    try:
        return store.load("HEAD")
    except (FileNotFoundError, OSError):
        raise ApiError(404, "no_installation", "instalasi belum dimulai") from None


def _issues(issues) -> list[dict]:
    return [asdict(i) for i in issues]


@router.post("/start", status_code=201)
def start(pid: str, body: StartBody, request: Request):
    from core.extraction.stages import run_params

    d = request.app.state.storage.project_dir(pid)
    layout_head = _specs(request, pid).head()
    if layout_head is None:
        raise ApiError(409, "no_layout", "layout belum punya versi spec")
    try:
        params = run_params(d)
    except (OSError, ValueError):
        params = {}
    ceiling = body.ceiling_height if body.ceiling_height is not None else params.get("ceiling_height")
    raised = body.raised_floor_height if body.raised_floor_height is not None else params.get("raised_floor_height")
    try:
        inst = _store(request, pid).start(layout_head, ceiling, raised, body.default_mounting)
    except FileExistsError:
        raise ApiError(409, "exists", "instalasi sudah dimulai") from None
    touch(request.app.state.storage, pid)
    return inst.model_dump(mode="json")


@router.get("")
def versions(pid: str, request: Request):
    store = _store(request, pid)
    out = []
    for v in store.versions():
        m = store.load(v).meta
        out.append({"version": v, "created_at": m.created_at, "message": m.message, "layout_version": m.layout_version})
    return out


@router.get("/HEAD")
def head(pid: str, request: Request):
    return _head(_store(request, pid)).model_dump(mode="json")


@router.post("", status_code=201)
def commit(pid: str, body: OpsBody, request: Request):
    store, specs = _store(request, pid), _specs(request, pid)
    layout = specs.load(_head(store).meta.layout_version)
    templates = _templates(request)
    try:
        inst, issues = store.commit_ops(body.base_version, body.ops, "editor", body.message, layout, templates,
                                        layout_head=specs.head())
    except VersionConflict as e:
        raise ApiError(409, "installation_conflict", str(e), {"base": e.base, "head": e.head}) from None
    except ValidationFailed as e:
        raise ApiError(422, "validation_failed", str(e), {"issues": _issues(e.issues)}) from None
    except OpError as e:
        raise ApiError(400, "bad_op", e.message, {"index": e.index, "op": e.op, "message": e.message}) from None
    touch(request.app.state.storage, pid)
    return {"version": inst.meta.version, "installation": inst.model_dump(mode="json"), "issues": _issues(issues),
            "lengths": lengths(inst, layout, templates)}


@router.post("/validate")
def dry_run(pid: str, body: OpsBody, request: Request):
    store, specs = _store(request, pid), _specs(request, pid)
    try:
        base = store.load(body.base_version)
    except (FileNotFoundError, OSError):
        raise ApiError(404, "no_installation", f"installation version {body.base_version} not found") from None
    try:
        inst = apply(base, body.ops, "editor", base.meta.version + 1)
    except OpError as e:
        raise ApiError(400, "bad_op", e.message, {"index": e.index, "op": e.op, "message": e.message}) from None
    layout, templates = specs.load(inst.meta.layout_version), _templates(request)
    return {"issues": _issues(validate_installation(inst, layout, templates, layout_head=specs.head())),
            "drops": drops(inst, layout, templates), "lengths": lengths(inst, layout, templates)}


@router.post("/rebase")
def rebase(pid: str, request: Request):
    store, specs = _store(request, pid), _specs(request, pid)
    _head(store)
    layout_head = specs.head()
    previous = specs.load(_head(store).meta.layout_version)
    inst, issues = store.rebase(layout_head, specs.load(layout_head), _templates(request), previous=previous)
    touch(request.app.state.storage, pid)
    return {"version": inst.meta.version, "issues": _issues(issues)}


def _page(request: Request, pid: str):
    """The newest run's binary page and its px -> mm transform, as the wall guide line uses (server/routes/projects.snap)."""
    import cv2

    storage = request.app.state.storage
    page, grid = latest_stage_file(storage, pid, "01_preprocess/bin.png"), latest_stage_file(storage, pid, "02_grid/grid.json")
    if not page or not grid:
        raise ApiError(404, "no_run", "belum ada gambar hasil ekstraksi untuk di-snap")
    return cv2.imread(str(page), cv2.IMREAD_GRAYSCALE), json.loads(grid.read_text())["px_to_mm"]


@router.post("/snap-tray")
def snap_tray_route(pid: str, body: SnapTrayBody, request: Request):
    from core.installation.snap import snap_tray

    binary, t = _page(request, pid)
    found = snap_tray(binary, t, body.points)
    if found is None:
        raise ApiError(422, "no_band", "tidak ada pita tray di dekat garis ini")
    return found


def _with_template(request: Request, found: dict) -> dict:
    """The rack template whose footprint matches the box within RACK_MATCH_MM in either orientation, else None."""
    short, long_ = found["size"]
    found["template_id"] = None
    for f in sorted(request.app.state.storage.templates_dir.glob("*/*/template.json")):
        try:
            meta = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if meta.get("category") != "rack":
            continue
        w, d = sorted((meta["dims"]["w"], meta["dims"]["d"]))
        if abs(w - short) <= RACK_MATCH_MM and abs(d - long_) <= RACK_MATCH_MM:
            return found | {"template_id": meta["id"], "template_version": meta["version"],
                            "dims": [meta["dims"]["w"], meta["dims"]["d"], meta["dims"]["h"]]}
    return found


@router.post("/snap-box")
def snap_box_route(pid: str, body: SnapBoxBody, request: Request):
    from core.installation.snap import snap_box

    binary, t = _page(request, pid)
    found = snap_box(binary, t, body.at)
    if found is None:
        raise ApiError(422, "no_box", "tidak ada kotak rack di sini")
    return _with_template(request, found)


@router.post("/fit-box")
def fit_box_route(pid: str, body: FitBoxBody, request: Request):
    """Shift-drag: a rack placed by hand on the dragged box, its sides moved onto the nearest drawn lines."""
    from core.installation.snap import fit_box

    binary, t = _page(request, pid)
    found = fit_box(binary, t, body.a, body.b)
    if found is None:
        raise ApiError(422, "no_box", "kotak terlalu kecil atau terlalu besar untuk rack (300–3000 mm)")
    return _with_template(request, found)


@router.post("/build", status_code=202)
def build(pid: str, body: BuildBody, request: Request):
    """M12b: build the installation in 3D (run kind "installation", stages 7-10); refused while it has errors."""
    store, specs = _store(request, pid), _specs(request, pid)
    try:
        inst = _head(store) if body.version == "HEAD" else store.load(body.version)
    except (FileNotFoundError, OSError):
        raise ApiError(404, "no_installation", f"installation version {body.version} not found") from None
    issues = validate_installation(inst, specs.load(inst.meta.layout_version), _templates(request), layout_head=specs.head())
    if any(i.severity == "error" for i in issues):
        raise ApiError(409, "installation_invalid", "instalasi masih punya error; perbaiki lalu Save",
                       {"issues": _issues(i for i in issues if i.severity == "error")})
    run = request.app.state.orchestrator.start_run(pid, "installation", version=inst.meta.version)
    return {"run_id": run["run_id"], "status": run["status"]}


def _outputs_root(request: Request, pid: str):
    return request.app.state.storage.project_dir(pid) / "installation_outputs"


@router.get("/outputs")
def outputs(pid: str, request: Request):
    root = _outputs_root(request, pid)
    versions = sorted((int(d.name[1:]) for d in root.iterdir() if d.is_dir() and d.name[1:].isdigit() and d.name.startswith("v")),
                      reverse=True) if root.exists() else []
    # built_at (mtime): a rebuilt version keeps its file names, so the viewer adds it to the URL to skip a cached model
    return [{"version": v, "built_at": int((root / f"v{v}").stat().st_mtime),
             "files": sorted(str(f.relative_to(root / f"v{v}")) for f in (root / f"v{v}").rglob("*") if f.is_file())}
            for v in versions]


@router.get("/outputs/{v}/{path:path}")
def output_file(pid: str, v: int, path: str, request: Request):
    storage = request.app.state.storage
    return FileResponse(storage.safe_join(_outputs_root(request, pid) / f"v{v}", path))


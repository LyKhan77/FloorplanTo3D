"""/api/projects/{id}/specs (PRD/09 §2.4)."""

import json
from dataclasses import asdict

from fastapi import APIRouter, Header, Query, Request
from pydantic import BaseModel, ValidationError

from core.extraction.rooms.labels import labels_from_ocr
from core.spec.diff import diff_specs
from core.spec.models import Spec
from core.spec.ops import OpError, apply
from core.spec.review_tasks import review_tasks
from core.spec.store import SpecStore, ValidationFailed, VersionConflict
from core.spec.validate import validate
from server.errors import ApiError
from server.projects import latest_stage_file, output_versions, touch

router = APIRouter(prefix="/api/projects/{pid}/specs")


class OpsBody(BaseModel):
    base_version: int
    ops: list[dict]
    message: str = ""


def _store(request: Request, pid: str) -> SpecStore:
    return SpecStore(request.app.state.storage.project_dir(pid) / "specs")


def _load(store: SpecStore, version) -> Spec:
    try:
        return store.load(version)
    except (FileNotFoundError, OSError):
        raise ApiError(404, "spec_not_found", f"spec version {version} not found") from None


def _issues(issues) -> list[dict]:
    return [asdict(i) for i in issues]


def _commit_message(spec: Spec) -> str:
    return next((e.reason or "" for e in reversed(spec.provenance_log) if e.op == "commit"), "")


@router.get("")
def list_versions(pid: str, request: Request):
    store = _store(request, pid)
    with_outputs = set(output_versions(request.app.state.storage, pid))
    out = []
    for v in store.versions():
        m = store.load(v).meta
        out.append({"version": v, "source": m.source, "created_at": m.created_at.isoformat(),
                    "message": _commit_message(store.load(v)), "run_id": m.run_id, "has_outputs": v in with_outputs})
    return out


@router.get("/HEAD")
def head(pid: str, request: Request):
    return _load(_store(request, pid), "HEAD").model_dump(mode="json")


@router.get("/diff")
def diff(pid: str, request: Request, from_: int = Query(alias="from"), to: int = Query()):
    store = _store(request, pid)
    return diff_specs(_load(store, from_), _load(store, to))


@router.get("/{version}")
def get_version(pid: str, version: int, request: Request):
    return _load(_store(request, pid), version).model_dump(mode="json")


@router.post("", status_code=201)
def commit(pid: str, body: OpsBody, request: Request, x_user: str | None = Header(None)):
    orchestrator = getattr(request.app.state, "orchestrator", None)
    run = orchestrator.active_run(pid) if orchestrator else None
    if run and any(s["n"] in (5, 6) and s["status"] == "running" for s in run["stages"]):
        raise ApiError(409, "run_in_progress", "a run is creating a new spec version (stage 5-6); retry later")
    message = f"user={x_user}; {body.message}" if x_user else body.message
    try:
        spec, result = _store(request, pid).commit_ops(body.base_version, body.ops, "editor", message)
    except VersionConflict as e:
        raise ApiError(409, "spec_conflict", str(e), {"base": e.base, "head": e.head}) from None
    except ValidationFailed as e:
        raise ApiError(422, "validation_failed", str(e), {"issues": _issues(e.issues)}) from None
    except OpError as e:
        raise ApiError(400, "bad_op", e.message, {"index": e.index, "op": e.op, "message": e.message}) from None
    touch(request.app.state.storage, pid)
    request.app.state.bus.emit(pid, None, None, "spec.created", data={"version": spec.meta.version, "source": "editor"})
    return {"version": spec.meta.version, "spec": spec.model_dump(mode="json"), "issues": _issues(result.issues)}


@router.post("/validate")
def dry_run(pid: str, body: OpsBody, request: Request):
    base = _load(_store(request, pid), body.base_version)
    try:
        spec = apply(base, body.ops, "editor", base.meta.version + 1)
    except OpError as e:
        raise ApiError(400, "bad_op", e.message, {"index": e.index, "op": e.op, "message": e.message}) from None
    r = validate(spec)
    return {"score": r.score, "passed": r.passed, "issues": _issues(r.issues),
            "rooms": [room.model_dump(mode="json") for room in spec.rooms],
            "tasks": review_tasks(spec, _labels(request, pid))}


def _labels(request: Request, pid: str):
    """Room labels the OCR found (stage 2 of the newest run that has one), for the review's leak tasks."""
    storage = request.app.state.storage
    ocr, grid = latest_stage_file(storage, pid, "02_grid/ocr.json"), latest_stage_file(storage, pid, "02_grid/grid.json")
    if not ocr or not grid:
        return None
    return labels_from_ocr(json.loads(ocr.read_text()), json.loads(grid.read_text())["px_to_mm"])


@router.post("/import", status_code=201)
async def import_spec(pid: str, request: Request, message: str = ""):
    store = _store(request, pid)
    try:
        spec = Spec.model_validate_json(await request.body())
    except ValidationError as e:
        raise ApiError(422, "invalid_spec", "spec does not match the schema",
                       {"errors": e.errors(include_url=False, include_context=False)}) from None
    try:
        saved = store.save_new(spec, "manual", message=message)
    except ValidationFailed as e:
        raise ApiError(422, "validation_failed", str(e), {"issues": _issues(e.issues)}) from None
    touch(request.app.state.storage, pid)
    request.app.state.bus.emit(pid, None, None, "spec.created", data={"version": saved.meta.version, "source": "manual"})
    return {"version": saved.meta.version}

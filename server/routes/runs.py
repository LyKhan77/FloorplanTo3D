"""Runs, stage artifacts and regenerate (PRD/09 §2.2, §2.3, §2.5)."""

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from core.pipeline import outputs_complete
from core.spec.store import SpecStore
from server.errors import ApiError
from server.orchestrator import STAGES

router = APIRouter(prefix="/api/projects/{pid}")


class RunBody(BaseModel):
    kind: str = "full"
    from_stage: int = 0
    params_override: dict | None = None
    profile_id: str | None = None


class ContinueBody(BaseModel):
    accept_low_score: bool = False


class RegenerateBody(BaseModel):
    version: int | str = "HEAD"


def _orch(request: Request):
    return request.app.state.orchestrator


@router.post("/runs", status_code=202)
def start(pid: str, body: RunBody, request: Request):
    if body.kind not in ("full", "from_stage", "regenerate"):
        raise ApiError(400, "bad_request", f"unknown run kind {body.kind}")
    if not 0 <= body.from_stage <= 10:
        raise ApiError(400, "bad_request", "from_stage must be 0-10")
    run = _orch(request).start_run(pid, body.kind, body.from_stage if body.kind == "from_stage" else 0,
                                   params_override=body.params_override, profile_id=body.profile_id)
    return {"run_id": run["run_id"], "status": run["status"]}


@router.get("/runs")
def list_runs(pid: str, request: Request):
    return _orch(request).list_runs(pid)


@router.get("/runs/{rid}")
def get_run(pid: str, rid: str, request: Request):
    request.app.state.storage.project_dir(pid)
    return _orch(request).load_run(pid, rid)


@router.post("/runs/{rid}/cancel")
def cancel(pid: str, rid: str, request: Request):
    request.app.state.storage.project_dir(pid)
    return _orch(request).cancel(pid, rid)


@router.post("/runs/{rid}/continue", status_code=202)
def continue_run(pid: str, rid: str, body: ContinueBody, request: Request):
    """A run stopped at stage 5 (low score, or paused for review) continues as a new run from stage 6 on HEAD."""
    run = _orch(request).load_run(pid, rid)
    if run["status"] == "needs_review":  # M8: the person approved the corrected spec
        orch = _orch(request)
        with orch.review_lock:  # M11: a dismiss of the same run waits, then finds it closed
            run = orch.load_run(pid, rid)
            if run["status"] != "needs_review":
                raise ApiError(409, "not_continuable", f"run {rid} is already {run['status']}")
            new = orch.start_run(pid, "from_stage", 6, params_override=run.get("params_override") or {},
                                 profile_id=run.get("profile_id"), extra={"review_open": _open_review_tasks(request, pid)})
            orch.close_review(pid, rid)
        return {"run_id": new["run_id"], "status": new["status"]}
    if run["status"] != "needs_attention" or run["stages"][5]["status"] != "needs_attention":
        raise ApiError(409, "not_continuable", "only runs stopped at stage 5 can continue")
    if not body.accept_low_score:
        raise ApiError(400, "bad_request", "set accept_low_score to continue")
    if not run["stages"][5]["metrics"].get("version"):
        raise ApiError(409, "no_spec", "stage 5 saved no spec: nothing to continue with")
    new = _orch(request).start_run(pid, "from_stage", 6)
    return {"run_id": new["run_id"], "status": new["status"]}


def _stage_dir(run_dir, n: int):
    return run_dir / "stages" / ("07_build" if n >= 7 else f"{n:02d}_{STAGES[n][1]}")


@router.get("/runs/{rid}/stages/{n}")
def stage_summary(pid: str, rid: str, n: int, request: Request):
    run = _orch(request).load_run(pid, rid)
    if not 0 <= n <= 10:
        raise ApiError(404, "not_found", "stage not found")
    run_dir = request.app.state.storage.project_dir(pid) / "runs" / rid
    base = run_dir / "stages"
    folder = _stage_dir(run_dir, n)
    files = sorted(str(p.relative_to(base)) for p in folder.rglob("*") if p.is_file()) if folder.exists() else []
    return run["stages"][n] | {"artifacts": files}


@router.get("/runs/{rid}/artifacts/{path:path}")
def artifact(pid: str, rid: str, path: str, request: Request):
    st = request.app.state.storage
    _orch(request).load_run(pid, rid)
    f = st.safe_join(st.project_dir(pid) / "runs" / rid / "stages", path)
    if not f.is_file():
        raise ApiError(404, "not_found", "file not found")
    return FileResponse(f)


@router.post("/regenerate", status_code=202)
def regenerate(pid: str, body: RegenerateBody, request: Request):
    d = request.app.state.storage.project_dir(pid)
    version = SpecStore(d / "specs").head() if body.version == "HEAD" else int(body.version)
    if version is not None and outputs_complete(d / "outputs" / f"v{version}"):
        return JSONResponse({"run_id": None, "reused": True}, status_code=200)
    run = _orch(request).start_run(pid, "regenerate", version=body.version)
    return {"run_id": run["run_id"], "status": run["status"]}


def _open_review_tasks(request: Request, pid: str) -> list[dict]:
    """The review tasks still open on the approved spec (HEAD): kept on the continuation as its record."""
    from core.spec.review_tasks import review_tasks
    from core.spec.store import SpecStore
    from server.routes.specs import _labels

    store = SpecStore(request.app.state.storage.project_dir(pid) / "specs")
    head = store.head()
    if head is None:
        return []
    return [{k: t[k] for k in ("id", "kind", "message", "at")} for t in review_tasks(store.load(head), _labels(request, pid))]

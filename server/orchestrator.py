"""Run orchestrator (PRD/02 §3.1, §3.2, §5): two FIFO queues (analysis 0-6, Blender 7-10), one worker each.

Run state lives in runs/<run_id>/run.json, written atomically on every transition. Stage implementations run
in worker threads and talk back only through the event bus and their return value.
"""

import asyncio
import logging
import shutil
import subprocess
import threading
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.blender_run import parse_progress
from core.config import Settings
from core.extraction.profiles import ProfileNotFound, load_profile
from core.extraction.stages import (
    run_params,
    stage_extract,
    stage_grid,
    stage_input,
    stage_preprocess,
    stage_rooms,
    stage_validate,
)
from core.llm_review.client import StrataClient
from core.llm_review.stage import stage_review
from core.llm_review.tasks import parse_prompt_llm
from core.pipeline import plan_mask_for, publish, stage_build, stage_report, stage_verify
from core.spec.store import SpecStore
from server.errors import ApiError
from server.events import EventBus
from server.projects import input_image, touch
from server.storage import Storage

log = logging.getLogger(__name__)

STAGES = [(0, "input"), (1, "preprocess"), (2, "grid"), (3, "extract"), (4, "rooms"), (5, "validate"),
          (6, "review"), (7, "build"), (8, "verify"), (9, "report"), (10, "publish")]
FIRST_BLENDER_STAGE = 7
STOP_ON_ATTENTION = {1, 2, 5}  # needs_attention here stops the run; at 6 and 8 it is only a warning
FIRST_SPEC_STAGE = 5  # stages before it read the previous stages' folders of the same run
REVIEW_STAGE = 6
BLENDER_TIMEOUT_S = 300


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def _code_version() -> str:
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False,
                       cwd=Path(__file__).resolve().parents[1])
    return f"git:{r.stdout.strip()}" if r.returncode == 0 else "unknown"


@dataclass
class StageContext:
    pid: str
    run_id: str
    stage: int
    version: int | None
    work_dir: Path
    project_dir: Path
    storage: Storage
    settings: Settings
    emit_log: Callable[..., None]
    emit_progress: Callable[[int, str], None]
    cancelled: threading.Event
    state: dict = field(default_factory=dict)  # shared between the stages of one run
    register_process: Callable[[subprocess.Popen], None] = lambda p: None
    params_override: dict = field(default_factory=dict)  # POST /runs params_override (explicit params win)
    profile: dict | None = None  # style profile chosen for the run (its params seed the sweep)
    emit_event: Callable[[str, dict], None] = lambda type, data: None  # e.g. llm.decision


# --- default stage implementations ------------------------------------------------------------------------------

def _strata(settings: Settings) -> StrataClient:
    return StrataClient.from_settings(settings)


def _use_strata(ctx: StageContext) -> bool:
    return run_params(ctx.project_dir, ctx.params_override, ctx.work_dir.parent).get("use_strata", True) is not False


def _input(ctx: StageContext) -> dict:
    if not list((ctx.project_dir / "input").glob("original.*")):
        return {"status": "failed", "message": "original upload missing"}
    llm_parse = None
    if "T0" in ctx.settings.llm_tasks_enabled and _use_strata(ctx):
        client = _strata(ctx.settings)
        if client.health():
            llm_parse = lambda prompt: parse_prompt_llm(client, prompt)
    return stage_input(ctx.project_dir, ctx.work_dir, ctx.params_override, llm_parse)


def _preprocess(ctx: StageContext) -> dict:
    return stage_preprocess(ctx.project_dir, ctx.work_dir)


def _grid(ctx: StageContext) -> dict:
    return stage_grid(ctx.project_dir, ctx.work_dir, ctx.params_override, ctx.emit_progress)


def _extract(ctx: StageContext) -> dict:
    return stage_extract(ctx.project_dir, ctx.work_dir, ctx.settings.sweep_max_candidates, ctx.emit_progress,
                         ctx.params_override, (ctx.profile or {}).get("params"))


def _rooms(ctx: StageContext) -> dict:
    return stage_rooms(ctx.project_dir, ctx.work_dir, ctx.emit_progress, ctx.params_override)


def _not_yet(milestone: str) -> Callable[[StageContext], dict]:
    def stage(ctx: StageContext) -> dict:
        return {"status": "skipped", "message": f"not implemented until {milestone}"}
    return stage


def _validate(ctx: StageContext) -> dict:
    if (ctx.work_dir.parent / "04_rooms" / "candidates.json").exists():
        result = stage_validate(ctx.project_dir, ctx.work_dir, ctx.run_id, ctx.emit_progress, ctx.params_override)
        if result.get("metrics", {}).get("version"):
            ctx.state["version"] = result["metrics"]["version"]
        return result
    head = SpecStore(ctx.project_dir / "specs").head()
    if head is None:
        return {"status": "needs_attention",
                "message": "no spec yet: import a spec (automatic extraction of walls/rooms arrives in M5b/M5c)"}
    ctx.state["version"] = head
    return {"status": "skipped", "message": f"using imported spec v{head}"}


def _review(ctx: StageContext) -> dict:
    result = stage_review(ctx.project_dir, ctx.work_dir, ctx.run_id, ctx.settings,
                          version=ctx.state.get("version", ctx.version), use_strata=_use_strata(ctx),
                          client=_strata(ctx.settings), emit=ctx.emit_event, progress=ctx.emit_progress,
                          cancelled=ctx.cancelled)
    if result.get("metrics", {}).get("version"):
        ctx.state["version"] = result["metrics"]["version"]
    return result


def _on_blender_line(ctx: StageContext, line: str) -> None:
    p = parse_progress(line)
    if p:
        ctx.emit_progress(*p)
    elif line.strip():
        level = "warn" if line.startswith("WARN") else "error" if line.startswith(("Error", "Traceback")) else "debug"
        ctx.emit_log(line, level)


def _build(ctx: StageContext) -> dict:
    version = ctx.state.get("version", ctx.version)
    spec = SpecStore(ctx.project_dir / "specs").load(version)
    image = input_image(ctx.storage, ctx.pid)
    doc, warnings = stage_build(spec, ctx.work_dir, image, ctx.storage.templates_dir, "BLENDER_WORKBENCH",
                                on_line=lambda line: _on_blender_line(ctx, line), on_start=ctx.register_process,
                                timeout_s=BLENDER_TIMEOUT_S, blender_bin=ctx.settings.blender_bin)
    ctx.state.update(spec=spec, image=image, doc=doc, warnings=warnings, version=version)
    return {"status": "succeeded", "warnings": warnings,
            "metrics": {"meshes": len(doc["meshes"]), "instances": len(doc["instances"]), "cameras": len(doc["cameras"])}}


def _verify(ctx: StageContext) -> dict:
    s = ctx.state
    v = stage_verify(s["spec"], ctx.work_dir, s["doc"], s["image"], s["warnings"],
                     plan_mask_for(ctx.project_dir, s["spec"]))
    s["verify"] = v
    status = {"needs_attention": "needs_attention", "failed": "failed"}.get(v["status"], "succeeded")
    return {"status": status, "warnings": v["warnings"],
            "metrics": {"iou": v["iou"], "glb_max_err_mm": v["glb_check"]["max_err_mm"]}}


def _report(ctx: StageContext) -> dict:
    s = ctx.state
    stage_report(s["spec"], ctx.work_dir, s["doc"], s["verify"], s["image"], ctx.run_id)
    return {"status": "succeeded"}


def _publish(ctx: StageContext) -> dict:
    version = ctx.state.get("version", ctx.version)
    out = publish(ctx.work_dir, ctx.project_dir / "outputs", version)
    files = sorted(p.name for p in out.iterdir() if p.is_file())
    ctx.state["published"] = {"version": version, "files": files}
    return {"status": "succeeded", "metrics": {"files": len(files)}}


DEFAULT_IMPLS: dict[int, Callable[[StageContext], dict]] = {
    0: _input, 1: _preprocess, 2: _grid, 3: _extract, 4: _rooms, 5: _validate,
    6: _review, 7: _build, 8: _verify, 9: _report, 10: _publish,
}


# --- orchestrator -----------------------------------------------------------------------------------------------

class Orchestrator:
    def __init__(self, storage: Storage, bus: EventBus, settings: Settings,
                 stage_impls: dict[int, Callable[[StageContext], dict]] | None = None):
        self.storage, self.bus, self.settings = storage, bus, settings
        self.impls = DEFAULT_IMPLS | (stage_impls or {})
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queues: dict[str, asyncio.Queue] = {}
        self._workers: list[asyncio.Task] = []
        self._active: dict[str, str] = {}  # project -> run in queue or running
        self._cancel: dict[str, threading.Event] = {}
        self._procs: dict[str, subprocess.Popen] = {}
        self._state: dict[str, dict] = {}
        self._running: set[str] = set()
        self._lock = threading.Lock()
        self.code_version = _code_version()

    # lifecycle
    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self.bus.bind_loop(self._loop)
        self._queues = {"analysis": asyncio.Queue(), "blender": asyncio.Queue()}
        self.recover()
        self._workers = [asyncio.create_task(self._worker(name)) for name in self._queues]

    async def stop(self) -> None:
        for event in self._cancel.values():
            event.set()
        for t in self._workers:
            t.cancel()
        for proc in list(self._procs.values()):
            proc.terminate()
            try:
                await asyncio.to_thread(proc.wait, 5)
            except subprocess.TimeoutExpired:
                proc.kill()

    # run files
    def _run_path(self, pid: str, rid: str) -> Path:
        return self.storage.projects_dir / pid / "runs" / rid / "run.json"

    def load_run(self, pid: str, rid: str) -> dict:
        path = self._run_path(pid, rid)
        if not path.exists():
            raise ApiError(404, "run_not_found", f"run {rid} not found")
        return self.storage.read_json(path)

    def _save(self, run: dict) -> None:
        self.storage.write_json_atomic(self._run_path(run["project_id"], run["run_id"]), run)

    def list_runs(self, pid: str) -> list[dict]:
        d = self.storage.project_dir(pid) / "runs"
        runs = [self.storage.read_json(p / "run.json") for p in d.iterdir() if (p / "run.json").exists()] if d.exists() else []
        return sorted(runs, key=lambda r: r["created_at"], reverse=True)

    def active_run(self, pid: str) -> dict | None:
        rid = self._active.get(pid)
        return self.load_run(pid, rid) if rid else None

    def queue_info(self) -> dict:
        waiting = sum(q.qsize() for q in self._queues.values())
        return {"waiting": waiting, "running": sorted(self._running),
                "blender_busy": any(self._stage_of(r) >= FIRST_BLENDER_STAGE for r in self._running)}

    def _stage_of(self, rid: str) -> int:
        return self._state.get(rid, {}).get("_stage", -1)

    # starting and cancelling
    def _seed_source(self, pid: str, upto: int) -> Path | None:
        """Stage folder of the latest run that has every stage folder 0..upto (for a from_stage rerun)."""
        for r in self.list_runs(pid):
            stages = self.storage.project_dir(pid) / "runs" / r["run_id"] / "stages"
            if all((stages / f"{n:02d}_{STAGES[n][1]}").is_dir() for n in range(upto + 1)):
                return stages
        return None

    def start_run(self, pid: str, kind: str, from_stage: int = 0, version: int | str = "HEAD",
                  params_override: dict | None = None, profile_id: str | None = None) -> dict:
        project_dir = self.storage.project_dir(pid)
        if profile_id:
            try:
                load_profile(self.storage, profile_id)
            except ProfileNotFound as e:
                raise ApiError(404, "not_found", str(e)) from None
        with self._lock:
            if pid in self._active:
                raise ApiError(409, "run_in_progress", f"project {pid} already has an active run",
                               {"run_id": self._active[pid]})
            head = SpecStore(project_dir / "specs").head()
            if kind == "regenerate" or from_stage > FIRST_BLENDER_STAGE:
                from_stage = FIRST_BLENDER_STAGE  # stages 8-10 need stage 7's spec and Blender output from this run
            seed = None
            if 0 < from_stage <= REVIEW_STAGE:  # the Strata review reads stages 1-5 of its run too
                seed = self._seed_source(pid, from_stage - 1)
                if seed is None and from_stage <= FIRST_SPEC_STAGE:
                    from_stage = 0  # nothing to continue from: run the extraction from the start
            resolved = head if version == "HEAD" else int(version)
            if from_stage >= FIRST_BLENDER_STAGE and resolved is None:
                raise ApiError(409, "no_spec", "import a spec before building outputs")
            rid = self.storage.new_run_id()
            run = {"run_id": rid, "project_id": pid, "kind": kind, "from_stage": from_stage, "version": resolved,
                   "spec_version_in": resolved, "spec_version_out": None, "status": "queued",
                   "stages": [{"n": n, "name": name, "status": "skipped" if n < from_stage else "pending",
                               "started_at": None, "ended_at": None, "duration_ms": None, "progress": None,
                               "metrics": {}, "warnings": []} for n, name in STAGES],
                   "code_version": self.code_version, "blender_version": None, "created_at": _now(), "error": None,
                   "params_override": params_override or {}, "profile_id": profile_id}
            if seed is not None:
                target = project_dir / "runs" / rid / "stages"
                for n in range(from_stage):
                    name = f"{n:02d}_{STAGES[n][1]}"
                    shutil.copytree(seed / name, target / name)
            self._save(run)
            self._active[pid] = rid
            self._cancel[rid] = threading.Event()
            self._state[rid] = {}
        touch(self.storage, pid, latest_run=rid)
        self.bus.emit(pid, rid, None, "run.queued", data={"status": "queued"})
        self._enqueue("analysis" if from_stage < FIRST_BLENDER_STAGE else "blender", pid, rid)
        return run

    def _enqueue(self, queue: str, pid: str, rid: str) -> None:
        self._loop.call_soon_threadsafe(self._queues[queue].put_nowait, (pid, rid))

    def cancel(self, pid: str, rid: str) -> dict:
        run = self.load_run(pid, rid)
        if self._active.get(pid) != rid:
            raise ApiError(409, "run_not_active", f"run {rid} is already {run['status']}")
        self._cancel[rid].set()
        proc = self._procs.get(rid)
        if proc and proc.poll() is None:
            proc.terminate()
        if run["status"] == "queued":  # never started: finish it now; the worker skips it on dequeue
            self._finish(run, "failed", "cancelled")
        return {"cancelled": rid}

    # execution
    async def _worker(self, queue: str) -> None:
        while True:
            pid, rid = await self._queues[queue].get()
            try:
                await self._run_part(queue, pid, rid)
            except Exception:  # noqa: BLE001 - a bug must not kill the worker loop
                error = traceback.format_exc(limit=3)
                try:
                    self._finish(self.load_run(pid, rid), "failed", error)
                except Exception:  # nor may a broken run.json (or a full disk) while recording it
                    log.exception("run %s/%s failed and could not be recorded:\n%s", pid, rid, error)
                    with self._lock:
                        if self._active.get(pid) == rid:
                            del self._active[pid]

    async def _run_part(self, queue: str, pid: str, rid: str) -> None:
        run = self.load_run(pid, rid)
        if run["status"] not in ("queued", "running") or self._cancel.get(rid, threading.Event()).is_set():
            if self._active.get(pid) == rid and run["status"] in ("queued", "running"):
                self._finish(run, "failed", "cancelled")
            return
        stages = range(FIRST_BLENDER_STAGE) if queue == "analysis" else range(FIRST_BLENDER_STAGE, len(STAGES))
        self._running.add(rid)
        try:
            for n in stages:
                if run["stages"][n]["status"] != "pending":
                    continue
                if self._cancel[rid].is_set():
                    self._finish(run, "failed", "cancelled")
                    return
                if not await self._run_stage(run, n):
                    return
                if self._cancel[rid].is_set():
                    self._finish(run, "failed", "cancelled")
                    return
        finally:
            self._running.discard(rid)
        if queue == "analysis":
            self._enqueue("blender", pid, rid)
        else:
            attention = any(s["status"] == "needs_attention" for s in run["stages"])
            published = self._state.get(rid, {}).get("published")
            if published:
                self.bus.emit(pid, rid, 10, "output.ready", data=published)
            self._finish(run, "needs_attention" if attention else "succeeded")

    def _context(self, run: dict, n: int) -> StageContext:
        pid, rid = run["project_id"], run["run_id"]
        project_dir = self.storage.projects_dir / pid
        run_dir = project_dir / "runs" / rid / "stages"
        work = run_dir / "07_build" / "work" if n >= FIRST_BLENDER_STAGE else run_dir / f"{n:02d}_{STAGES[n][1]}"

        def emit_log(msg: str, level: str = "info") -> None:
            self.bus.emit(pid, rid, n, "stage.log", level=level, msg=msg)

        def emit_progress(percent: int, msg: str = "") -> None:
            self.bus.emit(pid, rid, n, "stage.progress", data={"percent": percent, "msg": msg})

        def register(proc: subprocess.Popen) -> None:
            self._procs[rid] = proc

        return StageContext(pid, rid, n, run.get("version"), work, project_dir, self.storage, self.settings,
                            emit_log, emit_progress, self._cancel[rid], self._state[rid], register,
                            params_override=run.get("params_override") or {},
                            profile=load_profile(self.storage, run["profile_id"]) if run.get("profile_id") else None,
                            emit_event=lambda type, data: self.bus.emit(pid, rid, n, type, data=data))

    async def _run_stage(self, run: dict, n: int) -> bool:
        """Run one stage; return False when the run must stop."""
        pid, rid = run["project_id"], run["run_id"]
        stage = run["stages"][n]
        if run["status"] == "queued":
            run["status"] = "running"
            self.bus.emit(pid, rid, None, "run.started", data={"status": "running"})
        stage.update(status="running", started_at=_now())
        self._state[rid]["_stage"] = n
        self._save(run)
        self.bus.emit(pid, rid, n, "stage.started", data={"status": "running"})
        t0 = asyncio.get_running_loop().time()
        try:
            result = await asyncio.to_thread(self.impls[n], self._context(run, n))
        except Exception as e:  # noqa: BLE001 - a failing stage fails the run, not the server
            result = {"status": "failed", "message": f"{type(e).__name__}: {e}"}
        finally:
            self._procs.pop(rid, None)
        status = result.get("status", "succeeded")
        if n in (FIRST_SPEC_STAGE, REVIEW_STAGE) and result.get("metrics", {}).get("version"):
            run.update(spec_version_out=result["metrics"]["version"], version=result["metrics"]["version"])
        stage.update(status=status, ended_at=_now(), duration_ms=int((asyncio.get_running_loop().time() - t0) * 1000),
                     metrics=result.get("metrics", {}), warnings=result.get("warnings", []))
        if result.get("message"):
            self.bus.emit(pid, rid, n, "stage.log", level="error" if status == "failed" else "info",
                          msg=result["message"])
        self._save(run)
        self.bus.emit(pid, rid, n, "stage.finished",
                      data={"status": status, "duration_ms": stage["duration_ms"], "metrics": stage["metrics"]})
        if status == "failed":
            self._finish(run, "failed", "cancelled" if self._cancel[rid].is_set() else result.get("message", "failed"))
            return False
        if status == "needs_attention" and n in STOP_ON_ATTENTION:
            self._finish(run, "needs_attention", result.get("message"))
            return False
        return True

    def _finish(self, run: dict, status: str, error: str | None = None) -> None:
        pid, rid = run["project_id"], run["run_id"]
        run.update(status=status, error=error)
        self._save(run)
        with self._lock:
            if self._active.get(pid) == rid:
                del self._active[pid]
        self._state.pop(rid, None)
        if (self.storage.projects_dir / pid / "project.json").exists():
            touch(self.storage, pid, status=status)
        self.bus.emit(pid, rid, None, "run.finished", data={"status": status, "error": error})

    # restart recovery
    def recover(self) -> None:
        if not self.storage.projects_dir.exists():
            return
        queued = []
        for project in self.storage.projects_dir.iterdir():
            for tmp in (project / "outputs").glob("v*.tmp"):
                shutil.rmtree(tmp, ignore_errors=True)
            for run_file in (project / "runs").glob("*/run.json"):
                run = self.storage.read_json(run_file)
                if run["status"] == "running":
                    closed = [s for s in run["stages"] if s["status"] == "running"]
                    for s in closed:
                        s.update(status="failed", ended_at=_now())
                    run.update(status="failed", error="interrupted")
                    self._save(run)
                    for s in closed:
                        self.bus.emit(run["project_id"], run["run_id"], s["n"], "stage.finished",
                                      data={"status": "failed", "duration_ms": None, "metrics": {}})
                    self.bus.emit(run["project_id"], run["run_id"], None, "run.finished",
                                  data={"status": "failed", "error": "interrupted"})
                elif run["status"] == "queued":
                    queued.append(run)
        for run in sorted(queued, key=lambda r: r["created_at"]):
            pid, rid = run["project_id"], run["run_id"]
            self._active[pid] = rid
            self._cancel[rid] = threading.Event()
            self._state[rid] = {}
            first = next((s["n"] for s in run["stages"] if s["status"] == "pending"), FIRST_BLENDER_STAGE)
            self._queues["analysis" if first < FIRST_BLENDER_STAGE else "blender"].put_nowait((pid, rid))

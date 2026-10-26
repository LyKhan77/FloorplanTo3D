"""Project creation and summaries (PRD/09 §2.1, FR-IN-01…05, NFR-SC-03)."""

import hashlib
import json
import os
import re
import shutil
import threading
from collections import defaultdict
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from core.spec.store import SpecStore
from core.spec.validate import validate
from server.errors import ApiError
from server.storage import Storage

MAGIC = (("jpg", b"\xff\xd8\xff"), ("png", b"\x89PNG\r\n\x1a\n"), ("pdf", b"%PDF-"))


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sniff_type(head: bytes) -> Literal["jpg", "png", "pdf"] | None:
    return next((ext for ext, magic in MAGIC if head.startswith(magic)), None)


def sanitize_filename(name: str) -> str:
    base = Path(name.replace("\\", "/")).name
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._") or "upload"


def create_project(storage: Storage, data: bytes, filename: str, name: str | None, prompt: str, params: dict,
                   page: int | None, max_bytes: int) -> dict:
    if len(data) > max_bytes:
        raise ApiError(413, "file_too_large", f"upload exceeds {max_bytes // (1024 * 1024)} MB")
    ext = sniff_type(data[:16])
    if ext is None:
        raise ApiError(415, "unsupported_type", "only JPEG, PNG or PDF files are accepted")
    clean = sanitize_filename(filename)
    title = name or Path(clean).stem
    pid = storage.new_project_id(title)
    storage.projects_dir.mkdir(parents=True, exist_ok=True)
    tmp = storage.projects_dir / f".tmp-{pid}"
    try:
        (tmp / "input").mkdir(parents=True)
        (tmp / "input" / f"original.{ext}").write_bytes(data)
        storage.write_json_atomic(tmp / "input" / "input.json", {
            "filename": clean, "sha256": hashlib.sha256(data).hexdigest(), "prompt": prompt, "params": params,
            "page": page, "type": ext})
        ts = now()
        project = {"project_id": pid, "name": title, "created_at": ts, "updated_at": ts, "params": params,
                   "status": "new", "latest_run": None}
        storage.write_json_atomic(tmp / "project.json", project)
        os.rename(tmp, storage.projects_dir / pid)  # the project appears complete or not at all
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return project


def input_image(storage: Storage, pid: str) -> Path | None:
    """The plan as a raster: the original JPEG/PNG, or the page stage 1 rasterised from a PDF (input/raster.png)."""
    d = storage.project_dir(pid) / "input"
    return next((p for p in (d / "original.jpg", d / "original.png", d / "raster.png") if p.exists()), None)


def output_versions(storage: Storage, pid: str) -> list[int]:
    out = storage.project_dir(pid) / "outputs"
    if not out.exists():
        return []
    return sorted((int(p.name[1:]) for p in out.iterdir()
                   if re.fullmatch(r"v\d+", p.name) and (p / "shell.glb").exists()), reverse=True)


@lru_cache(maxsize=256)
def _score(spec_file: str, mtime: float) -> float:
    from core.spec.models import Spec

    return round(validate(Spec.model_validate_json(Path(spec_file).read_text())).score, 3)


def latest_run(storage: Storage, pid: str) -> dict | None:
    project = storage.read_json(storage.project_dir(pid) / "project.json")
    rid = project.get("latest_run")
    path = storage.project_dir(pid) / "runs" / str(rid) / "run.json"
    return storage.read_json(path) if rid and path.exists() else None


def summary(storage: Storage, pid: str) -> dict:
    d = storage.project_dir(pid)
    project = storage.read_json(d / "project.json")
    store = SpecStore(d / "specs")
    head = store.head()
    run = latest_run(storage, pid)
    active = next((s["n"] for s in (run or {}).get("stages", []) if s["status"] == "running"), None)
    score = None
    if head:
        f = d / "specs" / f"spec.v{head}.json"
        score = _score(str(f), f.stat().st_mtime)
    iou = None
    versions = output_versions(storage, pid)
    if versions and (d / "outputs" / f"v{versions[0]}" / "verify.json").exists():
        iou = json.loads((d / "outputs" / f"v{versions[0]}" / "verify.json").read_text()).get("iou")
    return {"project_id": pid, "name": project["name"], "floor": project.get("params", {}).get("floor_name"),
            "status": run["status"] if run else project.get("status", "new"), "active_stage": active,
            "validator_score": score, "iou": iou, "head_version": head, "updated_at": project["updated_at"]}


_touch_locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)


def touch(storage: Storage, pid: str, **changes) -> dict:
    """Read-modify-write of project.json, serialised per project (routes and run threads both call it)."""
    path = storage.project_dir(pid) / "project.json"
    with _touch_locks[pid]:
        project = storage.read_json(path) | changes | {"updated_at": now()}
        storage.write_json_atomic(path, project)
    return project

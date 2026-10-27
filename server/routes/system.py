"""/api/health and /api/config (PRD/09 §2.9)."""

import subprocess
import time
from functools import lru_cache

import httpx
from fastapi import APIRouter, Request

router = APIRouter(prefix="/api")


@lru_cache(maxsize=4)
def _blender_version(binary: str) -> str | None:
    try:
        r = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    first = r.stdout.splitlines()[0] if r.returncode == 0 and r.stdout else ""
    return first.replace("Blender", "").strip() or None


def _strata(base_url: str) -> dict:
    root = base_url.removesuffix("/").removesuffix("/v1")
    t0 = time.monotonic()
    try:
        r = httpx.get(f"{root}/health", timeout=2)
        latency = int((time.monotonic() - t0) * 1000)
        status = None
        try:
            s = httpx.get(f"{root}/status", timeout=2)
            body = s.json() if s.status_code == 200 else {}
            # Strata answers {"busy": bool, "queued": n}; keep a plain "status" field for other servers
            status = body.get("status") or (("processing" if body["busy"] else "idle") if "busy" in body else None)
        except (httpx.HTTPError, ValueError):
            pass
        return {"ok": r.status_code == 200, "status": status, "latency_ms": latency}
    except httpx.HTTPError:
        return {"ok": False, "status": None, "latency_ms": None}


@router.get("/health")
def health(request: Request):
    s = request.app.state.settings
    q = request.app.state.orchestrator.queue_info()
    version = _blender_version(s.blender_bin)
    return {"server": "ok", "strata": _strata(s.strata_base_url),
            "blender": {"ok": version is not None, "version": version, "busy": q["blender_busy"]},
            "queue": {"waiting": q["waiting"], "running": q["running"]}}


@router.get("/config")
def config(request: Request):
    s = request.app.state.settings
    return {"llm_tasks_enabled": list(s.llm_tasks_enabled), "llm_max_iter": s.llm_max_iter, "llm_votes": s.llm_votes,
            "sweep_max_candidates": s.sweep_max_candidates, "max_upload_mb": s.max_upload_mb, "schema_version": "1.0",
            "code_version": request.app.state.orchestrator.code_version, "strata_base_url": s.strata_base_url,
            "strata_model": s.strata_model, "blender_bin": s.blender_bin}
